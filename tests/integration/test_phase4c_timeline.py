"""
Phase 4C  -  Case timeline and escalation integration tests.

Tests:
  Timeline:
   1.  Timeline can be generated for a saved case
   2.  Timeline includes EDT/dismissal date when present
   3.  Timeline includes ACAS dates when present
   4.  Timeline includes authoritative ET deadline (rules_engine source)
   5.  Timeline includes uploaded-document event
   6.  Timeline includes generated-document event
   7.  Missing dates are flagged, not invented
   8.  Custom user event can be added
   9.  Custom user event can be updated
  10.  Timeline excludes unconfirmed extracted facts (no placeholder values)
  11.  Timeline excludes rejected extracted facts

  Escalation:
  12.  urgent_deadline near ET deadline
  13.  solicitor_recommended for seek_solicitor assessment
  14.  needs_review for insufficient_grounding
  15.  none when case is safe

  Safety:
  16.  Legal boundary notice visible on saved-case page
  17.  No prohibited phrases in timeline/escalation responses

  Saved-case page:
  18.  Saved-case page still loads after Phase 4C changes

  Regressions:
  19.  Phase 4B bundle still works
  20.  Phase 4A upload still works
  21.  Phase 3C document generation still works
  22.  Static routes still serve
  23.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase4c_timeline.py -v -s
"""

from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

from tests.integration.auth_helpers import TEST_USER_ID, mock_auth_headers
from tests.integration.extraction_helpers import seed_extracted_facts
from tests.integration.payment_helpers import mark_case_paid

client = TestClient(app, raise_server_exceptions=True)

# Legacy /documents/generate fails closed (401) for anonymous callers; these tests
# target payment/content behaviour, so authenticate with a mock identity.
_LEGACY_AUTH = mock_auth_headers(TEST_USER_ID)

_MOCK_PDF = b"%PDF-1.0\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"


@pytest.fixture(scope="module", autouse=True)
def apply_migration_009():
    """Apply migration 009 (case_timeline_events) if not already present."""
    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS case_timeline_events (
                    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
                    case_id     uuid        REFERENCES cases(id) ON DELETE CASCADE,
                    event_type  text        NOT NULL,
                    event_date  date,
                    title       text        NOT NULL,
                    description text,
                    source      text        NOT NULL DEFAULT 'user_entered',
                    status      text        NOT NULL DEFAULT 'active',
                    created_at  timestamptz NOT NULL DEFAULT now(),
                    updated_at  timestamptz NOT NULL DEFAULT now()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS cte_case_idx ON case_timeline_events (case_id)")
        conn.commit()
    finally:
        conn.close()


# ── Fixtures ──────────────────────────────────────────────────────────────────

_ASSESSMENT_OK = {
    "status": "ok", "claim_type": "unfair_dismissal", "has_viable_claim": "yes",
    "strength": "medium", "reasoning_summary": "Test.",
    "key_weaknesses": [], "employer_arguments": [],
    "deadline_info": {"limitation_date": "2026-06-30", "source": "rules",
                      "authority": "ERA 1996 s.111(2)", "ec_applied": False},
    "value_range": {"low": 1800, "high": 31200, "currency": "GBP", "basis": "From rules."},
    "recommended_next_step": "prepare_documents",
    "citations": [], "grounding_score": 0.85, "confidence_score": 0.75,
    "insufficient_grounding": False,
    "boundary_log": {"fields_passed": ["edt"], "fields_stripped": [], "pii_in_output": []},
}

_ASSESSMENT_SEEK_SOLICITOR = {**_ASSESSMENT_OK, "recommended_next_step": "seek_solicitor"}
_ASSESSMENT_INSUFFICIENT = {**_ASSESSMENT_OK, "insufficient_grounding": True, "strength": "low",
                             "recommended_next_step": "free_diagnosis_only"}

_KEY_DATES_FULL = {
    "edt": "2026-04-01",
    "deadline_date": "2026-06-30",
    "employment_start_date": "2023-04-01",
    "ec_day_a": "2026-04-20",
    "ec_day_b": "2026-05-10",
}

_KEY_DATES_EDT_ONLY = {
    "edt": "2026-04-01",
    "deadline_date": "2026-06-30",
}


def _make_case(assessment=None, key_dates=None) -> str:
    resp = client.post("/cases", headers=_LEGACY_AUTH, json={
        "claim_type": "unfair_dismissal", "jurisdiction": "EW",
        "assessment": assessment or _ASSESSMENT_OK,
        "key_dates": key_dates or _KEY_DATES_EDT_ONLY,
    })
    assert resp.status_code == 201
    return resp.json()["case_id"]


def _make_paid_case(assessment=None, key_dates=None) -> str:
    case_id = _make_case(assessment=assessment, key_dates=key_dates)
    mark_case_paid(case_id)
    return case_id


# ── 1. Timeline generated ─────────────────────────────────────────────────────

def test_timeline_generated_for_case():
    case_id = _make_case()
    resp = client.get(f"/cases/{case_id}/timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert data["event_count"] > 0
    assert "case_id" in data


# ── 2. Timeline includes EDT ──────────────────────────────────────────────────

def test_timeline_includes_edt():
    case_id = _make_case(key_dates=_KEY_DATES_EDT_ONLY)
    resp = client.get(f"/cases/{case_id}/timeline")
    events = resp.json()["events"]
    dismissal_events = [e for e in events if e["event_type"] == "dismissal"]
    assert len(dismissal_events) > 0
    assert dismissal_events[0]["event_date"] == "2026-04-01"
    assert dismissal_events[0]["missing_date"] is False


# ── 3. Timeline includes ACAS dates ──────────────────────────────────────────

def test_timeline_includes_acas_dates():
    case_id = _make_case(key_dates=_KEY_DATES_FULL)
    resp = client.get(f"/cases/{case_id}/timeline")
    events = resp.json()["events"]
    types  = [e["event_type"] for e in events]
    assert "acas_day_a" in types
    assert "acas_day_b" in types
    day_a = next(e for e in events if e["event_type"] == "acas_day_a")
    assert day_a["event_date"] == "2026-04-20"


# ── 4. ET deadline is rules_engine source ─────────────────────────────────────

def test_timeline_includes_authoritative_et_deadline():
    case_id = _make_case()
    resp = client.get(f"/cases/{case_id}/timeline")
    events = resp.json()["events"]
    deadline_evts = [e for e in events if e["event_type"] == "et_deadline"]
    assert len(deadline_evts) > 0
    assert deadline_evts[0]["source"] == "rules_engine", \
        "ET deadline must have source=rules_engine (backend-authoritative)"
    assert deadline_evts[0]["event_date"] == "2026-06-30"


# ── 5. Timeline includes uploaded-document event ──────────────────────────────

def test_timeline_includes_uploaded_document_event():
    case_id = _make_case()
    client.post(
        f"/cases/{case_id}/uploads",
        data={"doc_type": "dismissal_letter"},
        files={"file": ("dl.pdf", io.BytesIO(_MOCK_PDF), "application/pdf")},
    )
    resp = client.get(f"/cases/{case_id}/timeline")
    types = [e["event_type"] for e in resp.json()["events"]]
    assert "document_uploaded" in types


# ── 6. Timeline includes generated-document event ─────────────────────────────

def test_timeline_includes_generated_document_event():
    case_id = _make_paid_case()
    # Generate a document (bundle component is saved to documents table)
    client.post(f"/cases/{case_id}/bundle/generate", json={})
    resp = client.get(f"/cases/{case_id}/timeline")
    types = [e["event_type"] for e in resp.json()["events"]]
    assert "document_generated" in types


# ── 7. Missing dates flagged ──────────────────────────────────────────────────

def test_missing_dates_flagged_not_invented():
    """Case without employment_start_date must show missing_date=True for that event."""
    case_id = _make_case(key_dates={"edt": "2026-04-01", "deadline_date": "2026-06-30"})
    resp = client.get(f"/cases/{case_id}/timeline")
    data = resp.json()
    start_evts = [e for e in data["events"] if e["event_type"] == "employment_started"]
    assert len(start_evts) > 0
    # The one without confirmed start date must be flagged
    auto_start = next((e for e in start_evts if not e["is_manual"]), None)
    assert auto_start is not None
    assert auto_start["missing_date"] is True
    assert auto_start["event_date"] is None
    # Warnings list must mention missing start date
    assert len(data["missing_date_warnings"]) > 0


# ── 8. Custom event added ─────────────────────────────────────────────────────

def test_custom_event_can_be_added():
    case_id = _make_case()
    resp = client.post(f"/cases/{case_id}/timeline/events", json={
        "event_type": "custom_user_event",
        "event_date": "2026-04-10",
        "title": "Met with HR to discuss appeal",
        "description": "Informal meeting, no outcome recorded.",
        "source": "user_entered",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "event_id" in data
    assert data["event_type"] == "custom_user_event"
    assert data["event_date"] == "2026-04-10"

    # Verify it appears in timeline
    tl = client.get(f"/cases/{case_id}/timeline").json()
    manual = [e for e in tl["events"] if e["is_manual"]]
    assert any(e["title"] == "Met with HR to discuss appeal" for e in manual)


# ── 9. Custom event updated ───────────────────────────────────────────────────

def test_custom_event_can_be_updated():
    case_id = _make_case()
    create_resp = client.post(f"/cases/{case_id}/timeline/events", json={
        "event_type": "custom_user_event",
        "title": "Original title",
        "source": "user_entered",
    })
    event_id = create_resp.json()["event_id"]

    patch_resp = client.patch(
        f"/cases/{case_id}/timeline/events/{event_id}",
        json={"title": "Updated title", "event_date": "2026-04-15"},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["title"] == "Updated title"
    assert data["event_date"] == "2026-04-15"


# ── 10-11. Confirmed/unconfirmed/rejected facts ───────────────────────────────

def test_timeline_excludes_unconfirmed_extracted_facts():
    """Unconfirmed extraction placeholders must not appear as timeline event descriptions."""
    case_id = _make_case()
    # Upload + extract but do NOT confirm
    upload_id = client.post(
        f"/cases/{case_id}/uploads",
        data={"doc_type": "employment_contract"},
        files={"file": ("c.pdf", io.BytesIO(_MOCK_PDF), "application/pdf")},
    ).json()["upload_id"]
    client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")
    seed_extracted_facts(upload_id, {
        "edt_candidate": {"status": "extracted_unconfirmed", "value": "[Extracted from uploaded document]"},
    })

    tl = client.get(f"/cases/{case_id}/timeline").json()
    full_text = str(tl)
    assert "[Extracted from" not in full_text, \
        "Unconfirmed placeholder text must not appear in timeline"


def test_timeline_excludes_rejected_extracted_facts():
    case_id = _make_case()
    upload_id = client.post(
        f"/cases/{case_id}/uploads",
        data={"doc_type": "dismissal_letter"},
        files={"file": ("dl.pdf", io.BytesIO(_MOCK_PDF), "application/pdf")},
    ).json()["upload_id"]
    client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")
    seeded_facts = {
        "edt_candidate": {"status": "extracted_unconfirmed", "value": "2026-03-15"},
        "employer_name": {"status": "extracted_unconfirmed", "value": "Example Ltd"},
    }
    seed_extracted_facts(upload_id, seeded_facts)
    client.patch(
        f"/cases/{case_id}/uploads/{upload_id}/facts",
        json={"facts": {field: {"status": "rejected"} for field in seeded_facts}},
    )

    tl = client.get(f"/cases/{case_id}/timeline").json()
    # confirmed_extraction source events should be absent
    ce_events = [e for e in tl["events"] if e["source"] == "confirmed_extraction"]
    assert ce_events == [], \
        f"Rejected facts should not produce confirmed_extraction events; got {ce_events}"


# ── 12-15. Escalation ────────────────────────────────────────────────────────

def test_escalation_urgent_deadline_near_deadline():
    """Case with past deadline → urgent_deadline escalation."""
    case_id = _make_case(key_dates={"edt": "2025-01-01", "deadline_date": "2025-04-01"})
    resp = client.get(f"/cases/{case_id}/escalation?as_of=2026-06-01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] in ("urgent_deadline", "solicitor_recommended"), \
        f"Expected urgent escalation, got: {data['state']}"
    assert "urgent_deadline" in data["triggered_states"]


def test_escalation_solicitor_recommended_for_seek_solicitor():
    case_id = _make_case(assessment=_ASSESSMENT_SEEK_SOLICITOR)
    resp = client.get(f"/cases/{case_id}/escalation")
    data = resp.json()
    assert data["state"] == "solicitor_recommended"
    assert "solicitor_recommended" in data["triggered_states"]


def test_escalation_needs_review_for_insufficient_grounding():
    case_id = _make_case(assessment=_ASSESSMENT_INSUFFICIENT)
    resp = client.get(f"/cases/{case_id}/escalation")
    data = resp.json()
    assert data["state"] in ("needs_review", "solicitor_recommended"), \
        f"Insufficient grounding should trigger review/solicitor escalation: {data['state']}"


def test_escalation_none_for_safe_case():
    """Safe case (plenty of time, viable, no issues) → none or watch."""
    case_id = _make_case(key_dates={"edt": "2026-04-01", "deadline_date": "2099-12-31"})
    resp = client.get(f"/cases/{case_id}/escalation")
    data = resp.json()
    assert data["state"] in ("none", "watch"), \
        f"Safe case should be none/watch, got: {data['state']}"


# ── 16-17. Safety ────────────────────────────────────────────────────────────

def test_legal_boundary_on_saved_case_page():
    resp = client.get("/pages/saved_case.html")
    body = resp.text
    assert "Not a law firm" in body
    assert "not legal advice" in body.lower()


def test_no_prohibited_phrases_in_escalation():
    case_id = _make_case()
    resp = client.get(f"/cases/{case_id}/escalation")
    body = str(resp.json()).lower()
    for phrase in ["we will file", "we will submit", "we will represent",
                   "guaranteed", "you will win", "as your solicitor"]:
        assert phrase not in body, f"Prohibited phrase '{phrase}' in escalation"


def test_no_prohibited_phrases_in_timeline():
    case_id = _make_case()
    resp = client.get(f"/cases/{case_id}/timeline")
    body = str(resp.json()).lower()
    for phrase in ["we will file", "we will submit", "we will represent",
                   "guaranteed", "you will win"]:
        assert phrase not in body, f"Prohibited phrase '{phrase}' in timeline"


def test_escalation_never_claims_solicitor_assigned():
    case_id = _make_case(assessment=_ASSESSMENT_SEEK_SOLICITOR)
    resp = client.get(f"/cases/{case_id}/escalation")
    body = str(resp.json()).lower()
    assert "accepted" not in body or "no solicitor has been assigned" in body


# ── 18. Saved-case page ───────────────────────────────────────────────────────

def test_saved_case_page_loads_after_phase4c():
    resp = client.get("/pages/saved_case.html")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


# ── 19-23. Regressions ────────────────────────────────────────────────────────

def test_phase4b_bundle_regression():
    case_id = _make_paid_case()
    resp = client.post(f"/cases/{case_id}/bundle/generate", json={})
    assert resp.status_code == 200
    assert resp.json()["payment_required"] is False


def test_phase4a_upload_regression():
    case_id = _make_case()
    resp = client.post(
        f"/cases/{case_id}/uploads",
        data={"doc_type": "payslip"},
        files={"file": ("p.pdf", io.BytesIO(_MOCK_PDF), "application/pdf")},
    )
    assert resp.status_code == 201


def test_phase3c_document_generation_regression():
    from tests.integration.test_phase4b_bundle import _ASSESSMENT
    case_id = _make_paid_case()
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json={
        "document_type": "schedule_of_loss",
        "assessment": _ASSESSMENT,
        "facts": {"edt": "2026-04-01", "service_start_date": "2023-04-01", "jurisdiction": "EW"},
        "case_id": case_id,
    })
    assert resp.status_code == 200
    assert resp.json()["safety_check"]["passed"] is True


def test_static_routes_regression():
    for path in ["/", "/pages/intake.html", "/pages/assessment.html", "/pages/saved_case.html"]:
        assert client.get(path).status_code == 200, f"{path} failed"


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
