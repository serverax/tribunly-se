"""
/api/auth/{google,microsoft,apple,linkedin} — real OIDC ID-token verification.

The `oidc` fixture installs an in-test RSA key as the provider JWKS and signs
ID tokens with the matching private key, so the full verify path (signature →
issuer → audience → expiry) is exercised with real cryptography.
"""

from __future__ import annotations

import pytest

PROVIDERS = ["google", "microsoft", "apple", "linkedin"]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_oauth_login_creates_user_and_session(provider, client, oidc, db_query):
    oidc.configure(provider)
    sub = f"{provider}-sub-{provider}-001"
    email = f"{provider}user{abs(hash(sub))}@example.com"
    id_token = oidc.make_token(provider, sub=sub, email=email, name="OAuth User")

    resp = client.post(f"/api/auth/{provider}", json={"id_token": id_token})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["email_verified"] is True
    assert body["trace_id"]

    link = db_query("SELECT user_id FROM oauth_identities WHERE provider=%s AND subject=%s",
                    (provider, sub), fetch="one")
    assert link is not None


def test_oauth_same_subject_returns_same_user(client, oidc, db_query):
    oidc.configure("google")
    sub = "google-stable-sub-777"
    t1 = oidc.make_token("google", sub=sub, email="stable777@example.com")
    t2 = oidc.make_token("google", sub=sub, email="stable777@example.com")
    u1 = client.post("/api/auth/google", json={"id_token": t1}).json()["user_id"]
    u2 = client.post("/api/auth/google", json={"id_token": t2}).json()["user_id"]
    assert u1 == u2
    n = db_query("SELECT count(*) FROM oauth_identities WHERE provider='google' AND subject=%s",
                 (sub,), fetch="one")[0]
    assert n == 1


# ── token validation negatives ───────────────────────────────────────────────

def test_oauth_wrong_audience_rejected(client, oidc):
    oidc.configure("google", client_id="the-real-client-id")
    bad = oidc.make_token("google", aud="some-other-app", email="x@example.com")
    assert client.post("/api/auth/google", json={"id_token": bad}).status_code == 401


def test_oauth_expired_token_rejected(client, oidc):
    oidc.configure("google")
    expired = oidc.make_token("google", email="x@example.com", exp_delta_seconds=-60)
    assert client.post("/api/auth/google", json={"id_token": expired}).status_code == 401


def test_oauth_wrong_issuer_rejected(client, oidc):
    oidc.configure("google")
    bad = oidc.make_token("google", iss="https://evil.example.com", email="x@example.com")
    assert client.post("/api/auth/google", json={"id_token": bad}).status_code == 401


def test_oauth_tampered_signature_rejected(client, oidc):
    oidc.configure("google")
    tok = oidc.make_token("google", email="x@example.com")
    parts = tok.split(".")
    parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]   # corrupt the signature
    tampered = ".".join(parts)
    assert client.post("/api/auth/google", json={"id_token": tampered}).status_code == 401


def test_oauth_provider_not_configured_is_503(client, monkeypatch):
    # No client id configured for apple → fail closed, never fake success.
    monkeypatch.delenv("OAUTH_APPLE_CLIENT_ID", raising=False)
    resp = client.post("/api/auth/apple", json={"id_token": "anything"})
    assert resp.status_code == 503


# ── providers listing ────────────────────────────────────────────────────────

def test_providers_endpoint_reports_status(client, monkeypatch):
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "configured-client")
    monkeypatch.delenv("OAUTH_APPLE_CLIENT_ID", raising=False)
    body = client.get("/api/auth/providers").json()
    names = {p["name"]: p for p in body["providers"]}
    assert names["email_password"]["enabled"] is True
    assert names["magic_link"]["enabled"] is True
    assert names["google"]["enabled"] is True
    assert names["apple"]["enabled"] is False
    # blocked providers are never advertised
    assert "facebook" not in names and "tiktok" not in names and "twitter" not in names
