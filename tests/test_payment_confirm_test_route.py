from fastapi.testclient import TestClient

from backend.api.main import app


client = TestClient(app)


def test_confirm_test_payment_requires_auth(monkeypatch):
    monkeypatch.setenv("PAYMENT_MODE", "test")

    resp = client.post("/api/payments/confirm-test", json={"session_id": "cs_test_missing"})

    assert resp.status_code == 401


def test_confirm_test_payment_disabled_outside_test_mode(monkeypatch):
    monkeypatch.setenv("PAYMENT_MODE", "disabled")

    resp = client.post(
        "/api/payments/confirm-test",
        headers={"X-User-ID": "00000000-0000-0000-0000-000000000001"},
        json={"session_id": "cs_test_missing"},
    )

    assert resp.status_code == 403
