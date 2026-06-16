"""
Email/password auth flow  -  HTTP proof against the real local DB.

Endpoints under test (backend/api/auth_routes.py, prefix /api/auth):
  POST /api/auth/register   POST /api/auth/login

Proven (conftest -> localhost:5435 lawapp DB):
  HAPPY PATH
    - register a new account -> 201 + session bundle (user_id, access/refresh tokens)
    - login with those credentials -> 200 + a fresh session bundle
  ERROR CASES
    - duplicate email           -> 409 "Email already registered."
    - weak password             -> 400 (min length enforced)
    - malformed email           -> 400 "A valid email address is required."
    - wrong / unknown password  -> 401 "Invalid email or password." (no enumeration)
    - missing required field    -> 422 (request validation)

GUARDRAIL: a failed login returns the SAME generic 401 whether the account
exists or not  -  no account enumeration via the login endpoint.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

_PASSWORD = "Str0ngP@ssw0rd!"  # satisfies the strength policy (>= 10 chars, mixed)


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app
    try:
        app.state.limiter.enabled = False
    except Exception:
        pass
    return TestClient(app, raise_server_exceptions=False)


def _email() -> str:
    return f"ep_{uuid.uuid4().hex[:10]}@example.com"


def _assert_bundle(body: dict) -> None:
    assert body.get("user_id")
    assert body.get("access_token")
    assert body.get("refresh_token")
    assert body.get("token_type") == "bearer"


# ── register ─────────────────────────────────────────────────────────────────────

class TestRegister:
    def test_register_new_account_returns_bundle(self, client):
        r = client.post("/api/auth/register",
                        json={"email": _email(), "password": _PASSWORD})
        assert r.status_code == 201, r.text
        _assert_bundle(r.json())

    def test_duplicate_email_is_rejected(self, client):
        email = _email()
        first = client.post("/api/auth/register", json={"email": email, "password": _PASSWORD})
        assert first.status_code == 201, first.text
        dup = client.post("/api/auth/register", json={"email": email, "password": _PASSWORD})
        assert dup.status_code == 409, dup.text
        assert "already registered" in dup.json()["detail"].lower()

    def test_weak_password_is_rejected(self, client):
        r = client.post("/api/auth/register", json={"email": _email(), "password": "123"})
        assert r.status_code == 400, r.text
        assert "password" in r.json()["detail"].lower()

    def test_malformed_email_is_rejected(self, client):
        r = client.post("/api/auth/register", json={"email": "not-an-email", "password": _PASSWORD})
        assert r.status_code == 400, r.text
        assert "valid email" in r.json()["detail"].lower()

    def test_missing_password_is_422(self, client):
        r = client.post("/api/auth/register", json={"email": _email()})
        assert r.status_code == 422, r.text


# ── login ─────────────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_with_valid_credentials(self, client):
        email = _email()
        client.post("/api/auth/register", json={"email": email, "password": _PASSWORD})
        r = client.post("/api/auth/login", json={"email": email, "password": _PASSWORD})
        assert r.status_code == 200, r.text
        _assert_bundle(r.json())

    def test_wrong_password_is_401_generic(self, client):
        email = _email()
        client.post("/api/auth/register", json={"email": email, "password": _PASSWORD})
        r = client.post("/api/auth/login", json={"email": email, "password": "Wr0ngP@ssword!"})
        assert r.status_code == 401, r.text
        assert r.json()["detail"] == "Invalid email or password."

    def test_unknown_account_is_401_indistinguishable(self, client):
        r = client.post("/api/auth/login",
                        json={"email": f"ghost_{uuid.uuid4().hex}@example.com",
                              "password": _PASSWORD})
        assert r.status_code == 401, r.text
        # Same message as a wrong password -> no enumeration.
        assert r.json()["detail"] == "Invalid email or password."

    def test_missing_field_is_422(self, client):
        r = client.post("/api/auth/login", json={"email": _email()})
        assert r.status_code == 422, r.text
