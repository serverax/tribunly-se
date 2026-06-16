"""Scale-readiness proof for the 100k-concurrent requirement.

Proves the building blocks that let the citation/search hot path stay <100ms and
degrade gracefully under extreme load:

  - DB connection POOL: get_connection() reuses warm connections (no
    connect-per-request) and falls back to a direct connect if the pool breaks.
  - Redis CACHE: per-UUID existence cache; a hit answers WITHOUT touching the DB;
    a fabricated UUID can only ever cache as NEGATIVE (fail-closed preserved).
  - GRACEFUL DEGRADATION: when Redis is down every lookup falls through to the
    authoritative DB  -  the request never crashes.
  - CIRCUIT BREAKER: external-dependency failures trip the breaker so calls fail
    fast instead of piling up; it recovers via HALF_OPEN.

Cache/breaker tests use an injected in-memory fake (and a deterministic fake
clock)  -  no live Redis or sleeping required. DB-pool tests use the live DB and
skip if it is unreachable (they are never faked).
"""
from __future__ import annotations

import pytest

from backend.core import cache
from backend.core.agentic import corpus_citation_guard as cg
from backend.core.circuit_breaker import CircuitBreaker, CircuitOpenError


# ── fakes ────────────────────────────────────────────────────────────────────

class _FakeRedis:
    """Minimal in-memory redis stand-in (get/set with ex=)."""
    def __init__(self):
        self.store: dict[str, str] = {}
        self.get_calls = 0
        self.set_calls = 0

    def get(self, k):
        self.get_calls += 1
        return self.store.get(k)

    def set(self, k, v, ex=None):
        self.set_calls += 1
        self.store[k] = v


class _DownRedis:
    """A redis client that raises on every op (simulates Redis down/slow)."""
    def get(self, k):
        raise ConnectionError("redis down")

    def set(self, k, v, ex=None):
        raise ConnectionError("redis down")


class _FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture(autouse=True)
def _reset_cache():
    yield
    cache.reset_for_tests(None)  # restore "no cache" after each test


def _boom_conn():
    raise AssertionError("DB was hit but a cache hit should have avoided it")


# ── DB connection pool (live DB; skips if unreachable) ───────────────────────

def test_db_pool_reuses_connections():
    import ingestion.db as db

    db.close_pool()
    try:
        c1 = db.get_connection()
    except Exception:
        pytest.skip("DB unreachable  -  pool reuse cannot be proven on mock data")
    inner1 = id(getattr(c1, "_conn", c1))
    c1.close()                      # returns to pool (does NOT tear down socket)
    c2 = db.get_connection()
    inner2 = id(getattr(c2, "_conn", c2))
    c2.close()
    assert db._get_pool() is not None, "pool should be active by default"
    assert inner1 == inner2, "pool did not reuse the warm connection"


def test_db_pool_bounded_by_env(monkeypatch):
    import ingestion.db as db
    monkeypatch.setenv("DB_POOL_MAX", "4")
    db.close_pool()
    pool = db._get_pool()
    if pool is None:
        pytest.skip("DB unreachable  -  cannot build pool")
    assert pool.maxconn == 4
    db.close_pool()


# ── Redis cache: hit avoids DB, negative skips DB ────────────────────────────

def test_cache_hit_avoids_database():
    fake = _FakeRedis()
    uid = "11111111-1111-1111-1111-111111111111"
    fake.store[cg._CACHE_KEY_PREFIX + uid] = "1"   # pre-cached positive
    cache.reset_for_tests(fake)
    # get_conn raises if touched  -  proves the DB was NOT consulted on a hit.
    good = cg.cached_valid_corpus_uuids([uid], get_conn=_boom_conn)
    assert good == {uid}
    assert fake.get_calls == 1


def test_cache_negative_skips_database():
    fake = _FakeRedis()
    uid = "22222222-2222-2222-2222-222222222222"
    fake.store[cg._CACHE_KEY_PREFIX + uid] = "0"   # known-absent
    cache.reset_for_tests(fake)
    good = cg.cached_valid_corpus_uuids([uid], get_conn=_boom_conn)
    assert good == set()           # cached negative, DB never hit


def test_cache_miss_resolves_db_and_writes_back(monkeypatch):
    fake = _FakeRedis()
    cache.reset_for_tests(fake)
    uid = "33333333-3333-3333-3333-333333333333"
    # DB says it IS present; cache is cold so the DB must be consulted once.
    monkeypatch.setattr(cg, "valid_corpus_uuids", lambda u, get_conn=None: {uid})
    good = cg.cached_valid_corpus_uuids([uid])
    assert good == {uid}
    assert fake.store[cg._CACHE_KEY_PREFIX + uid] == "1"   # written back


# ── graceful degradation: Redis down -> authoritative DB still answers ───────

def test_cache_down_degrades_to_database(monkeypatch):
    cache.reset_for_tests(_DownRedis())   # every cache op raises -> treated as miss
    uid = "44444444-4444-4444-4444-444444444444"
    monkeypatch.setattr(cg, "valid_corpus_uuids", lambda u, get_conn=None: {uid})
    good = cg.cached_valid_corpus_uuids([uid])
    assert good == {uid}, "must fall through to DB when Redis is down (no crash)"


def test_cache_disabled_when_no_redis_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    cache.reset_for_tests(None)
    cache._init_done = False           # force re-evaluation
    assert cache.get_client() is None  # disabled, never raises
    assert cache.cache_get_bool("x") is None
    cache.cache_set_bool("x", True)    # no-op, must not raise


# ── SECURITY: cache can never make a fabricated UUID valid ───────────────────

def test_cache_never_promotes_fake_uuid(monkeypatch):
    fake = _FakeRedis()
    cache.reset_for_tests(fake)
    bad = "00000000-0000-0000-0000-000000000000"
    monkeypatch.setattr(cg, "valid_corpus_uuids", lambda u, get_conn=None: set())  # DB: absent
    good = cg.cached_valid_corpus_uuids([bad])
    assert good == set(), "fail-OPEN: cache promoted a fabricated UUID"
    assert fake.store[cg._CACHE_KEY_PREFIX + bad] == "0"   # only ever cached negative


def test_mixed_real_and_fake_only_real_valid(monkeypatch):
    fake = _FakeRedis()
    cache.reset_for_tests(fake)
    real = "55555555-5555-5555-5555-555555555555"
    bad = "00000000-0000-0000-0000-000000000000"
    monkeypatch.setattr(cg, "valid_corpus_uuids", lambda u, get_conn=None: {real})
    good = cg.cached_valid_corpus_uuids([real, bad])
    assert good == {real}     # the fabricated id is never included


# ── circuit breaker (deterministic fake clock) ───────────────────────────────

def test_breaker_opens_after_fail_max_then_fails_fast():
    clk = _FakeClock(100.0)
    br = CircuitBreaker("t", fail_max=3, reset_timeout_s=10, clock=clk)

    def boom():
        raise RuntimeError("dep down")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            br.call(boom)
    assert br.state == "open"
    # Now fails FAST without invoking the function.
    calls = {"n": 0}

    def counted():
        calls["n"] += 1
        return "ok"

    with pytest.raises(CircuitOpenError):
        br.call(counted)
    assert calls["n"] == 0, "open breaker must not invoke the dependency"


def test_breaker_half_open_recovers_on_success():
    clk = _FakeClock(0.0)
    br = CircuitBreaker("t", fail_max=1, reset_timeout_s=5, clock=clk)
    with pytest.raises(RuntimeError):
        br.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert br.state == "open"
    clk.t = 5.0                       # reset window elapsed -> HALF_OPEN
    assert br.state == "half_open"
    assert br.call(lambda: "ok") == "ok"
    assert br.state == "closed"       # success closes it


def test_breaker_half_open_failure_reopens():
    clk = _FakeClock(0.0)
    br = CircuitBreaker("t", fail_max=1, reset_timeout_s=5, clock=clk)
    with pytest.raises(RuntimeError):
        br.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    clk.t = 5.0
    assert br.state == "half_open"
    with pytest.raises(RuntimeError):
        br.call(lambda: (_ for _ in ()).throw(RuntimeError("again")))
    assert br.state == "open"         # half-open failure re-opens immediately
