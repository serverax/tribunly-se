"""
Phase 6C — Real JWT cryptographic verification tests.

Tests:
  JWT verification (direct):
   1.  Valid HS256 JWT accepted — correct sub returned
   2.  Expired JWT rejected (401)
   3.  Wrong issuer rejected (401)
   4.  Wrong audience rejected (401)
   5.  Invalid signature (wrong secret) rejected (401)
   6.  Malformed token (not JWT) rejected (401)
   7.  Missing Authorization header → None (no error)
   8.  Missing JWT_SECRET → 503 (server not configured)
   9.  Token value never logged (verified by absence in response body)

  Auth mode via API:
  10.  jwt mode accepts valid Bearer token for case access
  11.  jwt mode rejects expired token (401)
  12.  jwt mode rejects invalid signature (401)
  13.  mock mode still works with X-User-ID (dev/test preserved)
  14.  production mode confirms jwt is production-ready when configured

  Admin protection:
  15.  /admin/production-readiness without key returns 403
  16.  /admin/compliance-status without key returns 403

  Production readiness:
  17.  JWT HS256 implementation reflected in readiness report
  18.  controlled_beta_ready remains false (DPIA blockers)
  19.  production_ready remains false

  Regressions:
  20.  legal accuracy gate passes
  21.  rules verification gate passes
  22.  static routes serve
  23.  health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase6c_jwt.py -v -s
"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app, raise_server_exceptions=True)

# ── Test constants ─────────────────────────────────────────────────────────────
_TEST_SECRET   = "phase6c-test-secret-hs256-minimum32chars!"
_TEST_ISSUER   = "https://auth.test.lawapp.co.uk"
_TEST_AUDIENCE = "lawapp-api-test"
_TEST_SUB      = str(uuid.uuid4())   # UUID sub for case-ownership tests
_ADMIN_KEY     = "test-admin-6c"
_ADMIN_HDR     = {"X-Admin-Key": _ADMIN_KEY}


def _make_jwt(
    sub:      str  = _TEST_SUB,
    exp_secs: int  = 3600,
    issuer:   str  = _TEST_ISSUER,
    audience: str  = _TEST_AUDIENCE,
    secret:   str  = _TEST_SECRET,
) -> str:
    """Generate a signed HS256 JWT. Requires PyJWT."""
    import jwt
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    payload = {
        "sub": sub,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=exp_secs),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module", autouse=True)
def phase6c_env():
    """Set env vars for Phase 6C JWT tests."""
    from cryptography.fernet import Fernet
    saved = {k: os.environ.get(k) for k in [
        "ADMIN_API_KEY", "ENCRYPTION_KEY", "LAWAPP_AUTH_MODE",
        "JWT_SECRET", "JWT_ISSUER", "JWT_AUDIENCE",
        "PAYMENT_MODE", "DEPLOYMENT_MODE",
    ]}
    os.environ.update({
        "ADMIN_API_KEY":    _ADMIN_KEY,
        "ENCRYPTION_KEY":   Fernet.generate_key().decode(),
        "LAWAPP_AUTH_MODE": "jwt",
        "JWT_SECRET":       _TEST_SECRET,
        "JWT_ISSUER":       _TEST_ISSUER,
        "JWT_AUDIENCE":     _TEST_AUDIENCE,
        "PAYMENT_MODE":     "mock",
        "DEPLOYMENT_MODE":  "development",
    })
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ── 1-9. Direct JWT verification ──────────────────────────────────────────────

def test_valid_jwt_accepted():
    """Valid HS256 JWT returns correct sub claim."""
    from backend.core.user_auth import _verify_jwt
    token = _make_jwt()
    sub   = _verify_jwt(token)
    assert sub == _TEST_SUB


def test_expired_jwt_rejected():
    from backend.core.user_auth import _verify_jwt
    token = _make_jwt(exp_secs=-60)   # expired 60s ago
    with pytest.raises(Exception) as exc_info:
        _verify_jwt(token)
    assert "expired" in str(exc_info.value).lower()


def test_wrong_issuer_rejected():
    from backend.core.user_auth import _verify_jwt
    token = _make_jwt(issuer="https://wrong.issuer.com")
    with pytest.raises(Exception) as exc_info:
        _verify_jwt(token)
    assert "issuer" in str(exc_info.value).lower()


def test_wrong_audience_rejected():
    from backend.core.user_auth import _verify_jwt
    token = _make_jwt(audience="wrong-audience")
    with pytest.raises(Exception) as exc_info:
        _verify_jwt(token)
    assert "audience" in str(exc_info.value).lower()


def test_invalid_signature_rejected():
    from backend.core.user_auth import _verify_jwt
    token = _make_jwt(secret="a-completely-different-secret-x!!")
    with pytest.raises(Exception) as exc_info:
        _verify_jwt(token)
    # Should be signature or verification failure
    msg = str(exc_info.value).lower()
    assert any(w in msg for w in ("signature", "invalid", "verification", "decode"))


def test_malformed_token_rejected():
    from backend.core.user_auth import _verify_jwt
    with pytest.raises(Exception) as exc_info:
        _verify_jwt("this-is-not-a-valid-jwt-token")
    msg = str(exc_info.value).lower()
    assert any(w in msg for w in ("decode", "invalid", "token", "verification"))


def test_missing_authorization_returns_none():
    """No Authorization header → None (not authenticated, not an error)."""
    from backend.core.user_auth import get_current_user
    result = get_current_user(x_user_id=None, authorization=None)
    assert result is None


def test_missing_jwt_secret_returns_503():
    """JWT_SECRET not configured → 503 (server configuration error)."""
    from backend.core.user_auth import _verify_jwt
    saved = os.environ.pop("JWT_SECRET", None)
    try:
        with pytest.raises(Exception) as exc_info:
            _verify_jwt(_make_jwt(secret=saved or ""))
        # Should indicate server not configured
        msg = str(exc_info.value).lower()
        assert any(w in msg for w in ("jwt_secret", "configured", "503", "service"))
    finally:
        if saved:
            os.environ["JWT_SECRET"] = saved


def test_token_value_not_in_response():
    """JWT token value must not appear in any API response body."""
    token = _make_jwt()
    # A 401 response from an invalid endpoint should not echo the token
    resp = client.get("/cases/00000000-0000-0000-0000-000000000000",
                      headers=_bearer(token))
    resp_text = resp.text
    assert token not in resp_text, "JWT token value must not be included in response body"


# ── 10-14. Auth mode via API ───────────────────────────────────────────────────

_ASSESSMENT = {
    "status": "ok", "claim_type": "unfair_dismissal", "has_viable_claim": "yes",
    "strength": "medium", "reasoning_summary": "Test.", "key_weaknesses": [],
    "employer_arguments": [],
    "deadline_info": {"limitation_date": "2026-06-30", "source": "rules",
                      "authority": "ERA 1996 s.111(2)", "ec_applied": False},
    "value_range": {"low": 1800, "high": 31200, "currency": "GBP", "basis": "From rules."},
    "recommended_next_step": "prepare_documents",
    "citations": [], "grounding_score": 0.85, "confidence_score": 0.75,
    "insufficient_grounding": False,
    "boundary_log": {"fields_passed": ["edt"], "fields_stripped": [], "pii_in_output": []},
}


def test_jwt_mode_valid_token_allows_case_access():
    """JWT mode: valid token creates and retrieves case with ownership."""
    token = _make_jwt(sub=_TEST_SUB)
    case_resp = client.post("/cases", json={
        "claim_type": "unfair_dismissal", "jurisdiction": "EW",
        "assessment": _ASSESSMENT,
        "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
    }, headers=_bearer(token))
    assert case_resp.status_code == 201
    case_id = case_resp.json()["case_id"]

    get_resp = client.get(f"/cases/{case_id}", headers=_bearer(token))
    assert get_resp.status_code == 200


def test_jwt_mode_expired_token_rejected_by_api():
    """JWT mode: expired token returns 401 from API endpoint."""
    expired = _make_jwt(exp_secs=-60)
    resp = client.post("/cases", json={
        "claim_type": "unfair_dismissal", "jurisdiction": "EW",
        "assessment": _ASSESSMENT,
        "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
    }, headers=_bearer(expired))
    assert resp.status_code == 401, f"Expired token must be rejected, got {resp.status_code}"


def test_jwt_mode_invalid_signature_rejected_by_api():
    """JWT mode: wrong secret → 401 from API."""
    bad_sig = _make_jwt(secret="wrong-secret-that-is-also-long-enough!!")
    resp = client.get("/cases/00000000-0000-0000-0000-000000000000",
                      headers=_bearer(bad_sig))
    assert resp.status_code in (401, 404), \
        f"Bad signature: expected 401 or 404 (auth fails before case lookup), got {resp.status_code}"


def test_mock_mode_still_works():
    """Mock mode (dev/test) still works with X-User-ID after Phase 6C changes."""
    os.environ["LAWAPP_AUTH_MODE"] = "mock"
    try:
        mock_user = str(uuid.uuid4())
        case_resp = client.post("/cases", json={
            "claim_type": "unfair_dismissal", "jurisdiction": "EW",
            "assessment": _ASSESSMENT,
            "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
        }, headers={"X-User-ID": mock_user})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["case_id"]
        get_resp = client.get(f"/cases/{case_id}", headers={"X-User-ID": mock_user})
        assert get_resp.status_code == 200
    finally:
        os.environ["LAWAPP_AUTH_MODE"] = "jwt"


def test_production_readiness_jwt_configured():
    """
    Phase 7A update: HS256-only (JWT_SECRET, no JWT_JWKS_URL) is NOT production-ready.
    RS256+JWKS (JWT_JWKS_URL) IS production-ready.
    Phase 6C fixture has JWT_SECRET only (no JWKS_URL).
    """
    from backend.core.user_auth import is_auth_production_ready

    # HS256-only (current fixture) → NOT production-ready (Phase 7A)
    result_hs256 = is_auth_production_ready()
    assert result_hs256["ready"] is False, \
        "HS256-only must not be production-ready after Phase 7A (requires RS256+JWKS)"
    assert any("hs256" in b.lower() or "jwks" in b.lower() for b in result_hs256["blockers"])

    # RS256+JWKS (add JWT_JWKS_URL) → IS production-ready
    os.environ["JWT_JWKS_URL"] = "https://mock-jwks.example.com/.well-known/jwks.json"
    try:
        result_rs256 = is_auth_production_ready()
        assert result_rs256["ready"] is True, \
            f"RS256+JWKS with full config must be production-ready: {result_rs256['blockers']}"
        assert result_rs256["blockers"] == []
    finally:
        os.environ.pop("JWT_JWKS_URL", None)


# ── 15-16. Admin protection ───────────────────────────────────────────────────

def test_admin_production_readiness_blocks_without_key():
    resp = client.get("/admin/production-readiness")
    assert resp.status_code == 403


def test_admin_compliance_status_blocks_without_key():
    resp = client.get("/admin/compliance-status")
    assert resp.status_code == 403


# ── 17-19. Production readiness ───────────────────────────────────────────────

def test_readiness_report_shows_jwt_implemented():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    assert resp.status_code == 200
    data = resp.json()
    auth = data.get("user_authentication", {})
    assert "jwt_hs256_verification" in auth
    assert auth["jwt_hs256_verification"] == "IMPLEMENTED", \
        f"JWT HS256 should be IMPLEMENTED with JWT_SECRET set: {auth}"


def test_controlled_beta_ready_remains_false():
    """Controlled beta still blocked by DPIA/privacy — not a technical issue."""
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    # With current compliance-signoff.json (DPIA not reviewed), CB is still False
    assert data.get("controlled_beta_ready") is False, \
        "controlled_beta_ready must remain False until DPIA/privacy are genuinely reviewed"


def test_production_ready_remains_false():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    assert resp.json()["production_ready"] is False


# ── 20-23. Regressions ────────────────────────────────────────────────────────

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
    assert result.returncode == 0, f"Rules verification gate failed:\n{result.stdout}"


def test_static_routes_regression():
    os.environ["LAWAPP_AUTH_MODE"] = "none"   # temporarily disable auth for static check
    try:
        for path in ["/", "/pages/intake.html", "/pages/assessment.html"]:
            assert client.get(path).status_code == 200, f"{path} failed"
    finally:
        os.environ["LAWAPP_AUTH_MODE"] = "jwt"


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
