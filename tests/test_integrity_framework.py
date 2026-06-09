"""
Integrity Framework — adversarial "Red Team" tests for the Critic Gate.

These intentionally inject FAKE laws to prove the system halts before drafting:
  - A fake citation ('Section 999 Equality Act 2010') must be flagged by the Critic,
    logged to agent_validation_failures, and the request killed with HTTP 422 BEFORE
    Agent SEA (the drafter) runs. The document is never produced.
  - A real citation (ERA 1996 s.98, resolves to the local DB) must pass the Critic
    (it may still be payment-gated, but it is NOT a citation-integrity 422).

If the Critic ever lets a fake law through, these tests fail the build.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app
from ingestion.db import get_connection

client = TestClient(app)

FAKE_CITES = [
    {"cite": "Section 999 Equality Act 2010", "type": "legislation", "url": "https://example.invalid/s999"},
    {"cite": "Fictional Employment Act 2099 s.1", "type": "legislation", "url": "https://example.invalid/fake"},
]


def _failure_count() -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM agent_validation_failures WHERE agent_name='SEA'")
            return cur.fetchone()[0]
    finally:
        conn.close()


def test_fake_citation_is_blocked_before_drafting_and_logged():
    before = _failure_count()
    resp = client.post("/documents/generate", json={
        "document_type": "particulars_of_claim",
        "assessment": {"has_viable_claim": "yes", "citations": FAKE_CITES},
        "facts": {"edt": "2024-05-01"},
    })
    assert resp.status_code == 422, f"fake citation must be blocked, got {resp.status_code}"
    assert "integrity" in resp.json()["detail"].lower()
    assert _failure_count() > before, "Critic rejection must be logged to agent_validation_failures"


def test_real_citation_passes_the_critic():
    resp = client.post("/documents/generate", json={
        "document_type": "particulars_of_claim",
        "assessment": {"has_viable_claim": "no", "citations": [
            {"cite": "Employment Rights Act 1996 s.98", "type": "legislation",
             "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/98"},
        ]},
        "facts": {"edt": "2024-05-01"},
    })
    if resp.status_code == 422:
        assert "integrity" not in resp.json().get("detail", "").lower(), \
            "a real, resolving citation must not be flagged as a fake"


def test_every_fake_law_is_flagged_individually():
    for fake in FAKE_CITES:
        resp = client.post("/documents/generate", json={
            "document_type": "schedule_of_loss",
            "assessment": {"has_viable_claim": "yes", "citations": [fake]},
            "facts": {"edt": "2024-05-01"},
        })
        assert resp.status_code == 422, f"fake law not flagged: {fake['cite']}"
