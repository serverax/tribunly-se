"""
Phase 3A  -  MVP client integration tests.

Validates the FastAPI app serves the static client and wires the intake
submission correctly to the existing assessment pipeline.

Tests:
  1. Landing page served at GET /  -  contains legal notice text
  2. Intake page served at GET /pages/intake.html
  3. Assessment page served at GET /pages/assessment.html
  4. Legal notice present on all three pages
  5. POST /assess  -  intake submit path returns structured assessment
  6. POST /assess  -  out-of-scope returns not_supported (OOS rejection)
  7. POST /assess  -  citations present in response for viable claim
  8. POST /assess  -  key_weaknesses shown for weak case

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase3a_flows.py -v -s
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.models import StubReasoningModel

client = TestClient(app, raise_server_exceptions=True)

_FULL_FACTS = {
    "edt": "2026-04-01",
    "service_start_date": "2023-04-01",
    "reason_for_dismissal": "conduct",
    "was_procedure_followed": False,
    "weekly_pay": 600,
    "jurisdiction": "EW",
}


# ── 1. Landing page served ─────────────────────────────────────────────────────

def test_landing_page_served():
    """GET / must return 200 with HTML content."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


# ── 2. Intake page served ──────────────────────────────────────────────────────

def test_intake_page_served():
    """GET /pages/intake.html must return 200."""
    resp = client.get("/pages/intake.html")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


# ── 3. Assessment page served ──────────────────────────────────────────────────

def test_assessment_page_served():
    """GET /pages/assessment.html must return 200."""
    resp = client.get("/pages/assessment.html")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


# ── 4. Legal notice present on each page ──────────────────────────────────────

def test_legal_notice_on_landing_page():
    """Landing page must carry the 'Not a law firm' legal notice."""
    body = client.get("/").text
    assert "Not a law firm" in body, "Legal notice missing from landing page"
    assert "Not legal advice" in body, "Legal advice disclaimer missing"


def test_legal_notice_on_intake_page():
    """Intake page must carry the 'Not a law firm' legal notice."""
    body = client.get("/pages/intake.html").text
    assert "Not a law firm" in body


def test_legal_notice_on_assessment_page():
    """Assessment page must carry the 'Not a law firm' legal notice."""
    body = client.get("/pages/assessment.html").text
    assert "Not a law firm" in body


# ── 5. Intake submit → structured assessment ──────────────────────────────────

def test_intake_submit_returns_assessment():
    """POST /assess with full facts returns a structured assessment dict."""
    resp = client.post("/assess", json={
        "query": "I was unfairly dismissed",
        "facts": _FULL_FACTS,
        "jurisdiction": "EW",
        "use_model": False,     # StubReasoningModel  -  no external call
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    # Minimal structure regardless of stub path taken
    assert "boundary_log" in data, "boundary_log must always be returned"


# ── 6. OOS rejection ──────────────────────────────────────────────────────────

def test_oos_rejection():
    """Out-of-scope query must return not_supported, no assessment fields."""
    resp = client.post("/assess", json={
        "query": "I want to sue my landlord for deposit",
        "facts": {},
        "jurisdiction": "EW",
        "use_model": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "not_supported"
    for key in ("has_viable_claim", "strength", "citations"):
        assert key not in data, f"Assessment field '{key}' must not appear for OOS"


# ── 7. Citations present for viable claim ────────────────────────────────────

def test_citations_present_in_assessment():
    """A viable-claim assessment must include at least one citation."""
    resp = client.post("/assess", json={
        "query": "I was unfairly dismissed after 3 years",
        "facts": _FULL_FACTS,
        "jurisdiction": "EW",
        "use_model": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    if data.get("status") == "ok":
        cites = data.get("citations", [])
        assert len(cites) > 0, "Viable assessment must include at least one citation"
        for c in cites:
            assert c.get("cite"), f"Citation missing 'cite' field: {c}"


# ── 8. Weak case shows key_weaknesses ────────────────────────────────────────

def test_weak_case_shows_weaknesses():
    """Assessment with low qualifying service must expose key_weaknesses."""
    short_service_facts = {
        "edt": "2026-02-15",
        "service_start_date": "2025-01-01",   # ~13 months  -  below 2yr QP
        "reason_for_dismissal": "conduct",
        "was_procedure_followed": True,
        "weekly_pay": 400,
        "jurisdiction": "EW",
    }
    resp = client.post("/assess", json={
        "query": "I was dismissed after 13 months",
        "facts": short_service_facts,
        "jurisdiction": "EW",
        "use_model": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    if data.get("status") == "ok":
        weaknesses = data.get("key_weaknesses", [])
        assert len(weaknesses) > 0, "Weak case must show key_weaknesses"
