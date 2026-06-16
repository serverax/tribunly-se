#!/usr/bin/env python3
"""
Re-embed corpus_chunks with 1024-dim local Ollama model.

Owner decision Deployment Q5: bge-large-en-v1.5 or mxbai-embed-large via Ollama.
Run after migration 080 and Ollama model pull:

  ollama pull bge-large-en-v1.5
  python scripts/reembed_corpus_1024.py

Fails closed if Ollama is unreachable. Does not call external embedding APIs.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OLLAMA_BASE = os.getenv("LAWAPP_OLLAMA_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-large-en-v1.5")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
BATCH_SIZE = int(os.getenv("REEMBED_BATCH_SIZE", "16"))


def _ollama_embed(text: str) -> list[float]:
    payload = json.dumps({"model": EMBEDDING_MODEL, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE.rstrip('/')}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    vec = body.get("embedding")
    if not vec or len(vec) != EMBEDDING_DIM:
        raise RuntimeError(f"Unexpected embedding dim: {len(vec) if vec else 0} (expected {EMBEDDING_DIM})")
    return vec


def main() -> int:
    try:
        _ollama_embed("health check")
    except (urllib.error.URLError, RuntimeError) as exc:
        logger.error("Ollama not ready at %s: %s", OLLAMA_BASE, exc)
        logger.error("Pull model first: ollama pull %s", EMBEDDING_MODEL)
        return 1

    from ingestion.db import get_connection

    conn = get_connection()
    updated = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, body_text FROM corpus_chunks
                WHERE body_text IS NOT NULL
                ORDER BY id
                """
            )
            rows = cur.fetchall()
        logger.info("Re-embedding %d chunks with %s (%d-dim)", len(rows), EMBEDDING_MODEL, EMBEDDING_DIM)

        for chunk_id, body_text in rows:
            vec = _ollama_embed(body_text[:8000])
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE corpus_chunks
                       SET embedding = %s::vector,
                           embedding_model = %s,
                           embedding_dim = %s,
                           embedding_created_at = now(),
                           updated_at = now()
                     WHERE id = %s
                    """,
                    (vec, EMBEDDING_MODEL, EMBEDDING_DIM, chunk_id),
                )
            conn.commit()
            updated += 1
            if updated % BATCH_SIZE == 0:
                logger.info("Updated %d / %d", updated, len(rows))
    finally:
        conn.close()

    logger.info("Done. Updated %d chunks.", updated)
    return 0


if __name__ == "__main__":
    sys.exit(main())
