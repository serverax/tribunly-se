"""Hot-path cache for the rules-engine  -  built for 100k concurrent.

The deterministic legal values (statutory time limits, caps, qualifying periods)
live in the `rules` table and change only when legislation changes  -  effectively
never within a request window. Hitting Postgres on every rule evaluation is the
scaling bottleneck (a fresh psycopg connection per call, no pool  -  see
ingestion/db.py). This module removes the DB from the hot path:

  * read-through TTL cache keyed by (claim_type, jurisdiction, edt)  -  a cache hit
    returns the rules with ZERO database work, in microseconds.
  * single-flight on miss: the per-key compute runs under the lock, so a cold key
    hit by N concurrent requests triggers exactly ONE database read, not N. This is
    what prevents a connection-storm / lock contention at scale.
  * pure per-process state (a plain dict). Each pod owns its cache, shares nothing,
    and is therefore horizontally scalable  -  add pods to add capacity. No cross-pod
    coordination, no sticky sessions, no shared mutable state.

The deadline arithmetic is a pure function of (edt, time_limit_months, ec dates),
so it is memoized with an LRU  -  the second identical calculation is free.

Tuning via env: RULES_CACHE_TTL_SECONDS (default 300), RULES_CACHE_MAXSIZE (10000),
DEADLINE_MEMO_MAXSIZE (50000). All are read once at import.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import date
from functools import lru_cache
from typing import Callable

_TTL_SECONDS = int(os.getenv("RULES_CACHE_TTL_SECONDS", "300"))
_MAXSIZE = int(os.getenv("RULES_CACHE_MAXSIZE", "10000"))
_DEADLINE_MEMO_MAXSIZE = int(os.getenv("DEADLINE_MEMO_MAXSIZE", "50000"))


class _Metrics:
    __slots__ = ("hits", "misses")

    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0

    def as_dict(self) -> dict:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 4) if total else 0.0,
            "size": None,  # filled by caller
        }


class TTLCache:
    """Thread-safe TTL cache with single-flight read-through.

    On a hit within TTL the value is returned with no recompute. On a miss the
    loader runs under the lock (single-flight) so concurrent callers for the same
    key cause exactly one load. Eviction is best-effort: when full, the oldest
    entry by insertion order is dropped (FIFO  -  adequate for a small rules set).
    """

    def __init__(self, ttl_seconds: int, maxsize: int) -> None:
        self._ttl = ttl_seconds
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self._store: dict[tuple, tuple[float, object]] = {}
        self.metrics = _Metrics()

    def _now(self) -> float:
        return time.monotonic()

    def get_or_load(self, key: tuple, loader: Callable[[], object]) -> tuple[object, bool]:
        """Return (value, was_hit). Loader is only called on miss, under the lock."""
        now = self._now()
        with self._lock:
            entry = self._store.get(key)
            if entry is not None and (now - entry[0]) < self._ttl:
                self.metrics.hits += 1
                return entry[1], True
            # miss or expired  -  load under lock (single-flight)
            value = loader()
            if len(self._store) >= self._maxsize and key not in self._store:
                # drop oldest inserted key (FIFO)
                oldest = next(iter(self._store), None)
                if oldest is not None:
                    self._store.pop(oldest, None)
            self._store[key] = (now, value)
            self.metrics.misses += 1
            return value, False

    def stats(self) -> dict:
        with self._lock:
            d = self.metrics.as_dict()
            d["size"] = len(self._store)
            d["ttl_seconds"] = self._ttl
            d["maxsize"] = self._maxsize
        return d

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self.metrics.hits = 0
            self.metrics.misses = 0


_rules_cache = TTLCache(_TTL_SECONDS, _MAXSIZE)


def cached_retrieve_rules(claim_type: str, jurisdiction: str, edt: date) -> tuple[list[dict], bool]:
    """Read-through cached wrapper over backend.core.retrieve.retrieve_rules.

    Returns (rules, cache_hit). The DB is touched only on a cold/expired key.
    Imported lazily so this module has no import-time DB dependency.
    """
    key = (claim_type, jurisdiction, edt.isoformat())

    def _load() -> list[dict]:
        from backend.core.retrieve import retrieve_rules
        return retrieve_rules(claim_type, jurisdiction, edt)

    return _rules_cache.get_or_load(key, _load)


@lru_cache(maxsize=_DEADLINE_MEMO_MAXSIZE)
def _memo_limitation_date(edt_iso: str, tl_months: int,
                          ec_a_iso: str | None, ec_b_iso: str | None) -> dict:
    from backend.domains.employment.deadline import compute_limitation_date
    ec_a = date.fromisoformat(ec_a_iso) if ec_a_iso else None
    ec_b = date.fromisoformat(ec_b_iso) if ec_b_iso else None
    return compute_limitation_date(date.fromisoformat(edt_iso), tl_months, ec_a, ec_b)


def memoized_limitation_date(edt: date, tl_months: int,
                             ec_a: date | None, ec_b: date | None) -> dict:
    """Memoized deadline arithmetic. Pure function → identical inputs are free.
    Returns a fresh copy so callers cannot mutate the shared cached dict."""
    cached = _memo_limitation_date(
        edt.isoformat(), tl_months,
        ec_a.isoformat() if ec_a else None,
        ec_b.isoformat() if ec_b else None,
    )
    return dict(cached)


def cache_stats() -> dict:
    """Observability snapshot  -  rules cache + deadline memo, for /metrics-style use."""
    memo = _memo_limitation_date.cache_info()
    return {
        "rules_cache": _rules_cache.stats(),
        "deadline_memo": {
            "hits": memo.hits, "misses": memo.misses,
            "size": memo.currsize, "maxsize": memo.maxsize,
        },
    }


def reset_caches() -> None:
    """Test helper  -  clear all cached state."""
    _rules_cache.clear()
    _memo_limitation_date.cache_clear()
