"""
Shared fixtures for the /api/auth/* test suite.

Runs against the live local Docker DB (configured by the root tests/conftest.py)
in LAWAPP_AUTH_MODE=mock with the in-memory email backend (default under pytest).

Fixtures:
  client        -  FastAPI TestClient bound to the real app.
  unique_email  -  a fresh random email per call.
  db_query      -  run a parametrised SQL query against the live DB.
  email_outbox  -  the in-memory auth-email outbox (cleared each test).
  oidc          -  factory that mints provider ID tokens + installs a fake JWKS,
                 so OAuth verification is exercised end-to-end with real crypto.
"""

from __future__ import annotations

import datetime as _dt
import json
import uuid

import jwt as _jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from types import SimpleNamespace

from backend.api.main import app
from backend.api import auth_routes as _auth_routes
from backend.core.auth import email as email_mod
from backend.core.auth import providers as providers_mod
from ingestion.db import get_connection

# Rate limiting is a cross-cutting control proven separately; disable it here so
# the many requests this suite makes from a single test-client IP do not trip the
# per-IP limits and make assertions flaky. Production keeps limits enabled.
_auth_routes._limiter.enabled = False
try:
    app.state.limiter.enabled = False
except Exception:
    pass

client_instance = TestClient(app)


@pytest.fixture
def client() -> TestClient:
    return client_instance


@pytest.fixture
def unique_email():
    def _make() -> str:
        return f"auth-test-{uuid.uuid4()}@example.com"
    return _make


@pytest.fixture
def db_query():
    def _run(sql: str, params: tuple = (), *, fetch: str = "all"):
        conn = get_connection()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "none":
                    return None
                return cur.fetchall()
        finally:
            conn.close()
    return _run


@pytest.fixture
def email_outbox():
    email_mod.clear_outbox()
    yield email_mod.get_outbox()
    email_mod.clear_outbox()


def _extract_token_from_outbox(outbox, *, subject_contains: str) -> str:
    for msg in reversed(outbox):
        if subject_contains.lower() in msg.subject.lower():
            # body contains a "...?token=<raw>" URL
            for part in msg.text_body.split():
                if "token=" in part:
                    return part.split("token=", 1)[1].strip()
    raise AssertionError(f"No email with subject containing {subject_contains!r} in outbox")


@pytest.fixture
def extract_token():
    return _extract_token_from_outbox


@pytest.fixture
def oidc(monkeypatch):
    """
    Provider ID-token factory. Generates an RSA keypair, installs the public key
    as the provider JWKS (monkeypatching providers._fetch_jwks), and returns a
    helper that signs ID tokens with the matching private key.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    kid = "test-key-1"
    jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk.update({"kid": kid, "alg": "RS256", "use": "sig"})

    monkeypatch.setattr(providers_mod, "_fetch_jwks", lambda url: [jwk])

    ISSUERS = {
        "google": "https://accounts.google.com",
        "microsoft": "https://login.microsoftonline.com/common/v2.0",
        "apple": "https://appleid.apple.com",
        "linkedin": "https://www.linkedin.com/oauth",
    }

    def configure(provider: str, client_id: str = "test-client-id"):
        monkeypatch.setenv(f"OAUTH_{provider.upper()}_CLIENT_ID", client_id)

    def make_token(
        provider: str,
        *,
        sub: str = "provider-subject-123",
        aud: str = "test-client-id",
        iss: str | None = None,
        email: str | None = None,
        email_verified: bool = True,
        name: str | None = None,
        exp_delta_seconds: int = 3600,
    ) -> str:
        now = _dt.datetime.now(_dt.timezone.utc)
        payload: dict = {
            "iss": iss or ISSUERS[provider],
            "aud": aud,
            "sub": sub,
            "iat": now,
            "exp": now + _dt.timedelta(seconds=exp_delta_seconds),
        }
        if email is not None:
            payload["email"] = email
            payload["email_verified"] = email_verified
        if name is not None:
            payload["name"] = name
        return _jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})

    return SimpleNamespace(configure=configure, make_token=make_token, issuers=ISSUERS)
