from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app
from tests.integration.auth_helpers import TEST_USER_ID, mock_auth_headers
from tests.integration.payment_helpers import mark_case_paid


client = TestClient(app, raise_server_exceptions=True)
AUTH = mock_auth_headers(TEST_USER_ID)

ASSESSMENT = {
    "status": "ok",
    "claim_type": "unfair_dismissal",
    "has_viable_claim": "yes",
    "strength": "medium",
    "reasoning_summary": "3 years service, no procedure followed.",
    "key_weaknesses": ["Employer may argue conduct was serious."],
    "employer_arguments": [],
    "deadline_info": {
        "limitation_date": "2026-07-31",
        "source": "rules",
        "authority": "ERA 1996 s.111(2)",
        "ec_applied": False,
    },
    "value_range": {
        "low": 3798,
        "high": 34998,
        "currency": "GBP",
        "basis": "From rules.",
    },
    "recommended_next_step": "prepare_documents",
    "citations": [
        {"cite": "ERA 1996 s.94", "url": "https://legislation.gov.uk/ukpga/1996/18/section/94"},
        {"cite": "ERA 1996 s.111(2)", "url": "https://legislation.gov.uk/ukpga/1996/18/section/111"},
    ],
    "grounding_score": 0.85,
    "confidence_score": 0.75,
    "insufficient_grounding": False,
}

FACTS = {
    "edt": "2026-05-01",
    "service_start_date": "2020-01-01",
    "reason_for_dismissal": "conduct",
    "was_procedure_followed": False,
    "weekly_pay": 600,
    "jurisdiction": "EW",
}


def _paid_case_id() -> str:
    resp = client.post(
        "/cases",
        headers=AUTH,
        json={
            "claim_type": "unfair_dismissal",
            "jurisdiction": "EW",
            "assessment": ASSESSMENT,
            "key_dates": {"edt": "2026-05-01", "deadline_date": "2026-07-31"},
        },
    )
    assert resp.status_code == 201, resp.text
    case_id = resp.json()["case_id"]
    mark_case_paid(case_id)
    return case_id


def test_canonical_particulars_route_uses_unfair_dismissal_template():
    case_id = _paid_case_id()
    create = client.post(
        "/api/documents/generate",
        headers=AUTH,
        json={
            "case_id": case_id,
            "document_type": "particulars",
            "confirmed_facts": FACTS,
        },
    )
    assert create.status_code == 200, create.text
    document_id = create.json()["document_id"]

    download = client.get(f"/api/documents/{document_id}", headers=AUTH)
    assert download.status_code == 200, download.text
    content = download.text
    assert "IN THE EMPLOYMENT TRIBUNAL" in content
    assert "SELF-HELP DRAFT" in content
    assert "STATEMENT OF TRUTH" in content
    assert "ERA 1996 s.94" in content


def test_canonical_schedule_route_uses_unfair_dismissal_template():
    case_id = _paid_case_id()
    create = client.post(
        "/api/documents/generate",
        headers=AUTH,
        json={
            "case_id": case_id,
            "document_type": "schedule_of_loss",
            "confirmed_facts": FACTS,
        },
    )
    assert create.status_code == 200, create.text
    document_id = create.json()["document_id"]

    download = client.get(f"/api/documents/{document_id}", headers=AUTH)
    assert download.status_code == 200, download.text
    content = download.text
    assert "SCHEDULE OF LOSS  -  UNFAIR DISMISSAL CLAIM" in content
    assert "SELF-HELP DRAFT" in content
    assert "STATEMENT OF TRUTH" in content
    assert "£3,798" in content
    assert "£34,998" in content
