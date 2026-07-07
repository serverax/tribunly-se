from __future__ import annotations

import io

from fastapi.testclient import TestClient

from backend.api.main import app
from tests.integration.auth_helpers import TEST_USER_ID, mock_auth_headers

client = TestClient(app, raise_server_exceptions=True)
AUTH = mock_auth_headers(TEST_USER_ID)


def _make_case() -> str:
    response = client.post(
        "/cases",
        headers=AUTH,
        json={
            "claim_type": "unfair_dismissal",
            "jurisdiction": "EW",
            "assessment": {
                "status": "ok",
                "claim_type": "unfair_dismissal",
                "has_viable_claim": "yes",
                "strength": "medium",
                "reasoning_summary": "Test assessment.",
                "key_weaknesses": [],
                "employer_arguments": [],
                "deadline_info": {
                    "limitation_date": "2026-06-30",
                    "source": "rules",
                    "authority": "ERA 1996 s.111(2)",
                    "ec_applied": False,
                },
                "value_range": {"low": 1800, "high": 31200, "currency": "GBP", "basis": "From rules."},
                "recommended_next_step": "prepare_documents",
                "citations": [],
                "grounding_score": 0.85,
                "confidence_score": 0.75,
                "insufficient_grounding": False,
                "boundary_log": {"fields_passed": ["edt"], "fields_stripped": [], "pii_in_output": []},
            },
            "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["case_id"]


def test_api_uploads_route_is_fenced_in_beta(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "beta")
    monkeypatch.delenv("LAWAPP_ENABLE_API_UPLOADS", raising=False)

    case_id = _make_case()
    response = client.post(
        "/api/uploads/upload",
        headers=AUTH,
        data={"case_id": case_id},
        files={"file": ("beta-proof.pdf", io.BytesIO(b"%PDF-1.0\n%%EOF"), "application/pdf")},
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Not found"}
