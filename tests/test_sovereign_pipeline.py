"""Sovereign pipeline acceptance proof (order Test Cases A/B/C), via TestClient(app).

A: POST /api/v1/lawapp/ingest -> 202 + user_legal_profiles row (deterministic extraction).
B: POST /api/v1/lawapp/query  -> SSE thinking-states + citation-guarded answer.
C: invalid (fake-UUID) answer -> fail-closed ESCALATED, never streamed to the user.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def _conn():
    from ingestion.db import get_connection
    return get_connection()


def _db_up():
    try:
        c = _conn(); c.close(); return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_up(), reason="UNPROVEN  -  DB not accessible")

CHEF = ("I have been a chef at a restaurant in Bradford since January 2025 on a "
        "zero hours contract. Yesterday my manager told me not to come back because "
        "business is slow.")


def test_a_ingest_writes_extracted_profile_row():
    r = client.post("/api/v1/lawapp/ingest", json={"raw_text": CHEF})
    assert r.status_code == 202, r.text
    assert "X-Trace-ID" in r.headers
    body = r.json()
    uid = body["user_id"]
    ex = body["extracted"]
    assert ex["employment_type"] == "zero_hours"
    assert ex["recent_incident"] == "short_notice_cancellation"
    assert ex["tenure_months"] > 0
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT employment_type, recent_incident, tenure_months "
                        "FROM user_legal_profiles WHERE user_id=%s::uuid", (uid,))
            row = cur.fetchone()
            assert row is not None, "no user_legal_profiles row written"
            assert row[0] == "zero_hours"
            assert row[1] == "short_notice_cancellation"
            assert row[2] > 0
            cur.execute("DELETE FROM user_legal_profiles WHERE user_id=%s::uuid", (uid,))
        conn.commit()
    finally:
        conn.close()


def test_b_query_streams_stages_and_is_citation_guarded():
    r = client.post("/api/v1/lawapp/query",
                    json={"raw_text": "Am I entitled to a statutory notice period if I am dismissed after 3 months?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    body = r.text
    for stage in ("STAGE:CLASSIFYING_INTENT", "STAGE:HYBRID_DB_RETRIEVAL",
                  "STAGE:LOCAL_INFERENCE_GENERATION", "STAGE:WASM_GUARD_VALIDATION"):
        assert stage in body, f"missing thinking-state {stage}"
    assert "[DONE]" in body
    assert "STAGE:ESCALATED" not in body
    assert ("Citation:" in body) or ("cannot advise" in body.lower())


def test_c_fake_citation_fails_closed(monkeypatch):
    """A legal-claim answer citing a non-existent corpus UUID must be WITHHELD."""
    fake = ("You are entitled to 50 weeks of notice (Citation: "
            "00000000-0000-0000-0000-000000000000).", ["00000000-0000-0000-0000-000000000000"])
    monkeypatch.setattr("backend.core.sovereign.answer.build_answer", lambda *a, **k: fake)
    r = client.post("/api/v1/lawapp/query", json={"raw_text": "Can I be fired without notice?"})
    assert r.status_code == 200
    body = r.text
    assert "STAGE:ESCALATED" in body, "fake-cited answer was not blocked"
    assert "[BLOCKED]" in body
    assert "STAGE:COMPLETED" not in body
    assert "entitled to 50 weeks" not in body
