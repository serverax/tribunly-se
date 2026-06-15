from fastapi.testclient import TestClient
from psycopg2 import errors as pg_errors

from backend.api.main import app


client = TestClient(app)


class _BrokenCursor:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, *_args, **_kwargs):
        raise pg_errors.UndefinedTable("relation cases does not exist")


class _BrokenConnection:
    def __init__(self):
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _BrokenCursor()

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_save_case_reports_schema_not_ready(monkeypatch):
    conn = _BrokenConnection()
    monkeypatch.setattr("backend.api.main.get_connection", lambda: conn)

    resp = client.post(
        "/cases",
        headers={"X-User-ID": "11111111-1111-4111-8111-111111111111"},
        json={
            "claim_type": "unfair_dismissal",
            "jurisdiction": "EW",
            "assessment": {"status": "ok"},
            "key_dates": {"edt": "2026-05-01", "deadline_date": "2026-07-31"},
        },
    )

    assert resp.status_code == 503
    assert "schema is not ready" in resp.text
    assert conn.rolled_back is True
    assert conn.closed is True
