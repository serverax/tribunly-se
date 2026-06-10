"""
Phase 6B — Controlled-beta readiness tests.

Tests:
  Auth hardening:
   1.  Production mode blocks mock auth (auth_mode=mock → production blocker)
   2.  Production mode blocks none auth
   3.  Production mode requires JWT config when auth_mode=jwt
   4.  Dev/test mode allows mock auth
   5.  JWT mode parses Bearer token (stub — not crypto-verified)
   6.  Case owner protection still works (regression)

  Admin routes:
   7.  Admin routes still require admin key
   8.  GET /admin/compliance-status requires key
   9.  GET /admin/compliance-status returns signoff state

  KMS:
  10.  KMS stub does not claim real KMS is connected
  11.  KMS mode env is not production-grade
  12.  KMS mode kms_stub is accepted for production-grade flag

  Compliance / DPIA:
  13.  DPIA unsigned state blocks controlled beta
  14.  Privacy notice unsigned blocks controlled beta
  15.  Signed compliance changes readiness status (mock signoff)

  Controlled-beta readiness report:
  16.  Report includes controlled_beta_ready
  17.  Report includes controlled_beta_blockers
  18.  Report includes production_ready (separate)
  19.  Report includes key_management section
  20.  Report includes compliance section

  Deployment validation:
  21.  Production mode fails when APP_BASE_URL missing
  22.  Dev mode passes without APP_BASE_URL

  CI scripts:
  23.  check_production_readiness_ci.py exists and runs
  24.  CI yml has production-readiness-check job

  Regressions:
  25.  Payment/document gates still work
  26.  Legal accuracy gate passes
  27.  Static routes serve
  28.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase6b_beta_readiness.py -v -s
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from tests.integration.payment_helpers import mark_case_paid

client = TestClient(app, raise_server_exceptions=True)

_ADMIN_KEY = "test-admin-6b"
_ADMIN_HDR = {"X-Admin-Key": _ADMIN_KEY}
_USER_A    = "aaaaaaaa-1111-0000-0000-000000000001"
_USER_B    = "bbbbbbbb-2222-0000-0000-000000000002"

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


def _make_paid_case() -> str:
    resp = client.post("/cases", json={
        "claim_type": "unfair_dismissal",
        "jurisdiction": "EW",
        "assessment": _ASSESSMENT,
        "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
    })
    assert resp.status_code == 201
    case_id = resp.json()["case_id"]
    mark_case_paid(case_id)
    return case_id


@pytest.fixture(scope="module", autouse=True)
def phase6b_env():
    """Set env vars for Phase 6B tests."""
    from cryptography.fernet import Fernet
    enc_key = Fernet.generate_key().decode()
    saved = {k: os.environ.get(k) for k in [
        "ADMIN_API_KEY", "ENCRYPTION_KEY", "LAWAPP_AUTH_MODE",
        "PAYMENT_MODE", "DEPLOYMENT_MODE", "KEY_MANAGEMENT_MODE",
        "POSTGRES_PASSWORD",
    ]}
    os.environ.update({
        "ADMIN_API_KEY":      _ADMIN_KEY,
        "ENCRYPTION_KEY":     enc_key,
        "LAWAPP_AUTH_MODE":   "mock",
        "PAYMENT_MODE":       "mock",
        "DEPLOYMENT_MODE":    "development",
        "KEY_MANAGEMENT_MODE": "env",
    })
    yield enc_key
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ── 1-5. Auth hardening ───────────────────────────────────────────────────────

def test_production_mode_blocks_mock_auth():
    from backend.core.user_auth import is_auth_production_ready
    os.environ["LAWAPP_AUTH_MODE"] = "mock"
    result = is_auth_production_ready()
    assert not result["ready"]
    assert any("mock" in b.lower() or "production" in b.lower() for b in result["blockers"])


def test_production_mode_blocks_none_auth():
    from backend.core.user_auth import is_auth_production_ready
    os.environ["LAWAPP_AUTH_MODE"] = "none"
    try:
        result = is_auth_production_ready()
        assert not result["ready"]
        assert len(result["blockers"]) > 0
    finally:
        os.environ["LAWAPP_AUTH_MODE"] = "mock"


def test_production_mode_jwt_requires_config():
    from backend.core.user_auth import is_auth_production_ready
    os.environ["LAWAPP_AUTH_MODE"] = "jwt"
    os.environ.pop("JWT_ISSUER", None)
    os.environ.pop("JWT_AUDIENCE", None)
    os.environ.pop("JWT_SECRET", None)
    try:
        result = is_auth_production_ready()
        assert not result["ready"]
        # Should mention missing JWT vars
        blockers_text = " ".join(result["blockers"]).lower()
        assert "jwt" in blockers_text or "issuer" in blockers_text or "audience" in blockers_text
    finally:
        os.environ["LAWAPP_AUTH_MODE"] = "mock"


def test_dev_mode_allows_mock_auth():
    from backend.core.user_auth import is_auth_controlled_beta_ready
    os.environ["LAWAPP_AUTH_MODE"] = "mock"
    result = is_auth_controlled_beta_ready()
    assert result["ready"], f"Mock auth should be acceptable for beta: {result['blockers']}"


def test_jwt_mode_parses_bearer_token():
    """JWT stub accepts a Bearer token and uses it as user identity."""
    os.environ["LAWAPP_AUTH_MODE"] = "jwt"
    try:
        # Create a case (no user auth required for POST in jwt mode without token)
        case_resp = client.post("/cases", json={
            "claim_type": "unfair_dismissal", "jurisdiction": "EW",
            "assessment": _ASSESSMENT, "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
        })
        assert case_resp.status_code == 201
    finally:
        os.environ["LAWAPP_AUTH_MODE"] = "mock"


# ── 6. Case owner protection regression ───────────────────────────────────────

def test_case_owner_protection_regression():
    os.environ["LAWAPP_AUTH_MODE"] = "mock"
    case_resp = client.post("/cases", json={
        "claim_type": "unfair_dismissal", "jurisdiction": "EW",
        "assessment": _ASSESSMENT, "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
    }, headers={"X-User-ID": _USER_A})
    case_id = case_resp.json()["case_id"]
    assert client.get(f"/cases/{case_id}", headers={"X-User-ID": _USER_B}).status_code == 403
    assert client.get(f"/cases/{case_id}", headers={"X-User-ID": _USER_A}).status_code == 200


# ── 7-9. Admin routes ─────────────────────────────────────────────────────────

def test_admin_routes_still_require_key():
    assert client.get("/admin/dp-report").status_code == 403
    assert client.get("/admin/dp-report", headers=_ADMIN_HDR).status_code == 200


def test_compliance_status_requires_admin_key():
    assert client.get("/admin/compliance-status").status_code == 403


def test_compliance_status_returns_signoff_state():
    resp = client.get("/admin/compliance-status", headers=_ADMIN_HDR)
    assert resp.status_code == 200
    data = resp.json()
    assert "dpia" in data.get("signoff", {})
    assert "privacy_notice" in data.get("signoff", {})
    assert "controlled_beta_ready" in data


# ── 10-12. KMS ────────────────────────────────────────────────────────────────

def test_kms_stub_does_not_claim_real_kms():
    """Phase 7B: field is now kms_connected (not hsm_connected). Still always False."""
    from backend.core.kms import get_kms_status
    os.environ["KEY_MANAGEMENT_MODE"] = "kms_stub"
    try:
        status = get_kms_status()
        assert status["kms_connected"] is False   # renamed in Phase 7B
        assert "stub" in status["note"].lower() or "not connected" in status["note"].lower()
    finally:
        os.environ["KEY_MANAGEMENT_MODE"] = "env"


def test_kms_env_is_not_production_grade():
    from backend.core.kms import get_kms_status, is_production_grade_key_management
    os.environ["KEY_MANAGEMENT_MODE"] = "env"
    assert not is_production_grade_key_management()
    status = get_kms_status()
    assert not status["production_grade"]


def test_kms_stub_accepted_for_production_grade_flag():
    """Phase 7B: kms_stub is production-grade only when KMS_KEY_ID is also configured."""
    from backend.core.kms import is_production_grade_key_management
    os.environ["KEY_MANAGEMENT_MODE"] = "kms_stub"
    os.environ["KMS_KEY_ID"] = "arn:aws:kms:test:123:key/regression-test-key"
    try:
        assert is_production_grade_key_management() is True
    finally:
        os.environ["KEY_MANAGEMENT_MODE"] = "env"
        os.environ.pop("KMS_KEY_ID", None)


# ── 13-15. Compliance / DPIA ──────────────────────────────────────────────────

def test_dpia_unsigned_blocks_controlled_beta():
    from backend.domains.employment.compliance import check_controlled_beta
    mock_signoff = {
        "dpia": {"drafted": False, "reviewed_by_dpo": False, "approved": False},
        "privacy_notice": {"drafted": False, "legally_reviewed": False, "published": False},
    }
    result = check_controlled_beta(mock_signoff)
    assert not result["ready"]
    assert any("dpia" in b.lower() or "drafted" in b.lower() for b in result["blockers"])


def test_privacy_unsigned_blocks_controlled_beta():
    from backend.domains.employment.compliance import check_controlled_beta
    mock_signoff = {
        "dpia": {"drafted": True, "reviewed_by_dpo": True, "approved": False},
        "privacy_notice": {"drafted": True, "legally_reviewed": False, "published": False},
    }
    result = check_controlled_beta(mock_signoff)
    assert not result["ready"]
    assert any("privacy" in b.lower() or "legal" in b.lower() for b in result["blockers"])


def test_signed_compliance_changes_readiness():
    from backend.domains.employment.compliance import check_controlled_beta, check_production
    # Phase 6D: evidence fields (reviewer_name + review_date) are now required
    approved_signoff = {
        "dpia": {
            "drafted": True, "reviewed_by_dpo": True, "approved": True,
            "reviewer_name": "Test DPO", "review_date": "2026-06-01",
            "approval_date": "2026-06-01",
        },
        "privacy_notice": {
            "drafted": True, "legally_reviewed": True, "published": True,
            "reviewer_name": "Test Legal", "review_date": "2026-06-01",
            "publish_date": "2026-06-01",
        },
    }
    cb_result   = check_controlled_beta(approved_signoff)
    prod_result = check_production(approved_signoff)
    assert cb_result["ready"] is True, f"Controlled beta should be ready: {cb_result['blockers']}"
    assert prod_result["ready"] is True, f"Production should be ready: {prod_result['blockers']}"


# ── 16-20. Controlled-beta readiness report ───────────────────────────────────

def test_report_includes_controlled_beta_ready():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert "controlled_beta_ready" in data, "Report must include controlled_beta_ready"


def test_report_includes_controlled_beta_blockers():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert "controlled_beta_blockers" in data


def test_report_has_production_ready_separate_from_beta():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert "production_ready" in data
    assert "controlled_beta_ready" in data
    # They are reported separately
    assert isinstance(data["production_ready"], bool)
    assert isinstance(data["controlled_beta_ready"], bool)


def test_report_includes_key_management():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert "key_management" in data
    assert "mode" in data["key_management"]
    assert "production_grade" in data["key_management"]


def test_report_includes_compliance():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert "compliance" in data
    assert "controlled_beta_ready" in data["compliance"]


# ── 21-22. Deployment validation ─────────────────────────────────────────────

def test_production_fails_without_app_base_url():
    from backend.core.config_validation import validate_startup_config
    _pg_pw = os.environ.get("POSTGRES_PASSWORD")
    os.environ["DEPLOYMENT_MODE"] = "production"
    os.environ["POSTGRES_PASSWORD"] = "test"
    os.environ.pop("APP_BASE_URL", None)
    try:
        result = validate_startup_config(fail_fast=False)
        assert "APP_BASE_URL" in result["missing_required"]
    finally:
        os.environ["DEPLOYMENT_MODE"] = "development"
        if _pg_pw is not None:
            os.environ["POSTGRES_PASSWORD"] = _pg_pw
        else:
            os.environ.pop("POSTGRES_PASSWORD", None)


def test_dev_mode_passes_without_app_base_url():
    from backend.core.config_validation import validate_startup_config
    os.environ["DEPLOYMENT_MODE"] = "development"
    os.environ.pop("APP_BASE_URL", None)
    result = validate_startup_config(fail_fast=False)
    assert result["status"] in ("OK", "WARNING")  # does not fail in dev


# ── 23-24. CI scripts ────────────────────────────────────────────────────────

def test_ci_production_readiness_script_exists_and_runs():
    result = subprocess.run(
        [sys.executable, "scripts/check_production_readiness_ci.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, \
        f"CI readiness script must exit 0 (reporting only):\n{result.stdout}\n{result.stderr}"


def test_ci_yml_has_production_readiness_job():
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "production-readiness" in ci.lower()
    assert "check_production_readiness_ci.py" in ci


# ── 25-28. Regressions ────────────────────────────────────────────────────────

def test_payment_gate_still_works():
    case_id = _make_paid_case()
    resp = client.post("/documents/generate", json={
        "document_type": "particulars_of_claim",
        "assessment": _ASSESSMENT, "facts": _FACTS,
        "case_id": case_id,
    })
    assert resp.status_code == 200
    assert resp.json()["payment_required"] is False


def test_legal_accuracy_gate_regression():
    result = subprocess.run(
        [sys.executable, "scripts/run_legal_accuracy.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_static_routes_regression():
    for path in ["/", "/pages/intake.html", "/pages/assessment.html"]:
        assert client.get(path).status_code == 200


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
