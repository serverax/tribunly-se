from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app
from ingestion.db import get_connection
from tests.integration.auth_helpers import TEST_USER_ID, mock_auth_headers

client = TestClient(app, raise_server_exceptions=True)
AUTH = mock_auth_headers(TEST_USER_ID)

ASSESSMENT = {
    "status": "ok",
    "claim_type": "unfair_dismissal",
    "jurisdiction": "EW",
    "has_viable_claim": "yes",
    "strength": "medium",
    "reasoning_summary": "3 years of service and no fair procedure.",
    "key_weaknesses": ["Employer may dispute causation and mitigation."],
    "employer_arguments": ["Employer may say conduct justified dismissal."],
    "deadline_info": {
        "limitation_date": "2026-07-31",
        "source": "rules",
        "authority": "ERA 1996 s.111(2)",
    },
    "value_range": {
        "low": 3798,
        "high": 34998,
        "currency": "GBP",
        "basis": "Statutory basic award plus compensatory estimate from rules.",
    },
    "recommended_next_step": "prepare_documents",
    "citations": [
        {"cite": "ERA 1996 s.94", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/94"},
        {"cite": "ERA 1996 s.111(2)", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/111"},
    ],
    "grounding_score": 0.9,
    "confidence_score": 0.8,
    "insufficient_grounding": False,
    "boundary_log": {"fields_passed": ["edt"], "fields_stripped": [], "pii_in_output": []},
}

FACTS = {
    "edt": "2026-05-01",
    "service_start_date": "2023-05-01",
    "reason_for_dismissal": "conduct",
    "was_procedure_followed": False,
    "weekly_pay": 673,
    "jurisdiction": "EW",
}

KEY_DATES = {"edt": "2026-05-01", "deadline_date": "2026-07-31"}


def _save_case() -> str:
    response = client.post(
        "/cases",
        headers=AUTH,
        json={
            "claim_type": "unfair_dismissal",
            "jurisdiction": "EW",
            "assessment": ASSESSMENT,
            "key_dates": KEY_DATES,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["case_id"]


def _download(document_id: str) -> str:
    response = client.get(f"/api/documents/{document_id}", headers=AUTH)
    assert response.status_code == 200, response.text
    return response.text


def _payment_event_count(event_id: str) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM payment_events WHERE stripe_event_id = %s", (event_id,))
            return int(cur.fetchone()[0] or 0)
    finally:
        conn.close()


def test_paid_journey_enforces_402_then_unlocks_idempotently(monkeypatch):
    monkeypatch.setenv("PAYMENT_MODE", "test")

    primary_case = _save_case()
    second_case = _save_case()

    unpaid = client.post(
        "/api/documents/generate",
        headers=AUTH,
        json={"case_id": primary_case, "document_type": "particulars", "confirmed_facts": FACTS},
    )
    assert unpaid.status_code == 402, unpaid.text

    checkout = client.post(
        "/api/payments/create-session",
        headers=AUTH,
        json={"case_id": primary_case, "package_id": "full_documents"},
    )
    assert checkout.status_code == 200, checkout.text
    session_id = checkout.json()["session_id"]
    assert session_id.startswith("cs_test_")
    assert checkout.json()["amount_pence"] == 2999

    first_confirm = client.post(
        "/api/payments/confirm-test",
        headers=AUTH,
        json={"session_id": session_id},
    )
    assert first_confirm.status_code == 200, first_confirm.text
    assert first_confirm.json()["payment_status"] == "paid"

    second_confirm = client.post(
        "/api/payments/confirm-test",
        headers=AUTH,
        json={"session_id": session_id},
    )
    assert second_confirm.status_code == 200, second_confirm.text
    assert second_confirm.json()["payment_status"] == "paid"
    assert _payment_event_count(f"manual_payment_confirmed:{session_id}") == 1

    particulars = client.post(
        "/api/documents/generate",
        headers=AUTH,
        json={"case_id": primary_case, "document_type": "particulars", "confirmed_facts": FACTS},
    )
    assert particulars.status_code == 200, particulars.text
    particulars_html = _download(particulars.json()["document_id"])
    assert "IN THE EMPLOYMENT TRIBUNAL" in particulars_html
    assert "SELF-HELP DRAFT" in particulars_html
    assert "STATEMENT OF TRUTH" in particulars_html
    assert "ERA 1996 s.94" in particulars_html

    schedule = client.post(
        "/api/documents/generate",
        headers=AUTH,
        json={"case_id": primary_case, "document_type": "schedule_of_loss", "confirmed_facts": FACTS},
    )
    assert schedule.status_code == 200, schedule.text
    schedule_html = _download(schedule.json()["document_id"])
    assert "SCHEDULE OF LOSS  -  UNFAIR DISMISSAL CLAIM" in schedule_html
    assert "SELF-HELP DRAFT" in schedule_html
    assert "STATEMENT OF TRUTH" in schedule_html
    assert "£3,798" in schedule_html
    assert "£34,998" in schedule_html

    still_locked = client.post(
        "/api/documents/generate",
        headers=AUTH,
        json={"case_id": second_case, "document_type": "particulars", "confirmed_facts": FACTS},
    )
    assert still_locked.status_code == 402, still_locked.text
