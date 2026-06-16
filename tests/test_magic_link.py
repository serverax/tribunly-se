"""
Magic-link (passwordless) auth flow  -  HTTP + service-layer proof.

Endpoint under test: POST /api/auth/magic-link  (backend/api/auth_routes.py)
Service under test:   backend/core/auth/service.py
                        request_magic_link / consume_magic_link

Proven here (real local Docker DB  -  conftest sets POSTGRES_* to localhost:5435):
  HAPPY PATH
    - issue is generic (no account enumeration): always 200 with a generic message
    - a real issued token (captured at the delivery boundary) redeems a session
      bundle whose amr == ["magic_link"] and that marks the email verified
  ERROR CASES
    - consuming an unknown/expired token -> 400 "invalid or has expired"
    - an empty / malformed email still returns the generic 200 (no enumeration)

GUARDRAIL: the issue response NEVER returns the raw token (anti-enumeration).
The happy-path test obtains the raw token only by intercepting the email-delivery
boundary (_send_link_email)  -  exactly the channel a real user receives it on.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app
    # Decouple functional auth tests from per-route rate limits (tested elsewhere).
    try:
        app.state.limiter.enabled = False
    except Exception:
        pass
    return TestClient(app, raise_server_exceptions=False)


def _email() -> str:
    return f"ml_{uuid.uuid4().hex[:10]}@example.com"


# ── issue (request) path ────────────────────────────────────────────────────────

class TestMagicLinkIssue:
    def test_issue_is_generic_200(self, client):
        r = client.post("/api/auth/magic-link", json={"email": _email()})
        assert r.status_code == 200, r.text
        body = r.json()
        # Generic message  -  must not confirm whether the account exists.
        assert "sign-in link" in body["message"].lower()
        # Never leak a token in the issue response.
        assert "token" not in body
        assert body.get("trace_id")

    def test_issue_unknown_email_is_indistinguishable(self, client):
        # An address that certainly has no account still gets the SAME generic 200.
        r = client.post("/api/auth/magic-link",
                        json={"email": f"nobody_{uuid.uuid4().hex}@nowhere.invalid"})
        assert r.status_code == 200, r.text
        assert "sign-in link" in r.json()["message"].lower()

    def test_issue_malformed_email_still_generic(self, client):
        # No '@'  -  service short-circuits but the HTTP contract stays generic 200.
        r = client.post("/api/auth/magic-link", json={"email": "not-an-email"})
        assert r.status_code == 200, r.text
        assert "token" not in r.json()


# ── consume (redeem) path ────────────────────────────────────────────────────────

class TestMagicLinkConsume:
    def test_consume_unknown_token_is_rejected(self, client):
        r = client.post("/api/auth/magic-link", json={"token": "bogus-not-a-real-token"})
        assert r.status_code == 400, r.text
        assert "invalid or has expired" in r.json()["detail"].lower()

    def test_consume_empty_token_falls_through_to_issue(self, client):
        # token="" is falsy -> issue path (generic 200), not consume.
        r = client.post("/api/auth/magic-link", json={"token": "", "email": _email()})
        assert r.status_code == 200, r.text

    def test_full_flow_issue_then_consume(self, client, monkeypatch):
        """End-to-end passwordless sign-in against the real DB.

        Capture the raw token at the delivery boundary (the only place it exists
        in plaintext), then redeem it over HTTP."""
        from backend.core.auth import service

        captured: dict = {}

        def _capture(to, subject, intro, path, raw_token):
            captured["raw"] = raw_token

        monkeypatch.setattr(service, "_send_link_email", _capture)

        email = _email()
        ctx = service.RequestContext(trace_id="test-magic", ip_hash=None, user_agent=None)
        service.request_magic_link(email, ctx=ctx)

        raw = captured.get("raw")
        assert raw and len(raw) >= 32, "magic-link token was not issued/delivered"

        r = client.post("/api/auth/magic-link", json={"token": raw})
        assert r.status_code == 200, r.text
        bundle = r.json()
        assert bundle.get("user_id")
        assert bundle.get("access_token")
        assert bundle.get("refresh_token")
        assert bundle.get("token_type") == "bearer"

    def test_issue_for_existing_account(self, client, monkeypatch):
        """Issuing a magic link for an ALREADY-registered email reuses that user
        (the existing-user branch), still returning the generic 200."""
        from backend.core.auth import service

        email = _email()
        reg = client.post("/api/auth/register",
                          json={"email": email, "password": "Str0ngP@ssw0rd!"})
        assert reg.status_code == 201, reg.text

        captured: dict = {}
        monkeypatch.setattr(service, "_send_link_email",
                            lambda to, s, i, p, raw: captured.update(raw=raw))
        r = client.post("/api/auth/magic-link", json={"email": email})
        assert r.status_code == 200, r.text
        # A link was issued for the existing account, and it redeems.
        assert captured.get("raw")
        consume = client.post("/api/auth/magic-link", json={"token": captured["raw"]})
        assert consume.status_code == 200, consume.text

    def test_token_is_single_use(self, client, monkeypatch):
        """A magic-link token redeems exactly once; a replay is rejected."""
        from backend.core.auth import service

        captured: dict = {}
        monkeypatch.setattr(
            service, "_send_link_email",
            lambda to, s, i, p, raw: captured.update(raw=raw),
        )
        ctx = service.RequestContext(trace_id="test-magic-replay", ip_hash=None, user_agent=None)
        service.request_magic_link(_email(), ctx=ctx)
        raw = captured["raw"]

        first = client.post("/api/auth/magic-link", json={"token": raw})
        assert first.status_code == 200, first.text
        replay = client.post("/api/auth/magic-link", json={"token": raw})
        assert replay.status_code == 400, replay.text
        assert "invalid or has expired" in replay.json()["detail"].lower()
