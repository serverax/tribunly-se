"""
Phase 5C  -  Rules verification and production-readiness tests.

Tests:
  Rules verification:
   1.  UPW rules include verification_status column after migration 011
   2.  UD rules include verification_status column
   3.  UPW verified/case_law_verified rules pass the verification gate
   4.  UD verified rules pass the verification gate
   5.  Unverified production rule fails the CI gate (check_verification unit test)
   6.  Prospective rule is exempt from the gate
   7.  Rules verification report is generated (GET /admin/rules-verification)
   8.  Rules verification report gate_passed=True after seeding

  Production readiness:
   9.  Production readiness report is generated (GET /admin/production-readiness)
  10.  Report overall_status=NOT_PRODUCTION_READY
  11.  Report identifies encryption blockers
  12.  Report identifies DPIA blocker
  13.  Report shows model boundary as IMPLEMENTED
  14.  DP report includes priority breakdown categories

  Legal accuracy:
  15.  Legal accuracy CI gate still passes (all 38 tests)
  16.  UPW legal accuracy tests pass
  17.  UD legal accuracy tests pass

  Regressions:
  18.  Unpaid wages assessment still works
  19.  Unfair dismissal still works
  20.  Static routes still serve
  21.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase5c_verification.py -v -s
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.pipeline import assess
from backend.core.models import StubReasoningModel
from scripts.check_rules_verification import check_verification

client = TestClient(app, raise_server_exceptions=True)
STUB = StubReasoningModel()


# Phase 6: admin key for protected endpoints
_ADMIN_KEY_5C = "test-admin-5c"
_ADMIN_HDR = {"X-Admin-Key": _ADMIN_KEY_5C}


@pytest.fixture(scope="module", autouse=True)
def _set_admin_key_5c():
    os.environ["ADMIN_API_KEY"] = _ADMIN_KEY_5C
    yield
    os.environ.pop("ADMIN_API_KEY", None)


@pytest.fixture(scope="module", autouse=True)
def apply_migration_011_and_reseed():
    """Apply migration 011 (verification columns) and re-seed both rule sets."""
    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE rules ADD COLUMN IF NOT EXISTS verification_status
                    text DEFAULT 'verification_required'
            """)
            cur.execute("""
                ALTER TABLE rules ADD COLUMN IF NOT EXISTS verification_notes text
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS rules_verification_idx
                ON rules (verification_status, is_prospective)
            """)
            # Mark all prospective rules
            cur.execute("""
                UPDATE rules SET verification_status = 'prospective'
                WHERE is_prospective = true AND verification_status = 'verification_required'
            """)
        conn.commit()
    finally:
        conn.close()

    # Re-seed both rule sets with verification status
    from ingestion.rules.seed_unfair_dismissal import seed as seed_ud
    from ingestion.rules.seed_unpaid_wages import seed as seed_upw
    seed_ud()
    seed_upw()


def _get_rules(claim_type: str | None = None) -> list[dict]:
    """Helper: fetch rules from DB with verification_status."""
    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if claim_type:
                cur.execute(
                    "SELECT rule_key, claim_type, is_prospective, verification_status, "
                    "authority_ref FROM rules WHERE claim_type = %s",
                    (claim_type,),
                )
            else:
                cur.execute(
                    "SELECT rule_key, claim_type, is_prospective, verification_status, "
                    "authority_ref FROM rules"
                )
            cols = ["rule_key", "claim_type", "is_prospective", "verification_status", "authority_ref"]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


# ── 1-2. Rules have verification_status ─────────────────────────────────────

def test_unpaid_wages_rules_have_verification_status():
    rules = _get_rules("unpaid_wages")
    assert len(rules) > 0, "No UPW rules found"
    for r in rules:
        assert "verification_status" in r, f"verification_status missing for {r['rule_key']}"
        assert r["verification_status"] is not None


def test_unfair_dismissal_rules_have_verification_status():
    rules = _get_rules("unfair_dismissal")
    assert len(rules) > 0, "No UD rules found"
    for r in rules:
        assert "verification_status" in r
        assert r["verification_status"] is not None


# ── 3-4. Verified rules pass gate ─────────────────────────────────────────

def test_upw_verified_rules_pass_gate():
    rules = _get_rules("unpaid_wages")
    result = check_verification(rules)
    assert result["passed"] is True, \
        f"UPW verification gate failed. Failures: {result['failures']}"


def test_ud_verified_rules_pass_gate():
    rules = _get_rules("unfair_dismissal")
    result = check_verification(rules)
    assert result["passed"] is True, \
        f"UD verification gate failed. Failures: {result['failures']}"


# ── 5. Unverified production rule fails gate (unit test) ─────────────────

def test_unverified_production_rule_fails_gate():
    """A production rule with verification_required must fail the gate."""
    mock_rules = [
        {
            "rule_key":           "some_claim.unverified_rule",
            "claim_type":         "some_claim",
            "is_prospective":     False,
            "verification_status": "verification_required",
            "authority_ref":      "Some Act s.99",
        }
    ]
    result = check_verification(mock_rules)
    assert result["passed"] is False, "Unverified production rule must fail the gate"
    assert len(result["failures"]) > 0


def test_failed_verification_status_fails_gate():
    """A rule with status='failed' must fail the gate."""
    mock_rules = [
        {
            "rule_key":           "claim.bad_rule",
            "claim_type":         "claim",
            "is_prospective":     False,
            "verification_status": "failed",
            "authority_ref":      "Some Act",
        }
    ]
    result = check_verification(mock_rules)
    assert result["passed"] is False


# ── 6. Prospective rule exempt from gate ──────────────────────────────────

def test_prospective_rule_exempt_from_gate():
    """Prospective rules (is_prospective=true) are exempt from verification."""
    mock_rules = [
        {
            "rule_key":           "unfair_dismissal.time_limit_months",
            "claim_type":         "unfair_dismissal",
            "is_prospective":     True,
            "verification_status": "prospective",
            "authority_ref":      "ERA 2025 s.152",
        }
    ]
    result = check_verification(mock_rules)
    assert result["passed"] is True, "Prospective rule must not fail the gate"
    assert result["summary"]["prospective"] == 1


# ── 7-8. Rules verification report endpoint ───────────────────────────────

def test_rules_verification_report_generated():
    resp = client.get("/admin/rules-verification", headers=_ADMIN_HDR)
    assert resp.status_code == 200
    data = resp.json()
    assert "rules" in data
    assert "summary" in data
    assert "gate_passed" in data
    assert len(data["rules"]) > 0


def test_rules_verification_gate_passed_after_seeding():
    resp = client.get("/admin/rules-verification", headers=_ADMIN_HDR)
    data = resp.json()
    assert data["gate_passed"] is True, \
        f"Rules verification gate failed after seeding. Failures: {data.get('failures', [])}"


def test_rules_have_authority_urls():
    resp = client.get("/admin/rules-verification", headers=_ADMIN_HDR)
    data = resp.json()
    for rule in data["rules"]:
        assert rule.get("authority_ref"), f"authority_ref missing for {rule['rule_key']}"


def test_prospective_rules_in_report():
    resp = client.get("/admin/rules-verification", headers=_ADMIN_HDR)
    data = resp.json()
    prospective = [r for r in data["rules"] if r["is_prospective"]]
    assert len(prospective) > 0, "Should have at least one prospective rule"


# ── 9-14. Production readiness report ────────────────────────────────────

def test_production_readiness_report_generated():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    assert resp.status_code == 200
    data = resp.json()
    assert "overall_status" in data
    assert "claim_type_readiness" in data
    assert "legal_rules_verification" in data
    assert "data_protection" in data


def test_production_readiness_not_production_ready():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert data["overall_status"] == "NOT_PRODUCTION_READY"
    assert data["ready_for_production"] is False


def test_production_readiness_identifies_encryption_blockers():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    blockers = " ".join(data.get("overall_blockers", [])).lower()
    # Blocker wording is "hsm/kms key management not implemented" or "encryption"
    assert "hsm" in blockers or "kms" in blockers or "encryption" in blockers or "key management" in blockers, \
        f"Encryption/key-management blocker must be listed. Got: {blockers[:200]}"


def test_production_readiness_identifies_dpia_blocker():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    blockers = " ".join(data.get("overall_blockers", [])).lower()
    assert "dpia" in blockers or "data protection impact" in blockers


def test_production_readiness_model_boundary_implemented():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    mb = data.get("model_boundary", {})
    assert mb.get("status") == "IMPLEMENTED"
    assert mb.get("boundary_log_in_every_response") is True


def test_dp_report_has_priority_breakdown():
    resp = client.get("/admin/dp-report", headers=_ADMIN_HDR)
    data = resp.json()
    pb = data.get("priority_breakdown")
    assert pb is not None, "priority_breakdown missing from DP report"
    assert "launch_blockers" in pb
    assert "production_blockers" in pb
    assert "implemented" in pb
    assert len(pb["launch_blockers"]) > 0
    assert len(pb["implemented"]) > 0


# ── 15-17. Legal accuracy gate ───────────────────────────────────────────

def test_legal_accuracy_ci_gate_passes():
    result = subprocess.run(
        [sys.executable, "scripts/run_legal_accuracy.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, \
        f"Legal accuracy gate failed:\n{result.stdout}\n{result.stderr}"


def test_rules_verification_ci_gate_passes():
    result = subprocess.run(
        [sys.executable, "scripts/check_rules_verification.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, \
        f"Rules verification gate failed:\n{result.stdout}\n{result.stderr}"


# ── 18-21. Regressions ────────────────────────────────────────────────────

def test_unpaid_wages_assessment_regression():
    result = assess("My employer hasn't paid my wages", {
        "wages_due_date": "2026-03-31",
        "unpaid_amount": 2500.0,
        "worker_status": "employee",
        "jurisdiction": "EW",
    }, model=STUB)
    assert result.get("status") in ("ok", "insufficient_grounding")
    dl = result.get("deadline_info") or {}
    assert dl.get("source") == "rules"


def test_unfair_dismissal_regression():
    result = assess("I was unfairly dismissed", {
        "edt": "2026-04-01", "service_start_date": "2023-04-01",
        "reason_for_dismissal": "conduct", "weekly_pay": 600,
        "jurisdiction": "EW",
    }, model=STUB)
    dl = result.get("deadline_info") or {}
    assert dl.get("limitation_date") == "2026-06-30"
    assert dl.get("source") == "rules"


def test_static_routes_regression():
    for path in ["/", "/pages/intake.html", "/pages/assessment.html", "/pages/saved_case.html"]:
        assert client.get(path).status_code == 200


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
