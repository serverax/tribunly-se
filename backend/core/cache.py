"""Process-wide Redis cache with mandatory graceful degradation.

Scale contract (100k concurrent target):
  - Hot read paths (citation validation, retrieval) consult this cache first so a
    cache hit answers WITHOUT touching PostgreSQL.
  - The cache is NEVER on the critical correctness path: every operation is
    best-effort. If Redis is slow, down, or absent, every call degrades to a
    miss / no-op and the caller falls through to the authoritative database.
    A cache failure must never raise into the request path and never crash a
    worker (constitution: "degrade gracefully under extreme load, don't crash").

Security:
  - This module only ever caches DETERMINISTIC, low-sensitivity facts derived
    from the local corpus (e.g. "does corpus_chunks contain this UUID?": "1"/"0").
  - It must NEVER be used to cache a final grounded legal answer, PII, or an
    auth/entitlement decision. A bounded TTL means a fabricated id can only ever
    cache as a NEGATIVE ("0"); it can never be promoted to valid by the cache.

Configuration (env):
  REDIS_URL                redis connection url; empty/unset -> cache disabled
  CACHE_ENABLED            "false" to hard-disable (default enabled)
  CACHE_SOCKET_TIMEOUT_MS  per-op socket timeout, default 50ms (fail fast)
  CACHE_DEFAULT_TTL_S      default value TTL, default 300s
"""
from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger("lawapp.cache")

_client = None
_client_lock = threading.Lock()
_init_done = False


def _enabled() -> bool:
    if os.getenv("CACHE_ENABLED", "true").strip().lower() in {"0", "false", "no"}:
        return False
    return bool(os.getenv("REDIS_URL", "").strip())


def _socket_timeout_s() -> float:
    try:
        return max(1, int(os.getenv("CACHE_SOCKET_TIMEOUT_MS", "50"))) / 1000.0
    except ValueError:
        return 0.05


def default_ttl_s() -> int:
    try:
        return max(1, int(os.getenv("CACHE_DEFAULT_TTL_S", "300")))
    except ValueError:
        return 300


def get_client():
    """Lazily build a singleton Redis client, or return None if unavailable.

    Short socket timeouts ensure a degraded Redis cannot stall the request path.
    Any construction failure disables the cache for the rest of the process life
    (re-checked only if a later call resets _init_done).
    """
    global _client, _init_done
    if _init_done:
        return _client
    with _client_lock:
        if _init_done:
            return _client
        _init_done = True
        if not _enabled():
            _client = None
            return None
        try:
            import redis  # redis-py (installed)

            t = _socket_timeout_s()
            _client = redis.Redis.from_url(
                os.environ["REDIS_URL"],
                socket_connect_timeout=t,
                socket_timeout=t,
                retry_on_timeout=False,
                health_check_interval=30,
                decode_responses=True,
            )
        except Exception as exc:  # noqa: BLE001 - degrade on ANY failure
            logger.warning("cache disabled (client init failed): %s", exc)
            _client = None
    return _client


def cache_get_bool(key: str):
    """Return True/False for a cached boolean, or None on miss / cache-down."""
    c = get_client()
    if c is None:
        return None
    try:
        v = c.get(key)
    except Exception as exc:  # noqa: BLE001
        logger.debug("cache get degraded (%s): %s", key, exc)
        return None
    if v is None:
        return None
    return v == "1"


def cache_set_bool(key: str, value: bool, ttl_s: int | None = None) -> None:
    """Best-effort set of a boolean with TTL. Never raises."""
    c = get_client()
    if c is None:
        return
    try:
        c.set(key, "1" if value else "0", ex=ttl_s or default_ttl_s())
    except Exception as exc:  # noqa: BLE001
        logger.debug("cache set degraded (%s): %s", key, exc)


def reset_for_tests(client=None) -> None:
    """Inject a fake client (or None) and re-arm init — TEST USE ONLY."""
    global _client, _init_done
    with _client_lock:
        _client = client
        _init_done = True
