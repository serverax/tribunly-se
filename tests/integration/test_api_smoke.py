"""
Phase 2C  -  /assess API smoke tests.

Tests the HTTP endpoint directly via httpx to confirm the JSON shape is
production-correct. These run against the live backend container.

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_api_smoke.py -v -s
"""

from __future__ import annotations

import pytest
import httpx

API_BASE = "http://backend:8000"   # compose network; backend is the service name

_UD_CASE = {
    "query": "I was dismissed after 3 years without any warning or procedure.",
    "facts": {
        "edt":                    "2026-04-01",
        "service_start_date":     "2023-04-01",
        "reason_for_dismissal":   "conduct",
        "was_procedure_followed": False,
        "weekly_pay":             600,
        "jurisdiction":           "EW",
    },
    "jurisdiction": "EW",
    "use_model":    False,   # stub mode for smoke test repeatability
}

_OOS_CASE = {
    "query": "My landlord is not fixing the heating and wants to evict me.",
    "facts": {},
    "jurisdiction": "EW",
    "use_model":    False,
}

# Required top-level keys in every /assess response
_REQUIRED_BASE_KEYS = {"status", "in_scope", "boundary_log", "governance_result"}
# Required keys in a successful (status=ok) assessment
_REQUIRED_OK_KEYS   = {
    "claim_type", "jurisdiction", "has_viable_claim", "strength",
    "reasoning_summary", "value_range", "key_weaknesses", "deadline",
    "recommended_next_step", "citations", "grounding_score",
    "confidence_score", "insufficient_grounding",
}


@pytest.fixture(scope="module")
def client():
    """
    Live-stack fixture. Skips the entire module if the backend service is not
    reachable (e.g. when running the ingestion container in isolation without
    the backend service up). This prevents a transient ConnectError from
    appearing as a test failure in the regression suite.
    """
    c = httpx.Client(base_url=API_BASE, timeout=10)
    try:
        c.get("/health")
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        c.close()
        pytest.skip(f"Backend not reachable at {API_BASE}  -  skipping live-stack smoke tests ({exc})")
    yield c
    c.close()


# ── Health check (prerequisite) ───────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["db"] == "connected"


# ── In-scope unfair dismissal case ────────────────────────────────────────────

def test_assess_ud_returns_correct_shape(client):
    r = client.post("/assess", json=_UD_CASE)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
    data = r.json()

    print(f"\n/assess response status: {data.get('status')}")
    print(f"in_scope: {data.get('in_scope')}")
    print(f"governance_result: {data.get('governance_result')}")
    if data.get("status") == "ok":
        print(f"has_viable_claim: {data.get('has_viable_claim')}")
        print(f"strength: {data.get('strength')}")
        print(f"deadline: {data.get('deadline')}")
        print(f"citations ({len(data.get('citations', []))}): "
              f"{[c['cite'] for c in data.get('citations', [])][:3]}")

    # Base keys must always be present
    for key in _REQUIRED_BASE_KEYS:
        assert key in data, f"Missing required key: {key}"

    assert data["in_scope"] is True
    assert "boundary_log" in data
    assert data["boundary_log"]["pii_in_output"] == []

    # If passed governance, full assessment keys must be present
    if data["status"] == "ok":
        for key in _REQUIRED_OK_KEYS:
            assert key in data, f"Missing assessment key: {key}"
        assert data["claim_type"] == "unfair_dismissal"
        assert data["jurisdiction"] == "EW"
        assert data["deadline"]["source"] == "rules"
        assert data["has_viable_claim"] in ("yes", "no", "uncertain")
        assert data["strength"] in ("low", "medium", "high", "uncertain")
        assert isinstance(data["key_weaknesses"], list)
        assert isinstance(data["citations"], list)
        assert isinstance(data["grounding_score"], float)
        assert isinstance(data["confidence_score"], float)

    # Governance result must always be present
    assert "passes" in data["governance_result"]


def test_assess_ud_deadline_is_rule_backed(client):
    r = client.post("/assess", json=_UD_CASE)
    data = r.json()
    dl = data.get("deadline")
    if dl:
        assert dl["source"] == "rules", f"deadline.source must be 'rules', got: {dl['source']}"


def test_assess_ud_no_pii_in_boundary(client):
    """PII keys must not appear in boundary_log fields_passed."""
    pii_case = {**_UD_CASE, "facts": {
        **_UD_CASE["facts"],
        "claimant_name": "Test User",
        "employer_name": "Test Employer Ltd",
        "email":         "test@example.com",
    }}
    r = client.post("/assess", json=pii_case)
    data = r.json()
    passed = data.get("boundary_log", {}).get("fields_passed", [])
    for key in ("claimant_name", "employer_name", "email"):
        assert key not in passed, f"PII key '{key}' was not stripped before model call"


# ── Out-of-scope case ─────────────────────────────────────────────────────────

def test_assess_oos_returns_not_supported(client):
    r = client.post("/assess", json=_OOS_CASE)
    assert r.status_code == 200
    data = r.json()

    print(f"\n/assess OOS response status: {data.get('status')}")
    assert data["status"] == "not_supported", \
        f"Expected not_supported for tenancy query, got: {data['status']}"
    assert "assessment" not in data
    assert data.get("in_scope") is not True


def test_assess_oos_no_legal_assessment_returned(client):
    r = client.post("/assess", json=_OOS_CASE)
    data = r.json()
    # Must not contain any of the assessment-specific keys
    for key in ("has_viable_claim", "strength", "citations", "value_range"):
        assert key not in data, \
            f"Out-of-scope response must not contain assessment key '{key}'"
