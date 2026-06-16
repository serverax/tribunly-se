"""
Auth session lifecycle  -  refresh / logout / verify-email / password-reset.

Endpoints (backend/api/auth_routes.py, prefix /api/auth):
  POST /api/auth/refresh        POST /api/auth/logout
  POST /api/auth/verify-email   POST /api/auth/password-reset

These complete the email/password + magic-link auth surface. Single-use tokens
(email-verify, password-reset) are captured at the delivery boundary
(_send_link_email)  -  the same channel a real user receives them on.

Proven (conftest -> localhost:5435 lawapp DB):
  REFRESH
    - a valid refresh token rotates to a fresh session bundle
    - replaying a rotated (already-used) refresh token is rejected (reuse defence)
  LOGOUT
    - logout with a refresh token succeeds; that token can no longer refresh
  VERIFY-EMAIL
    - the token delivered at registration verifies the email; a bogus token -> 400
  PASSWORD-RESET
    - request is generic (no enumeration); confirm with the delivered token sets a
      new password that then logs in
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

_PASSWORD = "Str0ngP@ssw0rd!"


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app
    try:
        app.state.limiter.enabled = False
    except Exception:
        pass
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def capture_tokens(monkeypatch):
    """Capture every single-use token delivered via the email boundary."""
    from backend.core.auth import service
    box = {"tokens": []}

    def _capture(to, subject, intro, path, raw_token):
        box["tokens"].append({"subject": subject, "raw": raw_token})

    monkeypatch.setattr(service, "_send_link_email", _capture)
    return box


def _email() -> str:
    return f"flow_{uuid.uuid4().hex[:10]}@example.com"


def _register(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": _PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()


# ── refresh ───────────────────────────────────────────────────────────────────────

class TestRefresh:
    def test_valid_refresh_rotates_session(self, client):
        bundle = _register(client, _email())
        r = client.post("/api/auth/refresh", json={"refresh_token": bundle["refresh_token"]})
        assert r.status_code == 200, r.text
        new = r.json()
        assert new["refresh_token"] != bundle["refresh_token"]  # rotated
        assert new["access_token"]

    def test_replayed_rotated_token_is_rejected(self, client):
        bundle = _register(client, _email())
        old = bundle["refresh_token"]
        first = client.post("/api/auth/refresh", json={"refresh_token": old})
        assert first.status_code == 200, first.text
        # Replaying the now-rotated token is reuse -> rejected.
        replay = client.post("/api/auth/refresh", json={"refresh_token": old})
        assert replay.status_code in (400, 401), replay.text

    def test_unknown_refresh_token_is_rejected(self, client):
        r = client.post("/api/auth/refresh", json={"refresh_token": "not-a-real-token"})
        assert r.status_code in (400, 401), r.text


# ── logout ──────────────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_with_refresh_token(self, client):
        bundle = _register(client, _email())
        r = client.post("/api/auth/logout", json={"refresh_token": bundle["refresh_token"]})
        assert r.status_code == 200, r.text
        assert r.json()["logged_out"] is True

    def test_logged_out_token_cannot_refresh(self, client):
        bundle = _register(client, _email())
        client.post("/api/auth/logout", json={"refresh_token": bundle["refresh_token"]})
        r = client.post("/api/auth/refresh", json={"refresh_token": bundle["refresh_token"]})
        assert r.status_code in (400, 401), r.text

    def test_logout_requires_a_token_or_bearer(self, client):
        r = client.post("/api/auth/logout", json={})
        assert r.status_code == 400, r.text

    def test_logout_all_sessions_with_bearer(self, client):
        bundle = _register(client, _email())
        r = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {bundle['access_token']}"},
            json={"all_sessions": True},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["logged_out"] is True
        assert body["scope"] == "all"

    def test_logout_all_requires_bearer(self, client):
        # all_sessions without a Bearer access token -> 401.
        r = client.post("/api/auth/logout", json={"all_sessions": True})
        assert r.status_code == 401, r.text


# ── verify-email ──────────────────────────────────────────────────────────────────

class TestVerifyEmail:
    def test_registration_token_verifies_email(self, client, capture_tokens):
        _register(client, _email())
        verify = next((t for t in capture_tokens["tokens"] if "verify" in t["subject"].lower()), None)
        assert verify, "registration should deliver an email-verify token"
        r = client.post("/api/auth/verify-email", json={"token": verify["raw"]})
        assert r.status_code == 200, r.text

    def test_bogus_verify_token_is_rejected(self, client):
        r = client.post("/api/auth/verify-email", json={"token": "bogus-verify-token"})
        assert r.status_code == 400, r.text


# ── password-reset ────────────────────────────────────────────────────────────────

class TestPasswordReset:
    def test_request_is_generic(self, client):
        r = client.post("/api/auth/password-reset", json={"email": _email()})
        assert r.status_code == 200, r.text
        assert "reset" in r.json()["message"].lower() or "link" in r.json()["message"].lower()

    def test_confirm_sets_a_new_password(self, client, capture_tokens):
        email = _email()
        _register(client, email)
        capture_tokens["tokens"].clear()  # drop the registration verify token

        req = client.post("/api/auth/password-reset", json={"email": email})
        assert req.status_code == 200, req.text
        reset = next((t for t in capture_tokens["tokens"] if "reset" in t["subject"].lower()), None)
        assert reset, "a reset token should be delivered for a known account"

        new_password = "N3wStr0ng!pass"
        confirm = client.post("/api/auth/password-reset",
                              json={"token": reset["raw"], "new_password": new_password})
        assert confirm.status_code == 200, confirm.text

        # The new password now logs in; the old one no longer does.
        ok = client.post("/api/auth/login", json={"email": email, "password": new_password})
        assert ok.status_code == 200, ok.text
        old = client.post("/api/auth/login", json={"email": email, "password": _PASSWORD})
        assert old.status_code == 401, old.text
