"""
Phase 3D  -  Paid-path, case saving, and handoff integration tests.

Validates:
  1.  Unpaid document request returns preview + payment_required=True
  2.  Paid document request returns full content + payment_required=False
  3.  Preview still contains legal boundary notice
  4.  Preview does not contain full document body (truncated)
  5.  Case save endpoint returns case_id
  6.  Saved case can be retrieved via GET /cases/{id}
  7.  Handoff lead captured for trigger_reason=seek_solicitor
  8.  Handoff lead captured for trigger_reason=insufficient_grounding
  9.  Handoff without consent → 422
 10.  Handoff with invalid trigger_reason → 422
 11.  Phase 3C document generation still works (regression)
 12.  Phase 3B deadline tests still pass (regression)
 13.  Static routes still serve (Phase 3A regression)
 14.  Health endpoint still returns ok

Setup: migration 007 (handoff_leads table) applied in conftest fixture.

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase3d_paid_handoff.py -v -s
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from ingestion.db import get_connection
from tests.integration.payment_helpers import mark_case_paid

from tests.integration.auth_helpers import TEST_USER_ID, mock_auth_headers

client = TestClient(app, raise_server_exceptions=True)

_LEGACY_AUTH = mock_auth_headers(TEST_USER_ID)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def apply_migration_007():
    """Apply migration 007 (handoff_leads) if not already present."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS handoff_leads (
                    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
                    case_id         uuid        REFERENCES cases(id) ON DELETE SET NULL,
                    trigger_reason  text        NOT NULL,
                    name            text        NOT NULL,
                    email           text        NOT NULL,
                    phone           text,
                    case_summary    text,
                    consent_given   boolean     NOT NULL DEFAULT false,
                    created_at      timestamptz NOT NULL DEFAULT now(),
                    CONSTRAINT handoff_leads_consent_required CHECK (consent_given = true)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS handoff_leads_created_idx
                ON handoff_leads (created_at)
            """)
        conn.commit()
    finally:
        conn.close()


_ASSESSMENT = {
    "status": "ok",
    "claim_type": "unfair_dismissal",
    "has_viable_claim": "yes",
    "strength": "medium",
    "reasoning_summary": "3 years service, dismissed for conduct, no procedure.",
    "key_weaknesses": ["Employer may argue conduct was serious."],
    "employer_arguments": ["Band of reasonable responses."],
    "deadline_info": {
        "limitation_date": "2026-06-30",
        "source": "rules",
        "authority": "ERA 1996 s.111(2)",
        "ec_applied": False,
    },
    "value_range": {
        "low": 1800, "high": 31200, "currency": "GBP",
        "basis": "From statutory rules.",
    },
    "recommended_next_step": "prepare_documents",
    "citations": [{"cite": "ERA 1996 s.94", "url": "https://legislation.gov.uk/ukpga/1996/18/section/94"}],
    "grounding_score": 0.85, "confidence_score": 0.75,
    "insufficient_grounding": False,
    "boundary_log": {"fields_passed": ["edt"], "fields_stripped": [], "pii_in_output": []},
}

_FACTS = {
    "edt": "2026-04-01", "service_start_date": "2023-04-01",
    "reason_for_dismissal": "conduct", "was_procedure_followed": False,
    "weekly_pay": 600, "jurisdiction": "EW",
}

_POC_UNPAID = {"document_type": "particulars_of_claim", "assessment": _ASSESSMENT, "facts": _FACTS}
_POC_PAID   = {**_POC_UNPAID}
_SOL_PAID   = {"document_type": "schedule_of_loss", "assessment": _ASSESSMENT, "facts": _FACTS}


@pytest.fixture(scope="module", autouse=True)
def paid_case_for_document_generation():
    """Paid-path assertions use DB-backed paid state, never raw tokens."""
    resp = client.post("/cases", headers=_LEGACY_AUTH, json={
        "claim_type": "unfair_dismissal",
        "jurisdiction": "EW",
        "assessment": _ASSESSMENT,
        "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
    })
    assert resp.status_code == 201
    case_id = resp.json()["case_id"]
    mark_case_paid(case_id)
    _POC_PAID["case_id"] = case_id
    _SOL_PAID["case_id"] = case_id
    yield


# ── 1. Unpaid returns preview ──────────────────────────────────────────────────

def test_unpaid_document_returns_payment_required_true():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_UNPAID)
    assert resp.status_code == 200
    data = resp.json()
    assert data["payment_required"] is True, "Unpaid request must set payment_required=True"


def test_unpaid_document_content_is_truncated():
    resp_unpaid = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_UNPAID)
    resp_paid   = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_PAID)
    assert resp_unpaid.status_code == 200
    assert resp_paid.status_code == 200
    unpaid_len = len(resp_unpaid.json()["content"])
    paid_len   = len(resp_paid.json()["content"])
    assert unpaid_len < paid_len, \
        f"Preview ({unpaid_len} chars) should be shorter than full doc ({paid_len} chars)"


def test_unpaid_preview_contains_preview_notice():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_UNPAID)
    content = resp.json()["content"]
    assert "PREVIEW ENDS HERE" in content or "requires payment" in content.lower(), \
        "Preview must include payment gate notice"


# ── 2. Paid returns full content ──────────────────────────────────────────────

def test_paid_document_returns_payment_required_false():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_PAID)
    assert resp.status_code == 200
    assert resp.json()["payment_required"] is False


def test_paid_document_returns_full_content():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_PAID)
    content = resp.json()["content"]
    # Full doc should contain the statement of truth and the footer notice
    assert "STATEMENT OF TRUTH" in content or "statement of truth" in content.lower()
    assert "DOCUMENT INFORMATION" in content


def test_paid_sol_returns_full_content():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_SOL_PAID)
    assert resp.status_code == 200
    data = resp.json()
    assert data["payment_required"] is False
    assert "TOTALS" in data["content"] or "Total" in data["content"]


# ── 3. Legal boundary in preview ─────────────────────────────────────────────

def test_preview_contains_legal_boundary_notice():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_UNPAID)
    content = resp.json()["content"]
    # The legal boundary notice is near the top so must be in the preview
    assert "NOT legal advice" in content, "Legal boundary notice must appear in preview"


# ── 4. Case saving ────────────────────────────────────────────────────────────

def test_case_save_returns_case_id():
    resp = client.post("/cases", headers=_LEGACY_AUTH, json={
        "claim_type": "unfair_dismissal",
        "jurisdiction": "EW",
        "assessment": _ASSESSMENT,
        "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
        "recommended_next_step": "prepare_documents",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "case_id" in data
    assert len(data["case_id"]) == 36  # UUID format
    assert "created_at" in data


def test_case_save_and_retrieve():
    # Save
    save_resp = client.post("/cases", headers=_LEGACY_AUTH, json={
        "claim_type": "unfair_dismissal",
        "jurisdiction": "EW",
        "assessment": _ASSESSMENT,
        "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
    })
    assert save_resp.status_code == 201
    case_id = save_resp.json()["case_id"]

    # Retrieve
    get_resp = client.get(f"/cases/{case_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["case_id"] == case_id
    assert data["claim_type"] == "unfair_dismissal"
    assert data["jurisdiction"] == "EW"
    assert data["status"] == "diagnosis"
    assert isinstance(data["assessment"], dict)
    assert isinstance(data["key_dates"], dict)


def test_case_retrieve_404_unknown_id():
    resp = client.get("/cases/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── 5. Handoff lead capture ────────────────────────────────────────────────────

_HANDOFF_SEEK = {
    "trigger_reason": "seek_solicitor",
    "name": "Jane Test",
    "email": "jane@test.invalid",
    "consent_given": True,
}

_HANDOFF_IG = {
    "trigger_reason": "insufficient_grounding",
    "name": "Bob Test",
    "email": "bob@test.invalid",
    "phone": "07000000000",
    "case_summary": "Dismissed for no clear reason after 2 years.",
    "consent_given": True,
}


def test_handoff_seek_solicitor_captured():
    resp = client.post("/handoff/leads", json=_HANDOFF_SEEK)
    assert resp.status_code == 201
    data = resp.json()
    assert "lead_id" in data
    assert data["status"] == "received"
    assert "free" in data["message"].lower()


def test_handoff_insufficient_grounding_captured():
    resp = client.post("/handoff/leads", json=_HANDOFF_IG)
    assert resp.status_code == 201
    data = resp.json()
    assert "lead_id" in data
    assert data["status"] == "received"


def test_handoff_message_states_not_a_solicitor():
    resp = client.post("/handoff/leads", json=_HANDOFF_SEEK)
    message = resp.json()["message"]
    assert "not a solicitor" in message.lower() or "lawapp is not" in message.lower()


# ── 6. Handoff validation ─────────────────────────────────────────────────────

def test_handoff_without_consent_returns_422():
    resp = client.post("/handoff/leads", json={
        **_HANDOFF_SEEK,
        "consent_given": False,
    })
    assert resp.status_code == 422


def test_handoff_invalid_trigger_reason_returns_422():
    resp = client.post("/handoff/leads", json={
        **_HANDOFF_SEEK,
        "trigger_reason": "i_want_free_money",
    })
    assert resp.status_code == 422


def test_handoff_missing_name_returns_422():
    resp = client.post("/handoff/leads", json={
        "trigger_reason": "seek_solicitor",
        "email": "test@test.invalid",
        "consent_given": True,
    })
    assert resp.status_code == 422


# ── 7. Phase 3C regression ────────────────────────────────────────────────────

def test_phase3c_document_generation_still_works():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json=_POC_PAID)
    assert resp.status_code == 200
    assert resp.json()["safety_check"]["passed"] is True


def test_phase3c_safety_check_still_blocks_bad_phrases():
    from backend.core.documents import safety_check
    result = safety_check("We will represent you and file your claim.")
    assert result["passed"] is False


# ── 8. Phase 3B regression ────────────────────────────────────────────────────

def test_rules_api_still_returns_time_limit():
    resp = client.get("/rules/unfair_dismissal")
    assert resp.status_code == 200
    keys = [r["rule_key"] for r in resp.json()["rules"]]
    assert "unfair_dismissal.time_limit_months" in keys


def test_deadline_mismatch_detection_still_works():
    resp = client.post("/assess", json={
        "query": "unfair dismissal",
        "facts": {**_FACTS},
        "jurisdiction": "EW",
        "use_model": False,
        "client_deadline": "2026-01-01",
    })
    assert resp.status_code == 200
    assert resp.json().get("deadline_mismatch") is True


# ── 9. Phase 3A regression ────────────────────────────────────────────────────

def test_static_routes_still_serve():
    for path in ["/", "/pages/intake.html", "/pages/assessment.html"]:
        assert client.get(path).status_code == 200, f"{path} failed"


def test_health_still_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
