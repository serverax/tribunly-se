from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


_UD_CASE = {
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


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app

    try:
        app.state.limiter.enabled = False
    except Exception:
        pass
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("path", ["/assess", "/api/diagnosis"])
def test_assessment_routes_expose_rules_backed_deadline_contract(client, path):
    response = client.post(path, json=_UD_CASE)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "ok"
    assert "deadline" in body, body
    assert body["deadline"]["limitation_date"] == "2026-06-30"
    assert body["deadline"]["source"] == "rules"
    assert body["deadline"]["authority"] == "ERA 1996 s.111(2)"

    # Compatibility payload remains available for downstream consumers.
    assert body["deadline_info"]["limitation_date"] == body["deadline"]["limitation_date"]
    assert body["deadline_info"]["source"] == "rules"
