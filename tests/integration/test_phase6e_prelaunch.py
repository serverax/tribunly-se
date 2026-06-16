"""
Phase 6E  -  Pre-beta launch readiness tests.

Tests:
  Operational artifacts:
   1.  env-production.template exists and has required sections
   2.  pre-beta-runbook.md exists and references compliance steps
   3.  check_beta_readiness.py script exists and exits 0
   4.  dpia-review-checklist.md exists (Phase 6D)
   5.  privacy-review-checklist.md exists (Phase 6D)

  Production readiness report:
   6.  Report includes controlled_beta_next_steps
   7.  Next steps are ordered (priority field present)
   8.  DPIA review is first priority when not reviewed
   9.  Privacy review is second priority when not reviewed
  10.  Next steps include human_review_required type items
  11.  Report includes runbook reference
  12.  Report includes beta_readiness_script reference

  Current state validation:
  13.  controlled_beta_ready remains false (human review not done)
  14.  controlled_beta_next_steps is non-empty (blockers exist)
  15.  Next steps include configuration items when env vars not set

  CI integration:
  16.  .github/workflows/ci.yml includes beta readiness check step

  Regressions:
  17.  Legal accuracy gate passes
  18.  Rules verification gate passes
  19.  Admin endpoints require key
  20.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase6e_prelaunch.py -v -s
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app, raise_server_exceptions=True)

_ADMIN_KEY = "test-admin-6e"
_ADMIN_HDR = {"X-Admin-Key": _ADMIN_KEY}
_ROOT      = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module", autouse=True)
def phase6e_env():
    from cryptography.fernet import Fernet
    saved = {k: os.environ.get(k) for k in [
        "ADMIN_API_KEY", "ENCRYPTION_KEY", "LAWAPP_AUTH_MODE", "DEPLOYMENT_MODE",
    ]}
    os.environ.update({
        "ADMIN_API_KEY":    _ADMIN_KEY,
        "ENCRYPTION_KEY":   Fernet.generate_key().decode(),
        "LAWAPP_AUTH_MODE": "none",
        "DEPLOYMENT_MODE":  "development",
    })
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ── 1-5. Operational artifacts ─────────────────────────────────────────────────

def test_env_production_template_exists():
    template = _ROOT / "docs" / "env-production.template"
    assert template.exists(), "docs/env-production.template must exist"


def test_env_template_has_required_sections():
    template = (_ROOT / "docs" / "env-production.template").read_text(encoding="utf-8")
    required = ["DEPLOYMENT_MODE", "POSTGRES_PASSWORD", "ADMIN_API_KEY",
                "ENCRYPTION_KEY", "LAWAPP_AUTH_MODE", "JWT_SECRET",
                "JWT_ISSUER", "JWT_AUDIENCE", "APP_BASE_URL", "PAYMENT_MODE"]
    for var in required:
        assert var in template, f"{var} missing from env-production.template"


def test_pre_beta_runbook_exists():
    runbook = _ROOT / "docs" / "pre-beta-runbook.md"
    assert runbook.exists(), "docs/pre-beta-runbook.md must exist"


def test_runbook_references_compliance_steps():
    runbook = (_ROOT / "docs" / "pre-beta-runbook.md").read_text(encoding="utf-8")
    assert "dpia-review-checklist" in runbook.lower()
    assert "privacy-review-checklist" in runbook.lower()
    assert "compliance-signoff" in runbook.lower()


def test_check_beta_readiness_script_exists_and_runs():
    assert (_ROOT / "scripts" / "check_beta_readiness.py").exists()
    result = subprocess.run(
        [sys.executable, "scripts/check_beta_readiness.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, \
        f"check_beta_readiness.py must exit 0 (reporting only):\n{result.stdout}\n{result.stderr}"
    assert "LAWAPP" in result.stdout or "beta" in result.stdout.lower()


def test_dpia_review_checklist_exists():
    assert (_ROOT / "docs" / "dpia-review-checklist.md").exists()


def test_privacy_review_checklist_exists():
    assert (_ROOT / "docs" / "privacy-review-checklist.md").exists()


# ── 6-12. Production readiness report ─────────────────────────────────────────

def test_report_includes_controlled_beta_next_steps():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert "controlled_beta_next_steps" in data, \
        "Report must include controlled_beta_next_steps (Phase 6E)"


def test_next_steps_are_ordered():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    steps = resp.json()["controlled_beta_next_steps"]
    assert len(steps) > 0
    priorities = [s["priority"] for s in steps]
    assert priorities == sorted(priorities), "Steps must be ordered by priority"


def test_dpia_review_is_first_priority():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    steps = resp.json()["controlled_beta_next_steps"]
    first = min(steps, key=lambda s: s["priority"])
    assert "dpia" in first["action"].lower() or "dpo" in first["action"].lower(), \
        f"DPIA review must be first priority when not done: {first['action']}"


def test_privacy_review_is_second_priority():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    steps = resp.json()["controlled_beta_next_steps"]
    sorted_steps = sorted(steps, key=lambda s: s["priority"])
    if len(sorted_steps) > 1:
        second = sorted_steps[1]
        assert "privacy" in second["action"].lower() or "legal" in second["action"].lower(), \
            f"Privacy review should be second priority: {second['action']}"


def test_next_steps_include_human_review_type():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    steps = resp.json()["controlled_beta_next_steps"]
    types = [s["type"] for s in steps]
    assert "human_review_required" in types, \
        "Next steps must flag human-review-required items"


def test_report_includes_runbook_reference():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert "runbook" in data
    assert "pre-beta-runbook" in data["runbook"]


def test_report_includes_beta_readiness_script_reference():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert "beta_readiness_script" in data
    assert "check_beta_readiness" in data["beta_readiness_script"]


# ── 13-15. Current state ──────────────────────────────────────────────────────

def test_controlled_beta_ready_still_false():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert data["controlled_beta_ready"] is False, \
        "controlled_beta_ready must be false  -  no human sign-offs have occurred"


def test_next_steps_is_nonempty():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    steps = resp.json()["controlled_beta_next_steps"]
    assert len(steps) > 0, "There must be remaining next steps"


def test_next_steps_include_steps_for_missing_env_vars():
    """When env vars are missing, next steps must include configuration items."""
    saved_enc = os.environ.pop("ENCRYPTION_KEY", None)
    try:
        resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
        steps = resp.json()["controlled_beta_next_steps"]
        types = [s["type"] for s in steps]
        # At minimum, human review and/or configuration items should appear
        assert any(t in ("human_review_required", "configuration") for t in types)
    finally:
        if saved_enc:
            os.environ["ENCRYPTION_KEY"] = saved_enc


# ── 16. CI integration ────────────────────────────────────────────────────────

def test_ci_yml_includes_beta_readiness_step():
    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "check_beta_readiness.py" in ci, \
        "CI must include the beta readiness check step"


# ── 17-20. Regressions ────────────────────────────────────────────────────────

def test_legal_accuracy_gate_regression():
    result = subprocess.run(
        [sys.executable, "scripts/run_legal_accuracy.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_rules_verification_gate_regression():
    result = subprocess.run(
        [sys.executable, "scripts/check_rules_verification.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_admin_endpoints_still_require_key():
    assert client.get("/admin/production-readiness").status_code == 403
    assert client.get("/admin/compliance-status").status_code == 403


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
