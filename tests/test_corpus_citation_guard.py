"""Corpus-citation enforcement proof (LLM Fabric directive).

An LLM output is accepted ONLY if it cites a real corpus_chunks UUID; otherwise the
orchestrator regenerates (bounded) then falls back to a deterministic guide.
"""
from __future__ import annotations

import pytest

from backend.core.agentic.corpus_citation_guard import (
    enforce_or_regenerate, extract_uuids, response_has_valid_corpus_citation,
    valid_corpus_uuids,
)

FAKE_UUID = "00000000-0000-0000-0000-000000000000"


def _conn():
    from ingestion.db import get_connection
    return get_connection()


def _db_up():
    try:
        c = _conn(); c.close(); return True
    except Exception:
        return False


def _a_real_corpus_uuid():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id::text FROM corpus_chunks LIMIT 1")
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


db_required = pytest.mark.skipif(not _db_up(), reason="UNPROVEN  -  DB not accessible")


def test_extract_uuids_pure():
    txt = f"see chunk {FAKE_UUID} and again {FAKE_UUID.upper()}"
    assert extract_uuids(txt) == [FAKE_UUID]          # de-duped, lowercased
    assert extract_uuids("no uuids here") == []


@db_required
def test_fake_uuid_is_not_a_valid_citation():
    assert valid_corpus_uuids([FAKE_UUID]) == set()
    assert response_has_valid_corpus_citation(f"Authority: {FAKE_UUID}") is False


@db_required
def test_real_uuid_is_a_valid_citation():
    real = _a_real_corpus_uuid()
    if not real:
        pytest.skip("no corpus_chunks rows")
    assert real.lower() in valid_corpus_uuids([real])
    assert response_has_valid_corpus_citation(f"Per corpus row {real}, ...") is True


@db_required
def test_enforce_accepts_response_with_real_uuid():
    real = _a_real_corpus_uuid()
    if not real:
        pytest.skip("no corpus_chunks rows")
    out = enforce_or_regenerate(reason_fn=lambda attempt: f"Analysis cites {real}.")
    assert out["status"] == "accepted"
    assert real.lower() in out["valid_uuids"]
    assert out["attempts"] == 1


@db_required
def test_enforce_rejects_uncited_and_falls_back():
    calls = {"n": 0}

    def _no_uuid(attempt):
        calls["n"] += 1
        return "This answer cites no corpus UUID at all."

    out = enforce_or_regenerate(
        reason_fn=_no_uuid,
        fallback_fn=lambda: {"deterministic": True, "guide": "see rules table"},
    )
    assert out["status"] == "fallback"
    assert out["deterministic"] is True
    assert calls["n"] == 3            # initial + 2 regenerations, all rejected
