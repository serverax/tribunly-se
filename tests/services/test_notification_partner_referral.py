from __future__ import annotations

import json

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient


_SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend"
    / "services"
    / "lawapp-notification-service"
    / "main.py"
)
_SPEC = importlib.util.spec_from_file_location("lawapp_notification_service_main", _SERVICE_PATH)
assert _SPEC and _SPEC.loader
notification_service = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(notification_service)
app = notification_service.app


class _FakeCursor:
    def __init__(self, partner: dict):
        self._partner = partner
        self.executed: list[tuple[str, list[str]]] = []

    def execute(self, query: str, params: list[str]) -> None:
        self.executed.append((query, params))

    def fetchone(self) -> dict:
        return self._partner

    def close(self) -> None:
        return None


class _FakeConn:
    def __init__(self, partner: dict):
        self.cursor_obj = _FakeCursor(partner)
        self.closed = False

    def cursor(self, cursor_factory=None):  # noqa: ANN001
        return self.cursor_obj

    def close(self) -> None:
        self.closed = True


class _FakeRedis:
    def __init__(self):
        self.queue: list[tuple[str, str]] = []
        self.closed = False

    def rpush(self, key: str, value: str) -> None:
        self.queue.append((key, value))

    def close(self) -> None:
        self.closed = True


def test_partner_referral_queues_registry_backed_notification(monkeypatch):
    partner = {
        "id": "partner-1",
        "name": "Demo Employment Panel",
        "webhook_url": None,
        "notify_email": "panel@example.com",
        "active": True,
    }
    fake_conn = _FakeConn(partner)
    fake_redis = _FakeRedis()

    monkeypatch.setattr(notification_service, "get_db_connection", lambda: fake_conn)
    monkeypatch.setattr(notification_service, "get_redis_client", lambda: fake_redis)

    client = TestClient(app)

    response = client.post(
        "/api/notifications/partner-referral",
        params={
            "partner_slug": "demo-panel",
            "referral_id": "ref-123",
            "matter_id": "matter-456",
        },
        headers={"X-Trace-ID": "trace-partner-referral"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "accepted"
    assert data["partner_slug"] == "demo-panel"
    assert data["referral_id"] == "ref-123"
    assert data["email_queued"] is True
    assert data["webhook_configured"] is False

    assert fake_conn.cursor_obj.executed
    assert fake_redis.queue
    queue_key, payload = fake_redis.queue[0]
    assert queue_key == "lawapp:email_queue"
    job = json.loads(payload)
    assert job["type"] == "partner_referral"
    assert job["partner_slug"] == "demo-panel"
    assert job["referral_id"] == "ref-123"
    assert job["matter_id"] == "matter-456"
    assert job["email"] == "panel@example.com"
