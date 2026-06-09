"""
Phase 3E — Deadline tracker, saved-case return, legal-boundary sweep, MVP journey.

Tests:
  Urgency computation (unit, deterministic dates):
   1. expired
   2. due_within_7
   3. due_within_14
   4. due_within_30
   5. safe

  Deadline endpoint:
   6. GET /cases/{id}/deadline returns urgency info
   7. Expired deadline flagged correctly via as_of param
   8. Missing deadline returns deadline_available=False

  Saved-case return:
   9. Reloaded case preserves assessment
  10. Reloaded case preserves key_dates
  11. 404 on unknown case_id

  Reminders:
  12. POST /cases/{id}/reminders creates record
  13. GET /cases/{id}/reminders lists records
  14. Invalid reminder_type → 422

  Legal-boundary sweep:
  15. Landing page has "not a law firm" and "not legal advice"
  16. Intake page has "not a law firm" and "not legal advice"
  17. Assessment page has "not a law firm" and "not legal advice"
  18. Saved-case page has "not a law firm" and "not legal advice"
  19. No page contains "we will file", "we will represent", "guaranteed outcome"

  Full MVP journey:
  20. End-to-end: assess → save → preview doc → paid doc → reload → deadline → reminder

  Regressions:
  21. Phase 3B rules API still works
  22. Phase 3C document safety check still works
  23. Phase 3D handoff consent still enforced
  24. Static routes still serve

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase3e_mvp_close.py -v -s
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.domains.employment.reminders import compute_urgency

client = TestClient(app, raise_server_exceptions=True)


@pytest.fixture(scope="module", autouse=True)
def apply_migration_004_reminder_events():
    """
    Apply the reminder_events table from migration 004 if not already present.
    Migration 004 was a placeholder and may not have been applied to the live DB.
    This is idempotent (CREATE TABLE IF NOT EXISTS).
    """
    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reminder_events (
                    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
                    case_id         uuid        REFERENCES cases(id) ON DELETE CASCADE,
                    reminder_type   text        NOT NULL,
                    due_at          timestamptz,
                    channel         text        NOT NULL DEFAULT 'in_app',
                    status          text        NOT NULL DEFAULT 'pending',
                    payload         jsonb,
                    created_at      timestamptz NOT NULL DEFAULT now()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS re_case_idx ON reminder_events (case_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS re_due_idx ON reminder_events (due_at)
                WHERE status = 'pending'
            """)
        conn.commit()
    finally:
        conn.close()


_ASSESSMENT = {
    "status": "ok",
    "claim_type": "unfair_dismissal",
    "has_viable_claim": "yes",
    "strength": "medium",
    "reasoning_summary": "3 years service, no procedure followed.",
    "key_weaknesses": ["Employer may argue conduct was serious."],
    "employer_arguments": [],
    "deadline_info": {"limitation_date": "2026-06-30", "source": "rules", "authority": "ERA 1996 s.111(2)", "ec_applied": False},
    "value_range": {"low": 1800, "high": 31200, "currency": "GBP", "basis": "From rules."},
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

_KEY_DATES = {"edt": "2026-04-01", "deadline_date": "2026-06-30"}


def _save_case(**kwargs) -> str:
    """Helper: save a case and return its case_id."""
    body = {"claim_type": "unfair_dismissal", "jurisdiction": "EW",
            "assessment": _ASSESSMENT, "key_dates": _KEY_DATES}
    body.update(kwargs)
    resp = client.post("/cases", json=body)
    assert resp.status_code == 201
    return resp.json()["case_id"]


# ── 1-5. Urgency computation (deterministic unit tests) ───────────────────────

def test_urgency_expired():
    r = compute_urgency("2026-05-01", today_str="2026-06-01")
    assert r["urgency"] == "expired"
    assert r["days_remaining"] < 0
    assert r["is_urgent"] is True


def test_urgency_within_7():
    r = compute_urgency("2026-06-05", today_str="2026-06-01")
    assert r["urgency"] == "due_within_7"
    assert r["days_remaining"] == 4
    assert r["is_urgent"] is True


def test_urgency_within_14():
    r = compute_urgency("2026-06-10", today_str="2026-06-01")
    assert r["urgency"] == "due_within_14"
    assert r["days_remaining"] == 9
    assert r["is_urgent"] is True


def test_urgency_within_30():
    r = compute_urgency("2026-06-25", today_str="2026-06-01")
    assert r["urgency"] == "due_within_30"
    assert r["days_remaining"] == 24
    assert r["is_urgent"] is True


def test_urgency_safe():
    r = compute_urgency("2026-09-01", today_str="2026-06-01")
    assert r["urgency"] == "safe"
    assert r["days_remaining"] > 30
    assert r["is_urgent"] is False


def test_urgency_boundary_exactly_30_days():
    r = compute_urgency("2026-07-01", today_str="2026-06-01")
    assert r["urgency"] == "due_within_30"
    assert r["days_remaining"] == 30


def test_urgency_boundary_exactly_7_days():
    r = compute_urgency("2026-06-08", today_str="2026-06-01")
    assert r["urgency"] == "due_within_7"
    assert r["days_remaining"] == 7


# ── 6-8. Deadline endpoint ────────────────────────────────────────────────────

def test_deadline_endpoint_returns_urgency():
    case_id = _save_case()
    resp = client.get(f"/cases/{case_id}/deadline")
    assert resp.status_code == 200
    data = resp.json()
    assert "urgency" in data
    assert data["deadline_available"] is True
    assert data["limitation_date"] == "2026-06-30"


def test_deadline_endpoint_expired_via_as_of():
    """as_of parameter allows testing expired state deterministically."""
    case_id = _save_case()
    resp = client.get(f"/cases/{case_id}/deadline?as_of=2026-09-01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["urgency"] == "expired", f"Expected expired, got: {data['urgency']}"
    assert data["days_remaining"] < 0


def test_deadline_endpoint_safe_via_as_of():
    case_id = _save_case(key_dates={"edt": "2026-04-01", "deadline_date": "2026-06-30"})
    resp = client.get(f"/cases/{case_id}/deadline?as_of=2026-05-01")
    assert resp.status_code == 200
    assert resp.json()["urgency"] == "safe"


def test_deadline_endpoint_missing_deadline():
    case_id = _save_case(key_dates={"edt": "2026-04-01"})  # no deadline_date
    resp = client.get(f"/cases/{case_id}/deadline")
    assert resp.status_code == 200
    assert resp.json()["deadline_available"] is False


def test_deadline_endpoint_404_unknown_case():
    resp = client.get("/cases/00000000-0000-0000-0000-000000000000/deadline")
    assert resp.status_code == 404


# ── 9-11. Saved-case return ───────────────────────────────────────────────────

def test_saved_case_reload_preserves_assessment():
    case_id = _save_case()
    resp = client.get(f"/cases/{case_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["assessment"]["has_viable_claim"] == "yes"
    assert data["assessment"]["claim_type"] == "unfair_dismissal"
    assert data["assessment"]["strength"] == "medium"


def test_saved_case_reload_preserves_key_dates():
    case_id = _save_case()
    resp = client.get(f"/cases/{case_id}")
    data = resp.json()
    assert data["key_dates"]["edt"] == "2026-04-01"
    assert data["key_dates"]["deadline_date"] == "2026-06-30"


def test_saved_case_preserves_claim_type_and_status():
    case_id = _save_case()
    resp = client.get(f"/cases/{case_id}")
    data = resp.json()
    assert data["claim_type"] == "unfair_dismissal"
    assert data["jurisdiction"] == "EW"
    assert data["status"] == "diagnosis"


def test_saved_case_404_unknown_id():
    resp = client.get("/cases/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── 12-14. Reminders ─────────────────────────────────────────────────────────

def test_reminder_creation_works():
    case_id = _save_case()
    resp = client.post(f"/cases/{case_id}/reminders", json={
        "reminder_type": "deadline_approaching",
        "due_at": "2026-06-23T09:00:00",
        "channel": "in_app",
        "payload": {"message": "Your deadline is approaching."},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "reminder_id" in data
    assert data["reminder_type"] == "deadline_approaching"
    assert data["status"] == "pending"


def test_reminder_list_returns_created_reminders():
    case_id = _save_case()
    # Create two reminders
    for rt in ["deadline_approaching", "acas_not_started"]:
        r = client.post(f"/cases/{case_id}/reminders", json={"reminder_type": rt})
        assert r.status_code == 201
    # List
    resp = client.get(f"/cases/{case_id}/reminders")
    assert resp.status_code == 200
    reminders = resp.json()["reminders"]
    types = [r["reminder_type"] for r in reminders]
    assert "deadline_approaching" in types
    assert "acas_not_started" in types


def test_reminder_invalid_type_returns_422():
    case_id = _save_case()
    resp = client.post(f"/cases/{case_id}/reminders", json={
        "reminder_type": "send_threatening_letter",
    })
    assert resp.status_code == 422


def test_reminder_404_unknown_case():
    resp = client.post(
        "/cases/00000000-0000-0000-0000-000000000000/reminders",
        json={"reminder_type": "deadline_approaching"},
    )
    assert resp.status_code == 404


# ── 15-19. Legal-boundary sweep ───────────────────────────────────────────────

_REQUIRED_PHRASES = [
    "not a law firm",
    "not legal advice",
]

_PROHIBITED_PHRASES = [
    "we will file",
    "we will represent",
    "guaranteed outcome",
    "as your solicitor",
    "acting as your solicitor",
]

_PAGES_TO_CHECK = [
    ("/",                        "Landing page"),
    ("/pages/intake.html",       "Intake page"),
    ("/pages/assessment.html",   "Assessment page"),
    ("/pages/saved_case.html",   "Saved case page"),
]


@pytest.mark.parametrize("path,name", _PAGES_TO_CHECK)
def test_legal_boundary_present(path, name):
    body = client.get(path).text.lower()
    for phrase in _REQUIRED_PHRASES:
        assert phrase.lower() in body, \
            f"'{phrase}' missing from {name} ({path})"


@pytest.mark.parametrize("path,name", _PAGES_TO_CHECK)
def test_no_prohibited_phrases(path, name):
    body = client.get(path).text.lower()
    for phrase in _PROHIBITED_PHRASES:
        assert phrase.lower() not in body, \
            f"Prohibited phrase '{phrase}' found on {name} ({path})"


def test_saved_case_page_served():
    resp = client.get("/pages/saved_case.html")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


# ── 20. Full MVP journey ──────────────────────────────────────────────────────

def test_full_mvp_journey():
    """End-to-end: assess → preview → paid doc → save → reload → deadline → reminder → handoff."""

    # 1. Assess
    assess_resp = client.post("/assess", json={
        "query": "I was unfairly dismissed",
        "facts": _FACTS,
        "jurisdiction": "EW",
        "use_model": False,
        "client_deadline": "2026-06-30",
    })
    assert assess_resp.status_code == 200
    assessment = assess_resp.json()
    assert "boundary_log" in assessment
    assert assessment.get("deadline_mismatch") is False

    # 2. Preview document (unpaid)
    preview_resp = client.post("/documents/generate", json={
        "document_type": "particulars_of_claim",
        "assessment": assessment,
        "facts": _FACTS,
    })
    assert preview_resp.status_code == 200
    assert preview_resp.json()["payment_required"] is True
    assert "PREVIEW ENDS HERE" in preview_resp.json()["content"] or \
           "requires payment" in preview_resp.json()["content"].lower()

    # 3. Full document (mock paid)
    full_resp = client.post("/documents/generate", json={
        "document_type": "particulars_of_claim",
        "assessment": assessment,
        "facts": _FACTS,
        "payment_token": "test_mvp-journey-test",
    })
    assert full_resp.status_code == 200
    assert full_resp.json()["payment_required"] is False
    assert "STATEMENT OF TRUTH" in full_resp.json()["content"]

    # 4. Save case
    save_resp = client.post("/cases", json={
        "claim_type": "unfair_dismissal",
        "jurisdiction": "EW",
        "assessment": assessment,
        "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
    })
    assert save_resp.status_code == 201
    case_id = save_resp.json()["case_id"]

    # 5. Reload saved case
    reload_resp = client.get(f"/cases/{case_id}")
    assert reload_resp.status_code == 200
    assert reload_resp.json()["claim_type"] == "unfair_dismissal"
    assert reload_resp.json()["key_dates"]["deadline_date"] == "2026-06-30"

    # 6. Deadline + urgency
    dl_resp = client.get(f"/cases/{case_id}/deadline?as_of=2026-06-01")
    assert dl_resp.status_code == 200
    dl_data = dl_resp.json()
    assert dl_data["deadline_available"] is True
    assert dl_data["urgency"] == "due_within_30"

    # 7. Create reminder
    rem_resp = client.post(f"/cases/{case_id}/reminders", json={
        "reminder_type": "deadline_approaching",
        "payload": {"urgency": dl_data["urgency"]},
    })
    assert rem_resp.status_code == 201

    # 8. Handoff lead (seek_solicitor path)
    hf_resp = client.post("/handoff/leads", json={
        "trigger_reason": "seek_solicitor",
        "name": "MVP Test",
        "email": "mvp@test.invalid",
        "consent_given": True,
    })
    assert hf_resp.status_code == 201
    assert hf_resp.json()["status"] == "received"

    # 9. Rules API still authoritative
    rules_resp = client.get("/rules/unfair_dismissal")
    assert rules_resp.status_code == 200
    assert any(r["rule_key"] == "unfair_dismissal.time_limit_months"
               for r in rules_resp.json()["rules"])


# ── 21-24. Regressions ────────────────────────────────────────────────────────

def test_phase3b_rules_api_regression():
    resp = client.get("/rules/unfair_dismissal")
    assert resp.status_code == 200
    keys = [r["rule_key"] for r in resp.json()["rules"]]
    assert "unfair_dismissal.time_limit_months" in keys
    rule = next(r for r in resp.json()["rules"] if r["rule_key"] == "unfair_dismissal.time_limit_months")
    assert int(rule["value_numeric"]) == 3
    assert "last_verified_at" in rule


def test_phase3c_document_generation_regression():
    resp = client.post("/documents/generate", json={
        "document_type": "schedule_of_loss",
        "assessment": _ASSESSMENT,
        "facts": _FACTS,
        "payment_token": "test_regression-test",
    })
    assert resp.status_code == 200
    assert resp.json()["safety_check"]["passed"] is True
    assert resp.json()["payment_required"] is False


def test_phase3d_consent_still_enforced():
    resp = client.post("/handoff/leads", json={
        "trigger_reason": "seek_solicitor",
        "name": "Test",
        "email": "t@t.invalid",
        "consent_given": False,
    })
    assert resp.status_code == 422


def test_static_routes_regression():
    for path in ["/", "/pages/intake.html", "/pages/assessment.html", "/pages/saved_case.html"]:
        assert client.get(path).status_code == 200, f"{path} failed"


def test_health_regression():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
