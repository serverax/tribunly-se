"""Local Ollama embedding helper (1024-dim, no external API)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

from ingestion.config import settings

logger = logging.getLogger(__name__)


def ollama_base_url() -> str:
    return os.getenv(
        "LAWAPP_OLLAMA_BASE_URL",
        os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    ).rstrip("/")


def embed_text_ollama(text: str) -> list[float]:
    """Embed one text via Ollama /api/embeddings. Fails closed if unreachable."""
    model = settings.embedding_model
    dim = settings.embedding_dim
    payload = json.dumps({"model": model, "prompt": text[:8000]}).encode("utf-8")
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
    if not vec or len(vec) != dim:
        raise RuntimeError(f"Unexpected embedding dim {len(vec) if vec else 0} (expected {dim})")
    return vec


def embed_texts_ollama(texts: list[str]) -> list[list[float]]:
    return [embed_text_ollama(t) for t in texts]
