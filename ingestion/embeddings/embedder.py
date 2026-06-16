"""
Corpus embedding job - embeds public legal source chunks only.

Model: bge-large-en-v1.5 via local Ollama (1024-dim).
Schema: vector(1024) - see migrations 080_embedding_1024_prep.sql.

Corpus path only (public Crown/Open Justice material). No text-embedding-3-small.

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
from ingestion.embeddings.ollama_embed import embed_texts_ollama

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s  -  %(message)s",
)
logger = logging.getLogger(__name__)
console = Console()

EMBED_BATCH_SIZE = 16
EMBED_DIM = settings.embedding_dim
EMBED_MODEL = settings.embedding_model

TABLES = ["legislation", "case_law_chunks", "acas_guidance", "official_guidance"]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using local Ollama."""
    if not texts:
        return []
    return embed_texts_ollama(texts)


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
    console.print(
        f"[bold green]Embedding job  -  model: {EMBED_MODEL} ({EMBED_DIM}-dim, Ollama local)[/bold green]"
    )
    total = 0
    for table in tables:
        count = embed_table(table)
        total += count
        console.print(f"  {table}: [green]{count} embedded[/green]")
    console.print(f"\n[bold]Total chunks embedded: {total}[/bold]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed corpus chunks using local Ollama")
    parser.add_argument("--table", choices=TABLES, help="Embed only this table")
    args = parser.parse_args()
    embed_all(table_filter=args.table)


if __name__ == "__main__":
    main()
