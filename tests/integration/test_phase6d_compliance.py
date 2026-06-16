"""
Phase 6D  -  Compliance evidence structure and DPO/legal review gate tests.

Tests:
  Evidence quality gate:
   1.  Current state: controlled_beta_ready=false (reviewed=false)
   2.  Setting reviewed=true WITHOUT evidence → still blocked (insufficient)
   3.  Setting reviewed=true WITH evidence → unblocked (mechanism works)
   4.  Evidence check: reviewer_name missing → blocked
   5.  Evidence check: review_date missing → blocked
   6.  DPIA reviewed + privacy_notice reviewed + full evidence → beta-ready
   7.  Production threshold: requires approved=true not just reviewed_by_dpo
   8.  Production threshold: requires published=true for privacy notice

  Signoff file structure:
   9.  compliance-signoff.json has review_scope field
  10.  compliance-signoff.json has evidence_reference field
  11.  compliance-signoff.json has checklists referenced

  Admin compliance endpoint:
  12.  GET /admin/compliance-status returns required_evidence structure
  13.  required_evidence includes reviewer_name and review_date for each threshold
  14.  Checklists paths are present in compliance status

  Production readiness:
  15.  controlled_beta_ready remains false (DPIA not reviewed in current signoff)
  16.  Production readiness report includes compliance.required_evidence

  Regressions:
  17.  Legal accuracy gate passes
  18.  Rules verification gate passes
  19.  Admin endpoints still require key
  20.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase6d_compliance.py -v -s
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app, raise_server_exceptions=True)

_ADMIN_KEY = "test-admin-6d"
_ADMIN_HDR = {"X-Admin-Key": _ADMIN_KEY}


@pytest.fixture(scope="module", autouse=True)
def phase6d_env():
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


# ── 1-8. Evidence quality gate ────────────────────────────────────────────────

def test_current_state_controlled_beta_false():
    """Current compliance-signoff.json has reviewed=false → controlled_beta blocked."""
    from backend.domains.employment.compliance import load_signoff, check_controlled_beta
    signoff = load_signoff()
    result  = check_controlled_beta(signoff)
    assert not result["ready"], "Current state must be blocked (DPIA/privacy not reviewed)"
    assert len(result["blockers"]) > 0


def test_reviewed_true_without_evidence_still_blocked():
    """reviewed_by_dpo=true WITHOUT reviewer_name/review_date → still blocked."""
    from backend.domains.employment.compliance import check_controlled_beta
    insufficient = {
        "dpia": {
            "drafted": True,
            "reviewed_by_dpo": True,
            "approved": False,
            "reviewer_name": None,   # missing
            "review_date": None,     # missing
        },
        "privacy_notice": {
            "drafted": True,
            "legally_reviewed": True,
            "published": False,
            "reviewer_name": "Legal",
            "review_date": "2026-06-01",
        },
    }
    result = check_controlled_beta(insufficient)
    assert not result["ready"], "Boolean-only sign-off must be blocked"
    assert any("evidence" in b.lower() or "reviewer_name" in b.lower()
               for b in result["blockers"]), \
        f"Blocker must mention missing evidence: {result['blockers']}"


def test_reviewed_true_with_evidence_unblocks():
    """MECHANISM TEST: reviewed=true WITH evidence → controlled_beta_ready=true."""
    from backend.domains.employment.compliance import check_controlled_beta
    full_evidence = {
        "dpia": {
            "drafted": True,
            "reviewed_by_dpo": True,
            "approved": False,
            "reviewer_name": "Jane Smith, DPO",
            "review_date": "2026-06-01",
            "review_scope": "Full DPIA review per checklist v6D",
            "evidence_reference": "Meeting note REF-2026-001",
        },
        "privacy_notice": {
            "drafted": True,
            "legally_reviewed": True,
            "published": False,
            "reviewer_name": "Legal Counsel Ltd",
            "review_date": "2026-06-01",
            "review_scope": "Privacy notice legal review per checklist v6D",
            "evidence_reference": "Engagement letter EL-2026-042",
        },
    }
    result = check_controlled_beta(full_evidence)
    assert result["ready"] is True, \
        f"With full evidence, controlled beta should be unblocked: {result['blockers']}"
    assert result["blockers"] == []


def test_missing_reviewer_name_blocks():
    from backend.domains.employment.compliance import check_controlled_beta
    no_name = {
        "dpia": {
            "drafted": True, "reviewed_by_dpo": True,
            "reviewer_name": None, "review_date": "2026-06-01",
        },
        "privacy_notice": {
            "drafted": True, "legally_reviewed": True,
            "reviewer_name": "Legal", "review_date": "2026-06-01",
        },
    }
    result = check_controlled_beta(no_name)
    assert not result["ready"]
    assert any("reviewer_name" in b for b in result["blockers"])


def test_missing_review_date_blocks():
    from backend.domains.employment.compliance import check_controlled_beta
    no_date = {
        "dpia": {
            "drafted": True, "reviewed_by_dpo": True,
            "reviewer_name": "DPO", "review_date": None,  # missing
        },
        "privacy_notice": {
            "drafted": True, "legally_reviewed": True,
            "reviewer_name": "Legal", "review_date": "2026-06-01",
        },
    }
    result = check_controlled_beta(no_date)
    assert not result["ready"]
    assert any("review_date" in b for b in result["blockers"])


def test_full_evidence_both_sections_unblocks_beta():
    """Both DPIA and privacy with full evidence → beta ready."""
    from backend.domains.employment.compliance import check_controlled_beta
    both_ok = {
        "dpia": {
            "drafted": True, "reviewed_by_dpo": True, "approved": False,
            "reviewer_name": "DPO Name", "review_date": "2026-06-01",
        },
        "privacy_notice": {
            "drafted": True, "legally_reviewed": True, "published": False,
            "reviewer_name": "Lawyer Name", "review_date": "2026-06-01",
        },
    }
    result = check_controlled_beta(both_ok)
    assert result["ready"] is True
    assert result["blockers"] == []


def test_production_requires_approved_not_just_reviewed():
    """Production needs approved=true; reviewed_by_dpo alone is not enough."""
    from backend.domains.employment.compliance import check_production
    only_reviewed = {
        "dpia": {
            "drafted": True, "reviewed_by_dpo": True, "approved": False,
            "reviewer_name": "DPO", "review_date": "2026-06-01",
        },
        "privacy_notice": {
            "drafted": True, "legally_reviewed": True, "published": True,
            "reviewer_name": "Legal", "review_date": "2026-06-01",
        },
    }
    result = check_production(only_reviewed)
    assert not result["ready"]
    assert any("approved" in b.lower() for b in result["blockers"])


def test_production_requires_published_privacy_notice():
    """Production needs privacy notice published; legally_reviewed alone is not enough."""
    from backend.domains.employment.compliance import check_production
    not_published = {
        "dpia": {
            "drafted": True, "approved": True,
            "reviewer_name": "DPO", "review_date": "2026-06-01",
        },
        "privacy_notice": {
            "drafted": True, "legally_reviewed": True, "published": False,
            "reviewer_name": "Legal", "review_date": "2026-06-01",
        },
    }
    result = check_production(not_published)
    assert not result["ready"]
    assert any("published" in b.lower() for b in result["blockers"])


# ── 9-11. Signoff file structure ──────────────────────────────────────────────

def test_compliance_signoff_has_review_scope_field():
    from backend.domains.employment.compliance import load_signoff
    signoff = load_signoff()
    assert "review_scope" in signoff.get("dpia", {}), \
        "compliance-signoff.json dpia must have review_scope field"
    assert "review_scope" in signoff.get("privacy_notice", {}), \
        "compliance-signoff.json privacy_notice must have review_scope field"


def test_compliance_signoff_has_evidence_reference_field():
    from backend.domains.employment.compliance import load_signoff
    signoff = load_signoff()
    assert "evidence_reference" in signoff.get("dpia", {})
    assert "evidence_reference" in signoff.get("privacy_notice", {})


def test_compliance_status_includes_checklists():
    from backend.domains.employment.compliance import get_compliance_status
    status = get_compliance_status()
    checklists = status.get("checklists", {})
    assert "dpia" in checklists
    assert "privacy_notice" in checklists
    assert "review-checklist" in checklists["dpia"].lower()
    assert "review-checklist" in checklists["privacy_notice"].lower()


# ── 12-14. Admin compliance endpoint ─────────────────────────────────────────

def test_compliance_endpoint_returns_required_evidence():
    resp = client.get("/admin/compliance-status", headers=_ADMIN_HDR)
    assert resp.status_code == 200
    data = resp.json()
    req  = data.get("required_evidence", {})
    assert "controlled_beta" in req
    assert "production" in req


def test_required_evidence_specifies_mandatory_fields():
    resp = client.get("/admin/compliance-status", headers=_ADMIN_HDR)
    data = resp.json()
    dpia_req = data["required_evidence"]["controlled_beta"]["dpia"]
    assert "reviewer_name" in dpia_req["required_fields"]
    assert "review_date"   in dpia_req["required_fields"]
    assert "guidance" in dpia_req


def test_compliance_endpoint_returns_checklist_paths():
    resp = client.get("/admin/compliance-status", headers=_ADMIN_HDR)
    data = resp.json()
    assert "checklists" in data
    assert "dpia-review-checklist.md" in data["checklists"]["dpia"]
    assert "privacy-review-checklist.md" in data["checklists"]["privacy_notice"]


# ── 15-16. Production readiness ───────────────────────────────────────────────

def test_controlled_beta_ready_remains_false_current_state():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert data["controlled_beta_ready"] is False, \
        "Controlled beta must remain FALSE  -  DPIA and privacy not yet reviewed"


def test_production_readiness_compliance_has_required_evidence():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    comp = data.get("compliance", {})
    assert "required_evidence" in comp, \
        "Compliance section must include required_evidence from Phase 6D"


# ── 17-20. Regressions ────────────────────────────────────────────────────────

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


def test_admin_endpoints_still_require_key():
    assert client.get("/admin/dp-report").status_code == 403
    assert client.get("/admin/compliance-status").status_code == 403
    assert client.get("/admin/production-readiness").status_code == 403


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
