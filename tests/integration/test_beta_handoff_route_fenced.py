from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app


def test_handoff_leads_route_unreachable_in_beta(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "beta")
    monkeypatch.delenv("LAWAPP_ENABLE_HANDOFF_LEADS", raising=False)

    client = TestClient(app, raise_server_exceptions=True)

    response = client.post(
        "/handoff/leads",
        json={
            "trigger_reason": "seek_solicitor",
            "name": "Beta Fence",
            "email": "beta-fence@example.com",
            "consent_given": True,
        },
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Not found"}
