"""Redis cache for graph traversal results (graph:chain:{hash})."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Optional

from backend.domains.constants import DEFAULT_JURISDICTION

logger = logging.getLogger(__name__)

_DEFAULT_TTL = int(os.getenv("GRAPH_CACHE_TTL_SECONDS", "3600"))
_REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


def _cache_key(query: str, claim_type: str, jurisdiction: str, mode: str) -> str:
    raw = f"{query}|{claim_type}|{jurisdiction}|{mode}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"graph:chain:{digest}"


def _redis_client():
    try:
        import redis

        return redis.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    except Exception as exc:
        logger.debug("Redis client unavailable for graph cache: %s", exc)
        return None


def get_cached_chain(
    query: str,
    claim_type: str = "",
    jurisdiction: str = DEFAULT_JURISDICTION,
    mode: str = "postgres",
) -> Optional[dict[str, Any]]:
    client = _redis_client()
    if client is None:
        return None
    try:
        raw = client.get(_cache_key(query, claim_type, jurisdiction, mode))
        if not raw:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.debug("Graph cache read skipped: %s", exc)
        return None


def set_cached_chain(
    payload: dict[str, Any],
    query: str,
    claim_type: str = "",
    jurisdiction: str = DEFAULT_JURISDICTION,
    mode: str = "postgres",
    ttl: int = _DEFAULT_TTL,
) -> None:
    client = _redis_client()
    if client is None:
        return
    try:
        client.setex(
            _cache_key(query, claim_type, jurisdiction, mode),
            ttl,
            json.dumps(payload, default=str),
        )
    except Exception as exc:
        logger.debug("Graph cache write skipped: %s", exc)
