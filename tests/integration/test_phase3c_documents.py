"""
Phase 3C — Document generation integration tests.

Validates:
  1.  Particulars of Claim endpoint returns 200 with content
  2.  Schedule of Loss endpoint returns 200 with content
  3.  Generated PoC includes user intake facts (EDT, reason, service dates)
  4.  Generated SoL includes value range
  5.  Both documents include claim type "unfair dismissal"
  6.  Both documents include the legal boundary notice
  7.  Documents do not include outcome guarantees ("you will win", "guaranteed")
  8.  Documents do not imply lawapp files or represents ("we will file", etc.)
  9.  Unsupported document type → 422 (Pydantic Literal validation)
 10.  Missing / empty facts handled gracefully (no 500)
 11.  safety_check() function itself tested: blocks bad phrases
 12.  safety_check() passes for clean content
 13.  Phase 3B deadline tests still pass (regression)
 14.  Static routes still serve (Phase 3A regression)
 15.  /documents/generate appears in live Docker (health check)

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase3c_documents.py -v -s
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.documents import safety_check, LEGAL_BOUNDARY_NOTICE
from tests.integration.payment_helpers import mark_case_paid

from tests.integration.auth_helpers import TEST_USER_ID, mock_auth_headers

client = TestClient(app, raise_server_exceptions=True)

_LEGACY_AUTH = mock_auth_headers(TEST_USER_ID)

# ── Fixtures ──────────────────────────────────────────────────────────────────

_ASSESSMENT = {
    "status": "ok",
    "claim_type": "unfair_dismissal",
    "has_viable_claim": "yes",
    "strength": "medium",
    "reasoning_summary": (
        "The claimant has 3 years of service and was dismissed for conduct "
        "without a proper disciplinary procedure."
    ),
    "key_weaknesses": [
        "Employer may argue the conduct was serious enough to justify summary dismissal.",
        "Claimant did not formally appeal the decision.",
    ],
    "employer_arguments": [
        "Band of reasonable responses: the employer may contend dismissal fell within range.",
    ],
    "deadline_info": {
        "limitation_date": "2026-06-30",
        "source": "rules",
        "authority": "ERA 1996 s.111(2)",
        "ec_applied": False,
        "base_limit": "2026-06-30",
    },
    "value_range": {
        "low": 1800,
        "high": 31200,
        "currency": "GBP",
        "basis": "Basic award estimate + compensatory loss estimate from statutory rules.",
    },
    "recommended_next_step": "prepare_documents",
    "citations": [
        {"cite": "ERA 1996 s.94", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/94"},
        {"cite": "ERA 1996 s.111(2)", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/111"},
    ],
    "grounding_score": 0.85,
    "confidence_score": 0.75,
    "insufficient_grounding": False,
    "boundary_log": {
        "fields_passed": ["edt", "service_start_date", "reason_for_dismissal"],
        "fields_stripped": [],
        "pii_in_output": [],
    },
}

_FACTS = {
    "edt": "2026-04-01",
    "service_start_date": "2023-04-01",
    "reason_for_dismissal": "conduct",
    "was_procedure_followed": False,
    "weekly_pay": 600,
    "jurisdiction": "EW",
}

_POC_REQUEST = {"document_type": "particulars_of_claim", "assessment": _ASSESSMENT, "facts": _FACTS}
_SOL_REQUEST = {"document_type": "schedule_of_loss",     "assessment": _ASSESSMENT, "facts": _FACTS}
_PAID_CASE_ID: str | None = None


@pytest.fixture(scope="module", autouse=True)
def paid_case_for_document_generation():
    """Full-document assertions use DB-backed paid state, never raw tokens."""
    global _PAID_CASE_ID
    resp = client.post("/cases", headers=_LEGACY_AUTH, json={
        "claim_type": "unfair_dismissal",
        "jurisdiction": "EW",
        "assessment": _ASSESSMENT,
        "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
    })
    assert resp.status_code == 201
    _PAID_CASE_ID = resp.json()["case_id"]
    mark_case_paid(_PAID_CASE_ID)
    _POC_REQUEST["case_id"] = _PAID_CASE_ID
    _SOL_REQUEST["case_id"] = _PAID_CASE_ID
    yield


# ── 1. Particulars of Claim endpoint ─────────────────────────────────────────

def test_particulars_of_claim_endpoint_returns_200():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_REQUEST)
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_type"] == "particulars_of_claim"
    assert isinstance(data["content"], str)
    assert len(data["content"]) > 100
    assert data["safety_check"]["passed"] is True
    assert data["generation_method"] == "template"
    assert data["disclaimer_included"] is True


# ── 2. Schedule of Loss endpoint ──────────────────────────────────────────────

def test_schedule_of_loss_endpoint_returns_200():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_SOL_REQUEST)
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_type"] == "schedule_of_loss"
    assert isinstance(data["content"], str)
    assert len(data["content"]) > 100
    assert data["safety_check"]["passed"] is True


# ── 3. PoC includes user facts ────────────────────────────────────────────────

def test_particulars_includes_edt():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_REQUEST)
    content = resp.json()["content"]
    # EDT formatted as '1 April 2026'
    assert "April 2026" in content, f"EDT date not found in PoC content"


def test_particulars_includes_reason_for_dismissal():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_REQUEST)
    content = resp.json()["content"].lower()
    assert "conduct" in content, "reason_for_dismissal not found in PoC content"


def test_particulars_includes_service_dates():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_REQUEST)
    content = resp.json()["content"]
    assert "2023" in content, "Service start year not found in PoC"
    assert "2026" in content, "EDT year not found in PoC"


# ── 4. SoL includes value range ────────────────────────────────────────────────

def test_schedule_includes_value_range_figures():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_SOL_REQUEST)
    content = resp.json()["content"]
    assert "1,800" in content or "1800" in content, "Low estimate not found in SoL"
    assert "31,200" in content or "31200" in content, "High estimate not found in SoL"


def test_schedule_includes_value_range_basis():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_SOL_REQUEST)
    content = resp.json()["content"]
    assert "statutory rules" in content.lower() or "ERA 1996" in content


# ── 5. Claim type present ──────────────────────────────────────────────────────

def test_poc_includes_unfair_dismissal_claim_type():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_REQUEST)
    content = resp.json()["content"].lower()
    assert "unfair dismissal" in content


def test_sol_includes_unfair_dismissal_claim_type():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_SOL_REQUEST)
    content = resp.json()["content"].lower()
    assert "unfair dismissal" in content


# ── 6. Legal boundary notice present ─────────────────────────────────────────

def test_poc_includes_legal_boundary_notice():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_REQUEST)
    content = resp.json()["content"]
    assert "NOT legal advice" in content, "Legal boundary notice missing from PoC"
    assert "not a solicitor or law firm" in content.lower()
    assert "does not file" in content.lower() or "does not file" in content


def test_sol_includes_legal_boundary_notice():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_SOL_REQUEST)
    content = resp.json()["content"]
    assert "NOT legal advice" in content
    assert "not a solicitor or law firm" in content.lower()


def test_documents_include_self_help_draft_label():
    for req in [_POC_REQUEST, _SOL_REQUEST]:
        resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=req)
        content = resp.json()["content"]
        assert "SELF-HELP DRAFT" in content or "self-help draft" in content.lower(), \
            f"Self-help draft label missing for {req['document_type']}"


# ── 7. No outcome guarantees ──────────────────────────────────────────────────

def test_poc_no_guarantee_language():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_REQUEST)
    content = resp.json()["content"].lower()
    assert "you will win" not in content
    assert "guaranteed to win" not in content
    assert "certain to succeed" not in content
    assert resp.json()["safety_check"]["passed"] is True


def test_sol_no_guarantee_language():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_SOL_REQUEST)
    content = resp.json()["content"].lower()
    assert "you will win" not in content
    assert "guaranteed to win" not in content
    assert resp.json()["safety_check"]["passed"] is True


# ── 8. No filing / representation language ────────────────────────────────────

def test_poc_no_filing_language():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_REQUEST)
    content = resp.json()["content"].lower()
    assert "we will file" not in content
    assert "we will submit" not in content
    assert "we will represent you" not in content


def test_sol_no_representation_language():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_SOL_REQUEST)
    content = resp.json()["content"].lower()
    assert "we will represent you" not in content
    assert "as your solicitor" not in content


# ── 9. Unsupported document type ──────────────────────────────────────────────

def test_unsupported_document_type_returns_422():
    """Pydantic Literal validation rejects unknown document_type with 422."""
    # letter_before_action is now valid (Phase 5B). Use a genuinely invalid type.
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json={
        "document_type": "court_filing_invalid",
        "assessment": _ASSESSMENT,
        "facts": _FACTS,
    })
    assert resp.status_code == 422


# ── 10. Empty facts handled gracefully ────────────────────────────────────────

def test_empty_facts_does_not_crash():
    """Template must handle missing facts with placeholder text, not raise."""
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json={
        "document_type": "particulars_of_claim",
        "assessment": _ASSESSMENT,
        "facts": {},
        "case_id": _PAID_CASE_ID,
    })
    assert resp.status_code == 200
    content = resp.json()["content"]
    assert "DATE NOT PROVIDED" in content or "NOT PROVIDED" in content


# ── 11-12. safety_check() unit tests ─────────────────────────────────────────

def test_safety_check_blocks_guarantee_phrase():
    result = safety_check("You will win your case if you follow this advice.")
    assert result["passed"] is False
    assert len(result["violations"]) > 0


def test_safety_check_blocks_filing_phrase():
    result = safety_check("We will file your claim with the tribunal immediately.")
    assert result["passed"] is False


def test_safety_check_blocks_representation_phrase():
    result = safety_check("We will represent you at the hearing.")
    assert result["passed"] is False


def test_safety_check_passes_clean_content():
    clean = (
        "This is a self-help draft. It is NOT legal advice. "
        "lawapp is not a solicitor or law firm. No outcome is guaranteed."
    )
    result = safety_check(clean)
    assert result["passed"] is True
    assert result["violations"] == []


# ── 13. Phase 3B regression ───────────────────────────────────────────────────

def test_rules_api_still_works():
    """Phase 3B /rules endpoint must still return time_limit_months."""
    resp = client.get("/rules/unfair_dismissal")
    assert resp.status_code == 200
    data = resp.json()
    keys = [r["rule_key"] for r in data["rules"]]
    assert "unfair_dismissal.time_limit_months" in keys


def test_assess_endpoint_still_validates_client_deadline():
    """Phase 3B client_deadline validation must still work."""
    resp = client.post("/assess", json={
        "query": "unfair dismissal",
        "facts": {
            "edt": "2026-04-01", "service_start_date": "2023-04-01",
            "reason_for_dismissal": "conduct", "was_procedure_followed": False,
            "weekly_pay": 600, "jurisdiction": "EW",
        },
        "jurisdiction": "EW",
        "use_model": False,
        "client_deadline": "2026-01-01",   # wrong — should flag mismatch
    })
    assert resp.status_code == 200
    assert resp.json().get("deadline_mismatch") is True


# ── 14. Phase 3A static routes ────────────────────────────────────────────────

def test_static_routes_still_serve():
    for path in ["/", "/pages/intake.html", "/pages/assessment.html"]:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"


def test_health_still_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
