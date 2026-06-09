"""
Corpus embedding job — embeds public legal source chunks only.

Model: BAAI/bge-small-en-v1.5 via fastembed (384-dim, ONNX, no torch required)
Schema: vector(384) — see migration 016_vector_dim_384.sql

fastembed advantages:
  - No torch dependency (uses ONNX Runtime)
  - Works on Python 3.12
  - No mega-cache assertion errors
  - Lightweight (~100MB vs ~2GB for torch)

Corpus path only (public Crown/Open Justice material).

Usage:
    python -m ingestion.embeddings.embedder              # embed all tables
    python -m ingestion.embeddings.embedder --table legislation
"""

from __future__ import annotations

import argparse
import logging
from typing import Optional

from rich.console import Console
from rich.progress import track

from ingestion.config import settings
from ingestion.db import get_connection

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
console = Console()

EMBED_BATCH_SIZE = 64
EMBED_DIM        = 384
EMBED_MODEL      = "BAAI/bge-small-en-v1.5"   # 384-dim, fast, ONNX

import os as _os


def _resolve_cache_dir() -> str:
    """Resolve a writable fastembed cache dir across environments.

    Order: explicit FASTEMBED_CACHE_PATH → baked-in container cache when it
    exists AND is writable (Docker) → user cache (host/WSL). Hardcoding the
    container path broke host/WSL runs with PermissionError on /app.
    """
    explicit = _os.environ.get("FASTEMBED_CACHE_PATH")
    if explicit:
        return explicit
    baked = "/app/fastembed_cache"
    if _os.path.isdir(baked) and _os.access(baked, _os.W_OK):
        return baked
    return _os.path.join(
        _os.environ.get("XDG_CACHE_HOME", _os.path.expanduser("~/.cache")),
        "lawapp", "fastembed",
    )


_CACHE = _resolve_cache_dir()

TABLES = ["legislation", "case_law_chunks", "acas_guidance", "official_guidance"]

_model = None


def _get_model():
    """Load fastembed model once (lazy, cached)."""
    global _model
    if _model is None:
        try:
            from fastembed import TextEmbedding
        except ImportError:
            raise ImportError(
                "fastembed is not installed. Run: pip install fastembed"
            )
        console.print(f"Loading embedding model: [bold]{EMBED_MODEL}[/bold] (fastembed ONNX)")
        _model = TextEmbedding(model_name=EMBED_MODEL, cache_dir=_CACHE)
        console.print(f"  Output dimension: {EMBED_DIM}")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using fastembed (ONNX, no torch)."""
    if not texts:
        return []
    model = _get_model()
    embeddings = list(model.embed(texts))
    return [e.tolist() for e in embeddings]


def embed_table(table: str) -> int:
    """Embed all rows in `table` with embedding IS NULL. Returns count embedded."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, body_text FROM {table} WHERE embedding IS NULL ORDER BY created_at"
            )
            rows = cur.fetchall()

        if not rows:
            console.print(f"  [grey50]{table}: nothing to embed[/grey50]")
            return 0

        console.print(f"  {table}: {len(rows)} chunks to embed")
        embedded = 0
        ids_batch: list = []
        texts_batch: list[str] = []

        for row_id, body_text in track(rows, description=f"Embedding {table}…"):
            ids_batch.append(row_id)
            texts_batch.append((body_text or "")[:2000])

            if len(texts_batch) >= EMBED_BATCH_SIZE:
                _flush_batch(conn, table, ids_batch, texts_batch)
                embedded += len(ids_batch)
                ids_batch, texts_batch = [], []

        if texts_batch:
            _flush_batch(conn, table, ids_batch, texts_batch)
            embedded += len(ids_batch)

        return embedded
    finally:
        conn.close()


def _flush_batch(conn, table: str, ids: list, texts: list[str]) -> None:
    embeddings = embed_texts(texts)
    with conn.cursor() as cur:
        for row_id, embedding in zip(ids, embeddings):
            cur.execute(
                f"UPDATE {table} SET embedding = %s WHERE id = %s",
                (embedding, row_id),
            )
    conn.commit()


def embed_all(table_filter: Optional[str] = None) -> None:
    tables = [table_filter] if table_filter else TABLES
    console.print(f"[bold green]Embedding job — model: {EMBED_MODEL} ({EMBED_DIM}-dim, fastembed ONNX)[/bold green]")
    total = 0
    for table in tables:
        count = embed_table(table)
        total += count
        console.print(f"  {table}: [green]{count} embedded[/green]")
    console.print(f"\n[bold]Total chunks embedded: {total}[/bold]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed corpus chunks using fastembed ONNX")
    parser.add_argument("--table", choices=TABLES, help="Embed only this table")
    args = parser.parse_args()
    embed_all(table_filter=args.table)


if __name__ == "__main__":
    main()
