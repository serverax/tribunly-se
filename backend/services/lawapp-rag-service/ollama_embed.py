"""Query embedding via local Ollama (bge-large-en-v1.5, 1024-dim). No fastembed fallback."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-large-en-v1.5")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))


def ollama_base_url() -> str:
    return os.getenv(
        "LAWAPP_OLLAMA_BASE_URL",
        os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_URL", "http://ollama:11434")),
    ).rstrip("/")


def embed_query(text: str) -> list[float]:
    """Embed query text. Fails closed on unreachable Ollama or dimension mismatch."""
    payload = json.dumps({"model": EMBEDDING_MODEL, "prompt": text[:8000]}).encode("utf-8")
    req = urllib.request.Request(
        f"{ollama_base_url()}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama not reachable at {ollama_base_url()}: {exc}") from exc
    vec = body.get("embedding")
    if not vec or len(vec) != EMBEDDING_DIM:
        raise RuntimeError(
            f"Query embedding dim {len(vec) if vec else 0} != expected {EMBEDDING_DIM}"
        )
    return vec
