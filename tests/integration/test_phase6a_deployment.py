"""
Phase 6A — Deployment readiness, auth, and payment mode tests.

Tests:
  Config validation:
   1.  Production mode fails when required vars missing
   2.  Production mode passes when all required vars present
   3.  Development mode warns but does not fail

  User authentication:
   4.  Auth mode 'none' allows access without X-User-ID
   5.  Auth mode 'mock' associates case with user_id
   6.  Auth mode 'mock' blocks access to another user's case (403)
   7.  Auth mode 'mock' allows owner access to their case (200)
   8.  Admin key overrides user auth restriction

  Payment modes:
   9.  Payment mode 'mock' allows paid document access
  10.  Payment mode 'disabled' blocks all paid output
  11.  Payment mode 'stripe_live' fails safely without STRIPE_SECRET_KEY
  12.  Payment mode 'stripe_test' fails safely (not yet implemented)
  13.  Document gate still works in mock mode
  14.  Bundle gate still works in mock mode

  Production readiness:
  15.  /admin/production-readiness includes deployment config status
  16.  /admin/production-readiness includes auth status
  17.  /admin/production-readiness includes payment mode status
  18.  Report remains NOT_PRODUCTION_READY

  CI scripts:
  19.  scripts/run_legal_accuracy.py exists and is runnable
  20.  scripts/check_rules_verification.py exists
  21.  scripts/safe_push.sh exists
  22.  .github/workflows/ci.yml contains legal accuracy gate
  23.  .github/workflows/ci.yml contains rules verification gate

  Regressions:
  24.  UD assessment still works
  25.  Admin auth still blocks /admin/* without key
  26.  Legal accuracy gate passes
  27.  Static routes serve
  28.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase6a_deployment.py -v -s
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

from tests.integration.auth_helpers import TEST_USER_ID, mock_auth_headers
from backend.core.pipeline import assess
from backend.core.models import StubReasoningModel
from tests.integration.payment_helpers import mark_case_paid

client = TestClient(app, raise_server_exceptions=True)
# Legacy /documents/generate fails closed (401) for anonymous callers; these tests
# target payment/content behaviour, so authenticate with a mock identity.
_LEGACY_AUTH = mock_auth_headers(TEST_USER_ID)

STUB = StubReasoningModel()

_ADMIN_KEY = "test-admin-6a"
_ADMIN_HDR = {"X-Admin-Key": _ADMIN_KEY}

_USER_A = "aaaaaaaa-0000-0000-0000-000000000001"
_USER_B = "bbbbbbbb-0000-0000-0000-000000000002"

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

_FACTS = {"edt": "2026-04-01", "service_start_date": "2023-04-01",
          "reason_for_dismissal": "conduct", "weekly_pay": 600, "jurisdiction": "EW"}


@pytest.fixture(scope="module", autouse=True)
def phase6a_env():
    """Set env vars for Phase 6A tests."""
    from cryptography.fernet import Fernet
    enc_key = Fernet.generate_key().decode()
    saved = {
        "ADMIN_API_KEY":    os.environ.get("ADMIN_API_KEY"),
        "ENCRYPTION_KEY":   os.environ.get("ENCRYPTION_KEY"),
        "LAWAPP_AUTH_MODE": os.environ.get("LAWAPP_AUTH_MODE"),
        "PAYMENT_MODE":     os.environ.get("PAYMENT_MODE"),
        "DEPLOYMENT_MODE":  os.environ.get("DEPLOYMENT_MODE"),
    }
    os.environ["ADMIN_API_KEY"]    = _ADMIN_KEY
    os.environ["ENCRYPTION_KEY"]   = enc_key
    os.environ["LAWAPP_AUTH_MODE"] = "mock"
    os.environ["PAYMENT_MODE"]     = "mock"
    os.environ["DEPLOYMENT_MODE"]  = "development"
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _make_case(user_id=None) -> str:
    hdrs = dict(_LEGACY_AUTH)
    if user_id:
        hdrs["X-User-ID"] = user_id
    resp = client.post("/cases", headers=hdrs, json={
        "claim_type": "unfair_dismissal", "jurisdiction": "EW",
        "assessment": _ASSESSMENT,
        "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
    })
    assert resp.status_code == 201
    return resp.json()["case_id"]


def _make_paid_case(user_id=None) -> str:
    case_id = _make_case(user_id=user_id)
    mark_case_paid(case_id)
    return case_id


# ── 1-3. Config validation ─────────────────────────────────────────────────────

def test_production_mode_fails_when_required_vars_missing():
    from backend.core.config_validation import validate_startup_config, StartupConfigError
    saved = os.environ.pop("ADMIN_API_KEY", None)
    try:
        result = validate_startup_config(fail_fast=False)
        os.environ["DEPLOYMENT_MODE"] = "production"
        result2 = validate_startup_config(fail_fast=False)
        assert result2["status"] in ("FAILED", "WARNING")
        assert "ADMIN_API_KEY" in result2["missing_required"]
    finally:
        if saved:
            os.environ["ADMIN_API_KEY"] = saved
        os.environ["DEPLOYMENT_MODE"] = "development"


def test_production_mode_passes_when_all_required_vars_present():
    """Phase 6B update: production now requires APP_BASE_URL + jwt auth with config."""
    from backend.core.config_validation import validate_startup_config
    extra = {
        "DEPLOYMENT_MODE":  "production",
        "POSTGRES_PASSWORD": "test-pass",
        "APP_BASE_URL":     "https://app.lawapp.co.uk",
        "LAWAPP_AUTH_MODE": "jwt",
        "JWT_ISSUER":       "https://auth.lawapp.co.uk",
        "JWT_AUDIENCE":     "lawapp-api",
        "JWT_SECRET":       "test-secret",
        "PAYMENT_MODE":     "stripe_live",
        "STRIPE_SECRET_KEY": "sk_live_test_placeholder",
        "STRIPE_WEBHOOK_SECRET": "whsec_test_placeholder",
    }
    saved = {k: os.environ.get(k) for k in extra}
    os.environ.update(extra)
    try:
        result = validate_startup_config(fail_fast=False)
        assert result["status"] == "OK", \
            f"Expected OK with all vars present, got {result['status']}: {result['missing_required']}"
        assert result["missing_required"] == []
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_development_mode_warns_but_does_not_fail():
    from backend.core.config_validation import validate_startup_config
    os.environ["DEPLOYMENT_MODE"] = "development"
    saved = os.environ.pop("POSTGRES_PASSWORD", None)
    try:
        result = validate_startup_config(fail_fast=False)
        # Should not raise; status is WARNING or OK
        assert result["status"] in ("OK", "WARNING")
    finally:
        if saved:
            os.environ["POSTGRES_PASSWORD"] = saved


# ── 4-8. User authentication ──────────────────────────────────────────────────

def test_auth_none_allows_access_without_user_id():
    os.environ["LAWAPP_AUTH_MODE"] = "none"
    try:
        case_id = _make_case()  # no user_id
        resp = client.get(f"/cases/{case_id}")
        assert resp.status_code == 200
    finally:
        os.environ["LAWAPP_AUTH_MODE"] = "mock"


def test_mock_auth_associates_case_with_user():
    case_id = _make_case(user_id=_USER_A)
    # Owner can access
    resp = client.get(f"/cases/{case_id}", headers={"X-User-ID": _USER_A})
    assert resp.status_code == 200


def test_mock_auth_blocks_other_users_case():
    case_id = _make_case(user_id=_USER_A)
    resp = client.get(f"/cases/{case_id}", headers={"X-User-ID": _USER_B})
    assert resp.status_code == 403, \
        f"User B must not access User A's case (got {resp.status_code})"


def test_mock_auth_allows_owner_access():
    case_id = _make_case(user_id=_USER_A)
    resp = client.get(f"/cases/{case_id}", headers={"X-User-ID": _USER_A})
    assert resp.status_code == 200


def test_admin_key_overrides_user_auth():
    case_id = _make_case(user_id=_USER_A)
    # Admin key without user ID can access
    resp = client.get(f"/cases/{case_id}", headers=_ADMIN_HDR)
    assert resp.status_code == 200, \
        "Admin key must bypass user ownership restriction"


# ── 9-14. Payment modes ───────────────────────────────────────────────────────

def test_payment_mock_does_not_unlock_raw_token():
    os.environ["PAYMENT_MODE"] = "mock"
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json={
        "document_type": "particulars_of_claim",
        "assessment": _ASSESSMENT, "facts": _FACTS,
        "payment_token": "mock-test-token",
    })
    assert resp.status_code == 200
    assert resp.json()["payment_required"] is True


def test_payment_disabled_blocks_paid_output():
    os.environ["PAYMENT_MODE"] = "disabled"
    try:
        resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json={
            "document_type": "particulars_of_claim",
            "assessment": _ASSESSMENT, "facts": _FACTS,
            "payment_token": "any-token",
        })
        assert resp.status_code == 200
        assert resp.json()["payment_required"] is True, \
            "PAYMENT_MODE=disabled must block all paid output"
    finally:
        os.environ["PAYMENT_MODE"] = "mock"


def test_payment_stripe_live_fails_safely_without_key():
    os.environ["PAYMENT_MODE"] = "stripe_live"
    os.environ.pop("STRIPE_SECRET_KEY", None)
    try:
        resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json={
            "document_type": "particulars_of_claim",
            "assessment": _ASSESSMENT, "facts": _FACTS,
            "payment_token": "some-token",
        })
        assert resp.status_code == 200
        assert resp.json()["payment_required"] is True, \
            "stripe_live without key must fail closed to preview-only output"
    finally:
        os.environ["PAYMENT_MODE"] = "mock"


def test_payment_stripe_test_fails_safely():
    os.environ["PAYMENT_MODE"] = "stripe_test"
    try:
        resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json={
            "document_type": "particulars_of_claim",
            "assessment": _ASSESSMENT, "facts": _FACTS,
            "payment_token": "some-token",
        })
        assert resp.status_code == 200
        assert resp.json()["payment_required"] is True, \
            "stripe_test must not unlock output from an arbitrary request token"
    finally:
        os.environ["PAYMENT_MODE"] = "mock"


def test_document_gate_uses_db_paid_state():
    os.environ["PAYMENT_MODE"] = "test"
    case_id = _make_paid_case()
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json={
        "document_type": "schedule_of_loss",
        "assessment": _ASSESSMENT, "facts": _FACTS,
        "case_id": case_id,
    })
    assert resp.status_code == 200
    assert resp.json()["payment_required"] is False
    assert resp.json()["safety_check"]["passed"] is True


def test_bundle_gate_uses_db_paid_state():
    case_id = _make_paid_case()
    resp = client.post(f"/cases/{case_id}/bundle/generate", json={})
    assert resp.status_code == 200
    assert resp.json()["payment_required"] is False


# ── 15-18. Production readiness ───────────────────────────────────────────────

def test_production_readiness_includes_deployment_config():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert "deployment_config" in data
    assert "mode" in data["deployment_config"]


def test_production_readiness_includes_auth_status():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert "user_authentication" in data
    assert "admin_key_status" in data["user_authentication"]
    assert "end_user_auth_mode" in data["user_authentication"]


def test_production_readiness_includes_payment_status():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert "payment" in data
    assert "mode" in data["payment"]


def test_production_readiness_remains_not_ready():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert data["overall_status"] == "NOT_PRODUCTION_READY"
    assert data["ready_for_production"] is False


# ── 19-23. CI scripts ────────────────────────────────────────────────────────

def test_legal_accuracy_script_exists():
    assert Path("scripts/run_legal_accuracy.py").exists()


def test_rules_verification_script_exists():
    assert Path("scripts/check_rules_verification.py").exists()


def test_safe_push_script_exists():
    assert Path("scripts/safe_push.sh").exists()


def test_ci_yml_contains_legal_accuracy_gate():
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "legal-accuracy" in ci.lower() or "legal_accuracy" in ci.lower(), \
        "CI must run legal accuracy gate"
    assert "run_legal_accuracy.py" in ci


def test_ci_yml_contains_rules_verification_gate():
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "rules-verification" in ci.lower() or "rules_verification" in ci.lower()
    assert "check_rules_verification.py" in ci


# ── 24-28. Regressions ────────────────────────────────────────────────────────

def test_ud_assessment_regression():
    result = assess("I was unfairly dismissed", _FACTS, model=STUB)
    dl = result.get("deadline_info") or {}
    assert dl.get("source") == "rules"


def test_admin_auth_blocks_without_key():
    assert client.get("/admin/dp-report").status_code == 403


def test_legal_accuracy_gate_regression():
    result = subprocess.run(
        [sys.executable, "scripts/run_legal_accuracy.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Legal accuracy gate failed:\n{result.stdout}"


def test_static_routes_regression():
    for path in ["/", "/pages/intake.html", "/pages/assessment.html"]:
        assert client.get(path).status_code == 200


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
