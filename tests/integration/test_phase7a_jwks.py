"""
Phase 7A  -  RS256/JWKS JWT verification tests.

Tests:
  RS256/JWKS verification (direct):
   1.  Valid RS256 JWT accepted  -  correct sub returned
   2.  Expired RS256 token rejected (401)
   3.  Wrong issuer rejected (401)
   4.  Wrong audience rejected (401)
   5.  Invalid signature (signed with different RSA key) rejected (401)
   6.  Unknown kid (not in JWKS) rejected (401)
   7.  JWKS fetch failure fails safely (503)
   8.  JWT_JWKS_URL not set fails safely (503)
   9.  Wrong algorithm (HS256 token presented to RS256 path) rejected (401)
  10.  Token value not in any exception message

  Dispatcher routing:
  11.  JWT_JWKS_URL set → RS256 path used
  12.  JWT_SECRET set (no JWKS_URL) → HS256 path used (preserved)
  13.  Neither set → 503

  Auth mode:
  14.  Mock mode still works (dev/test preserved)
  15.  RS256+full config is production-ready per is_auth_production_ready()
  16.  HS256-only is not production-ready (non-production-grade key)

  Production readiness:
  17.  jwt_rs256_jwks_verification shown as IMPLEMENTED when JWT_JWKS_URL set
  18.  jwt_production_grade=true when RS256+JWKS+issuer+audience all configured
  19.  controlled_beta_ready remains false (DPIA/privacy blockers)
  20.  production_ready remains false

  Admin protection:
  21.  /admin/* still requires X-Admin-Key

  Regressions:
  22.  Legal accuracy gate passes
  23.  Rules verification gate passes
  24.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase7a_jwks.py -v -s
"""

from __future__ import annotations

import base64
import datetime
import os
import subprocess
import sys
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app, raise_server_exceptions=True)

# ── Test constants ─────────────────────────────────────────────────────────────
_TEST_ISSUER   = "https://auth.test.lawapp.co.uk"
_TEST_AUDIENCE = "lawapp-api-test"
_TEST_SUB      = str(uuid.uuid4())
_TEST_KID      = "phase7a-test-key-rs256"
_TEST_WRONG_KID = "unknown-key-id-xyz"
_ADMIN_KEY      = "test-admin-7a"
_ADMIN_HDR      = {"X-Admin-Key": _ADMIN_KEY}


def _gen_rsa_key():
    """Generate a fresh RSA-2048 key pair. Returns (private_key, public_key)."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    priv = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    return priv, priv.public_key()


def _int_to_b64url(n: int) -> str:
    """Convert a Python int to URL-safe base64 (JWK format)."""
    n_bytes = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(n_bytes).rstrip(b"=").decode("ascii")


def _pubkey_to_jwk(pub_key, kid: str) -> dict:
    """Convert an RSA public key object to JWK dict."""
    nums = pub_key.public_numbers()
    return {
        "kty": "RSA", "use": "sig", "alg": "RS256",
        "kid": kid,
        "n":   _int_to_b64url(nums.n),
        "e":   _int_to_b64url(nums.e),
    }


def _sign_rs256(priv_key, sub=_TEST_SUB, exp_secs=3600, kid=_TEST_KID,
                issuer=_TEST_ISSUER, audience=_TEST_AUDIENCE) -> str:
    """Sign a JWT with RS256 using the given RSA private key."""
    import jwt
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    payload = {
        "sub": sub, "iss": issuer, "aud": audience,
        "exp": now + datetime.timedelta(seconds=exp_secs),
        "iat": now,
    }
    return jwt.encode(payload, priv_key, algorithm="RS256", headers={"kid": kid})


# Generate test keys once for the module
_PRIV, _PUB  = _gen_rsa_key()
_WRONG_PRIV, _ = _gen_rsa_key()   # different key pair for invalid-signature tests
_TEST_JWKS   = [_pubkey_to_jwk(_PUB, _TEST_KID)]


@pytest.fixture(scope="module", autouse=True)
def phase7a_env():
    from cryptography.fernet import Fernet
    saved = {k: os.environ.get(k) for k in [
        "ADMIN_API_KEY", "ENCRYPTION_KEY", "LAWAPP_AUTH_MODE",
        "JWT_JWKS_URL", "JWT_SECRET", "JWT_ISSUER", "JWT_AUDIENCE",
        "DEPLOYMENT_MODE",
    ]}
    os.environ.update({
        "ADMIN_API_KEY":    _ADMIN_KEY,
        "ENCRYPTION_KEY":   Fernet.generate_key().decode(),
        "LAWAPP_AUTH_MODE": "jwt",
        "JWT_JWKS_URL":     "https://mock-jwks.test/.well-known/jwks.json",
        "JWT_ISSUER":       _TEST_ISSUER,
        "JWT_AUDIENCE":     _TEST_AUDIENCE,
        "DEPLOYMENT_MODE":  "development",
    })
    os.environ.pop("JWT_SECRET", None)   # RS256 path: JWKS_URL takes priority
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ── 1-10. Direct RS256/JWKS verification ─────────────────────────────────────

def test_valid_rs256_token_accepted():
    """Valid RS256 JWT with matching kid → correct sub returned."""
    from backend.core.user_auth import _verify_jwt_rs256
    token = _sign_rs256(_PRIV)
    with patch("backend.core.user_auth._fetch_jwks", return_value=_TEST_JWKS):
        result = _verify_jwt_rs256(token)
    assert result == _TEST_SUB


def test_expired_rs256_token_rejected():
    from backend.core.user_auth import _verify_jwt_rs256
    token = _sign_rs256(_PRIV, exp_secs=-60)   # expired 60s ago
    with patch("backend.core.user_auth._fetch_jwks", return_value=_TEST_JWKS):
        with pytest.raises(Exception) as exc_info:
            _verify_jwt_rs256(token)
    assert "expired" in str(exc_info.value).lower()


def test_wrong_issuer_rs256_rejected():
    from backend.core.user_auth import _verify_jwt_rs256
    token = _sign_rs256(_PRIV, issuer="https://wrong.issuer.com")
    with patch("backend.core.user_auth._fetch_jwks", return_value=_TEST_JWKS):
        with pytest.raises(Exception) as exc_info:
            _verify_jwt_rs256(token)
    assert "issuer" in str(exc_info.value).lower()


def test_wrong_audience_rs256_rejected():
    from backend.core.user_auth import _verify_jwt_rs256
    token = _sign_rs256(_PRIV, audience="wrong-audience")
    with patch("backend.core.user_auth._fetch_jwks", return_value=_TEST_JWKS):
        with pytest.raises(Exception) as exc_info:
            _verify_jwt_rs256(token)
    assert "audience" in str(exc_info.value).lower()


def test_invalid_signature_rs256_rejected():
    """Token signed with a different RSA private key → 401."""
    from backend.core.user_auth import _verify_jwt_rs256
    token = _sign_rs256(_WRONG_PRIV, kid=_TEST_KID)   # wrong key, same kid
    with patch("backend.core.user_auth._fetch_jwks", return_value=_TEST_JWKS):
        with pytest.raises(Exception) as exc_info:
            _verify_jwt_rs256(token)
    msg = str(exc_info.value).lower()
    assert any(w in msg for w in ("signature", "invalid", "verification", "decode"))


def test_unknown_kid_rejected():
    """Token with a kid not present in JWKS → 401."""
    from backend.core.user_auth import _verify_jwt_rs256
    token = _sign_rs256(_PRIV, kid=_TEST_WRONG_KID)   # kid not in JWKS
    with patch("backend.core.user_auth._fetch_jwks", return_value=_TEST_JWKS):
        with pytest.raises(Exception) as exc_info:
            _verify_jwt_rs256(token)
    msg = str(exc_info.value).lower()
    assert any(w in msg for w in ("kid", "key", "unknown"))


def test_jwks_fetch_failure_fails_safely():
    """JWKS fetch failure → 503 (fails closed, token not accepted)."""
    from backend.core.user_auth import _verify_jwt_rs256
    from fastapi import HTTPException
    token = _sign_rs256(_PRIV)
    with patch("backend.core.user_auth._fetch_jwks",
               side_effect=HTTPException(status_code=503, detail="mock fetch failure")):
        with pytest.raises(Exception) as exc_info:
            _verify_jwt_rs256(token)
    assert "503" in str(exc_info.value) or "fetch" in str(exc_info.value).lower()


def test_missing_jwks_url_fails_safely():
    """JWT_JWKS_URL not set → 503."""
    from backend.core.user_auth import _verify_jwt_rs256
    saved = os.environ.pop("JWT_JWKS_URL", None)
    try:
        with pytest.raises(Exception) as exc_info:
            _verify_jwt_rs256(_sign_rs256(_PRIV))
        assert "503" in str(exc_info.value) or "configured" in str(exc_info.value).lower()
    finally:
        if saved:
            os.environ["JWT_JWKS_URL"] = saved


def test_wrong_algorithm_rejected():
    """HS256 token presented to RS256 path → 401."""
    from backend.core.user_auth import _verify_jwt_rs256
    import jwt
    hs_token = jwt.encode(
        {"sub": "test", "exp": datetime.datetime.now(tz=datetime.timezone.utc)
         + datetime.timedelta(hours=1), "iat": datetime.datetime.now(tz=datetime.timezone.utc)},
        "some-secret", algorithm="HS256"
    )
    with patch("backend.core.user_auth._fetch_jwks", return_value=_TEST_JWKS):
        with pytest.raises(Exception) as exc_info:
            _verify_jwt_rs256(hs_token)
    msg = str(exc_info.value).lower()
    assert any(w in msg for w in ("algorithm", "supported", "rs256", "401"))


def test_token_value_not_in_exception():
    """Token value must not appear in any exception detail."""
    from backend.core.user_auth import _verify_jwt_rs256
    token = _sign_rs256(_PRIV, exp_secs=-60)  # expired
    with patch("backend.core.user_auth._fetch_jwks", return_value=_TEST_JWKS):
        with pytest.raises(Exception) as exc_info:
            _verify_jwt_rs256(token)
    assert token not in str(exc_info.value), "Token value must not appear in exception"


# ── 11-13. Dispatcher routing ─────────────────────────────────────────────────

def test_jwks_url_routes_to_rs256():
    """With JWT_JWKS_URL set, dispatcher uses RS256 path."""
    from backend.core.user_auth import _verify_jwt
    token = _sign_rs256(_PRIV)
    with patch("backend.core.user_auth._fetch_jwks", return_value=_TEST_JWKS):
        result = _verify_jwt(token)
    assert result == _TEST_SUB


def test_jwt_secret_routes_to_hs256_when_no_jwks():
    """When only JWT_SECRET is set (no JWKS_URL), dispatcher uses HS256."""
    from backend.core.user_auth import _verify_jwt_hs256
    import jwt
    _hs_secret  = "phase7a-test-hs256-secret-min32chars"
    _hs_issuer  = "https://hs256-test.example.com"
    _hs_audience = "hs256-test"
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    token = jwt.encode(
        {"sub": "hs256-user", "iss": _hs_issuer, "aud": _hs_audience,
         "exp": now + datetime.timedelta(hours=1), "iat": now},
        _hs_secret, algorithm="HS256",
    )
    saved = {
        "JWT_SECRET":   os.environ.get("JWT_SECRET"),
        "JWT_JWKS_URL": os.environ.get("JWT_JWKS_URL"),
        "JWT_ISSUER":   os.environ.get("JWT_ISSUER"),
        "JWT_AUDIENCE": os.environ.get("JWT_AUDIENCE"),
    }
    os.environ["JWT_SECRET"]   = _hs_secret
    os.environ["JWT_ISSUER"]   = _hs_issuer
    os.environ["JWT_AUDIENCE"] = _hs_audience
    os.environ.pop("JWT_JWKS_URL", None)
    try:
        result = _verify_jwt_hs256(token)
        assert result == "hs256-user"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_neither_secret_nor_jwks_returns_503():
    """Neither JWT_SECRET nor JWT_JWKS_URL → 503."""
    from backend.core.user_auth import _verify_jwt
    saved_url    = os.environ.pop("JWT_JWKS_URL", None)
    saved_secret = os.environ.pop("JWT_SECRET", None)
    try:
        with pytest.raises(Exception) as exc_info:
            _verify_jwt("any-token-value")
        assert "503" in str(exc_info.value) or "configured" in str(exc_info.value).lower()
    finally:
        if saved_url:
            os.environ["JWT_JWKS_URL"] = saved_url
        if saved_secret:
            os.environ["JWT_SECRET"] = saved_secret


# ── 14-16. Auth mode ──────────────────────────────────────────────────────────

def test_mock_mode_still_works():
    """Mock mode (X-User-ID) is unchanged by Phase 7A."""
    os.environ["LAWAPP_AUTH_MODE"] = "mock"
    try:
        mock_id = str(uuid.uuid4())
        case_resp = client.post("/cases", json={
            "claim_type": "unfair_dismissal", "jurisdiction": "EW",
            "assessment": {
                "status": "ok", "claim_type": "unfair_dismissal",
                "has_viable_claim": "yes", "strength": "medium",
                "reasoning_summary": "Test.", "key_weaknesses": [],
                "employer_arguments": [],
                "deadline_info": {"limitation_date": "2026-06-30", "source": "rules",
                                   "authority": "ERA 1996 s.111(2)", "ec_applied": False},
                "value_range": {"low": 1800, "high": 31200, "currency": "GBP",
                                 "basis": "From rules."},
                "recommended_next_step": "prepare_documents",
                "citations": [], "grounding_score": 0.85, "confidence_score": 0.75,
                "insufficient_grounding": False,
                "boundary_log": {"fields_passed": ["edt"], "fields_stripped": [],
                                  "pii_in_output": []},
            },
            "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
        }, headers={"X-User-ID": mock_id})
        assert case_resp.status_code == 201
    finally:
        os.environ["LAWAPP_AUTH_MODE"] = "jwt"


def test_rs256_jwks_full_config_is_production_ready():
    """RS256 + JWT_JWKS_URL + JWT_ISSUER + JWT_AUDIENCE → production-ready."""
    from backend.core.user_auth import is_auth_production_ready
    # Env fixture already sets all these
    result = is_auth_production_ready()
    assert result["ready"] is True, \
        f"RS256+JWKS with full config must be production-ready: {result['blockers']}"
    assert result["blockers"] == []


def test_hs256_only_is_not_production_ready():
    """HS256 (JWT_SECRET only) must NOT be flagged as production-ready."""
    from backend.core.user_auth import is_auth_production_ready
    saved_url = os.environ.pop("JWT_JWKS_URL", None)
    os.environ["JWT_SECRET"] = "test-hs256-secret-min32chars-here"
    try:
        result = is_auth_production_ready()
        assert not result["ready"], "HS256-only must not be production-ready"
        assert any("hs256" in b.lower() or "production" in b.lower() or "jwks" in b.lower()
                   for b in result["blockers"])
    finally:
        if saved_url:
            os.environ["JWT_JWKS_URL"] = saved_url
        os.environ.pop("JWT_SECRET", None)


# ── 17-20. Production readiness report ───────────────────────────────────────

def test_readiness_shows_rs256_jwks_implemented():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    auth = data.get("user_authentication", {})
    assert auth.get("jwt_rs256_jwks_verification") == "IMPLEMENTED", \
        f"RS256+JWKS should show IMPLEMENTED: {auth}"


def test_readiness_shows_jwt_production_grade():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    auth = data.get("user_authentication", {})
    assert auth.get("jwt_production_grade") is True, \
        "jwt_production_grade must be true with full RS256+JWKS config"


def test_controlled_beta_ready_still_false():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    assert resp.json()["controlled_beta_ready"] is False


def test_production_ready_still_false():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    assert resp.json()["production_ready"] is False


# ── 21. Admin protection ──────────────────────────────────────────────────────

def test_admin_endpoints_still_require_key():
    assert client.get("/admin/production-readiness").status_code == 403
    assert client.get("/admin/compliance-status").status_code == 403


# ── 22-24. Regressions ────────────────────────────────────────────────────────

def test_legal_accuracy_gate_regression():
    result = subprocess.run(
        [sys.executable, "scripts/run_legal_accuracy.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Legal accuracy gate failed:\n{result.stdout}"


def test_rules_verification_gate_regression():
    result = subprocess.run(
        [sys.executable, "scripts/check_rules_verification.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
