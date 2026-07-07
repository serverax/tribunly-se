from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_assess_returns_temporary_unavailable_when_retrieval_backend_fails():
    body = {
        "query": "I was dismissed after 3 years without any warning or procedure.",
        "facts": {
            "edt": "2026-04-01",
            "service_start_date": "2023-04-01",
            "reason_for_dismissal": "conduct",
            "was_procedure_followed": False,
            "weekly_pay": 600,
            "jurisdiction": "EW",
        },
        "jurisdiction": "EW",
        "use_model": False,
    }

    with patch(
        "backend.core.control_plane.reasoning_router.ReasoningRouter.route_and_retrieve",
        side_effect=RuntimeError("rules backend down"),
    ):
        response = client.post("/assess", json=body)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "temporarily_unavailable"
    assert "temporarily unavailable" in data["message"].lower()
    assert "try again" in data["message"].lower()
    assert data.get("retryable") is True
    assert data.get("insufficient_grounding") is True
    assert data.get("citations") == []
    assert data["status"] != "not_supported"
