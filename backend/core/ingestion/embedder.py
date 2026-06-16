"""Embedder  -  Perpetual Law Brain stage 4.

Chunks and vectorises content ONLY after the critic and graph linker have
approved it. Writes provenance-complete rows into corpus_chunks (the unified
retrieval table) with a content hash, and marks previous chunks of the same
source stale when the content hash changes.

Embeddings are local (Ollama bge-large-en-v1.5, 1024-dim). No external API.
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_EMBED_MODEL = "bge-large-en-v1.5"
_EMBED_DIM = 1024


def _embed(text: str) -> list[float]:
    from ingestion.embeddings.ollama_embed import embed_text_ollama
    return embed_text_ollama(text)


def _resolve_cache_dir() -> str:
    explicit = os.environ.get("FASTEMBED_CACHE_PATH")
    if explicit:
        return explicit
    baked = "/app/fastembed_cache"
    if os.path.isdir(baked) and os.access(baked, os.W_OK):
        return baked
    return os.path.join(
        os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
        "lawapp", "fastembed",
    )


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def chunk_text(text: str, size: int = 800) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [text[i:i + size] for i in range(0, len(text), size)]


def _chunk_hash(source_url: str, idx: int, body: str) -> str:
    return hashlib.sha256(f"autoingest:{source_url}:{idx}:{body}".encode()).hexdigest()


def _get_conn():
    from ingestion.db import get_connection
    return get_connection()


@dataclass
class EmbedResult:
    chunks_written: int
    chunk_hashes: list[str]
    stale_marked: int


class CorpusEmbedder:
    def __init__(self, get_conn: Callable = _get_conn) -> None:
        self._get_conn = get_conn

    def store(self, *, source_url: str, authority_ref: str, jurisdiction_code: str,
              body_text: str, title: str = "", source_type: str = "primary_legislation",
              ingestion_run_id: Optional[str] = None, embed: bool = True) -> EmbedResult:
        """Chunk, (optionally) embed, and upsert corpus_chunks rows. Idempotent on
        chunk_hash. Returns the hashes written so the caller can mark stale."""
        if not source_url:
            raise ValueError("refusing to embed a chunk without source_url (provenance)")
        chunks = chunk_text(body_text)
        hashes: list[str] = []
        written = 0
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema='public'
                          AND table_name='corpus_chunks'
                          AND column_name='jurisdiction'
                    )
                    """
                )
                has_legacy_jurisdiction = bool(cur.fetchone()[0])
                for idx, body in enumerate(chunks):
                    h = _chunk_hash(source_url, idx, body)
                    hashes.append(h)
                    emb = _vec_literal(_embed(body)) if embed else None
                    if has_legacy_jurisdiction:
                        cur.execute(
                            """
                            INSERT INTO corpus_chunks
                                (source_table, source_url, authority_ref, jurisdiction, jurisdiction_code,
                                 domain, claim_type, title, body_text, chunk_index, chunk_hash,
                                 tokens_estimate, embedding, embedding_model, embedding_created_at,
                                 is_current, source_type, ingestion_run_id)
                            VALUES (%s,%s,%s,%s,%s,'employment_uk','unfair_dismissal',%s,%s,%s,%s,%s,
                                    %s::vector, %s, now(), true, %s, %s::uuid)
                            ON CONFLICT (chunk_hash) DO NOTHING
                            """,
                            ("autonomous_ingest", source_url, authority_ref, jurisdiction_code, jurisdiction_code,
                             title, body, idx, h, max(1, len(body) // 4),
                             emb, (_EMBED_MODEL if embed else None), source_type,
                             ingestion_run_id),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO corpus_chunks
                                (source_table, source_url, authority_ref, jurisdiction_code,
                                 domain, claim_type, title, body_text, chunk_index, chunk_hash,
                                 tokens_estimate, embedding, embedding_model, embedding_created_at,
                                 is_current, source_type, ingestion_run_id)
                            VALUES (%s,%s,%s,%s,'employment_uk','unfair_dismissal',%s,%s,%s,%s,%s,
                                    %s::vector, %s, now(), true, %s, %s::uuid)
                            ON CONFLICT (chunk_hash) DO NOTHING
                            """,
                            ("autonomous_ingest", source_url, authority_ref, jurisdiction_code,
                             title, body, idx, h, max(1, len(body) // 4),
                             emb, (_EMBED_MODEL if embed else None), source_type,
                             ingestion_run_id),
                        )
                    written += cur.rowcount
            conn.commit()
        finally:
            conn.close()
        return EmbedResult(chunks_written=written, chunk_hashes=hashes, stale_marked=0)

    def mark_stale(self, source_url: str, current_hashes: list[str]) -> int:
        """Mark rows for this source whose hash is NOT in the current set as
        not-current (content_hash change detection)."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE corpus_chunks SET is_current=false, updated_at=now()
                       WHERE source_url=%s AND is_current=true
                         AND NOT (chunk_hash = ANY(%s))""",
                    (source_url, current_hashes or [""]),
                )
                n = cur.rowcount
            conn.commit()
            return n
        finally:
            conn.close()
