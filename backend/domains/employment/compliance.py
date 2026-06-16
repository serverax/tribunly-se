"""
Compliance sign-off reader and evidence validator  -  Phase 6D.

Reads docs/compliance-signoff.json and determines whether the system
meets controlled-beta and production compliance thresholds.

Phase 6D: Evidence quality gate added.
  - reviewer_name AND review_date are REQUIRED alongside boolean flags.
  - Setting reviewed_by_dpo=true WITHOUT these fields is still blocked.
  - required_evidence() lists exactly what is needed for each threshold.

GUARDRAIL: Do not mark approved/reviewed unless signoff file explicitly says so.
GUARDRAIL: A boolean flag alone is not sufficient  -  evidence fields are mandatory.
GUARDRAIL: Signoff file is single source of truth  -  no env var overrides.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Repo root is four levels up: backend/domains/employment/compliance.py → <root>
_SIGNOFF_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "compliance-signoff.json"
)


def load_signoff() -> dict:
    """Load the compliance sign-off file. Never invents approved/reviewed state."""
    if not _SIGNOFF_PATH.exists():
        logger.warning("compliance-signoff.json not found at %s", _SIGNOFF_PATH)
        return {
            "dpia": {"drafted": False, "reviewed_by_dpo": False, "approved": False,
                     "reviewer_name": None, "review_date": None, "approval_date": None,
                     "review_scope": None, "evidence_reference": None},
            "privacy_notice": {"drafted": False, "legally_reviewed": False, "published": False,
                               "reviewer_name": None, "review_date": None, "publish_date": None,
                               "review_scope": None, "evidence_reference": None},
        }
    try:
        return json.loads(_SIGNOFF_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to read compliance-signoff.json: %s", exc)
        return {}


def _evidence_ok(section: dict) -> tuple[bool, list[str]]:
    """
    Check that a signed-off section has required evidence fields.
    A boolean flag alone is not sufficient evidence of genuine review.
    Required: reviewer_name AND review_date.
    """
    missing: list[str] = []
    if not section.get("reviewer_name"):
        missing.append("reviewer_name")
    if not section.get("review_date"):
        missing.append("review_date")
    return len(missing) == 0, missing


def required_evidence() -> dict:
    """Return exactly what evidence is required for each compliance threshold."""
    return {
        "controlled_beta": {
            "dpia": {
                "required_flag":   "reviewed_by_dpo=true OR approved=true",
                "required_fields": ["reviewer_name", "review_date"],
                "optional_fields": ["review_scope", "evidence_reference"],
                "guidance":        "docs/dpia-review-checklist.md",
            },
            "privacy_notice": {
                "required_flag":   "legally_reviewed=true",
                "required_fields": ["reviewer_name", "review_date"],
                "optional_fields": ["review_scope", "evidence_reference"],
                "guidance":        "docs/privacy-review-checklist.md",
            },
        },
        "production": {
            "dpia": {
                "required_flag":   "approved=true",
                "required_fields": ["reviewer_name", "approval_date"],
                "optional_fields": ["review_scope", "evidence_reference"],
                "guidance":        "docs/dpia-review-checklist.md",
            },
            "privacy_notice": {
                "required_flag":   "published=true",
                "required_fields": ["reviewer_name", "publish_date"],
                "optional_fields": ["review_scope", "evidence_reference"],
                "guidance":        "docs/privacy-review-checklist.md",
            },
        },
    }


def check_controlled_beta(signoff: dict) -> dict:
    """
    Check compliance for controlled beta.

    Controlled-beta threshold:
      - DPIA: (reviewed_by_dpo OR approved) + reviewer_name + review_date
      - Privacy notice: legally_reviewed + reviewer_name + review_date
    """
    blockers: list[str] = []
    dpia = signoff.get("dpia", {})
    pn   = signoff.get("privacy_notice", {})

    # DPIA
    if not dpia.get("drafted", False):
        blockers.append("DPIA not drafted  -  create artefact at docs/dpia-artefact.md")
    elif not (dpia.get("reviewed_by_dpo", False) or dpia.get("approved", False)):
        blockers.append(
            "DPIA not reviewed by DPO or approved. "
            "Complete docs/dpia-review-checklist.md and update compliance-signoff.json."
        )
    else:
        ok, missing = _evidence_ok(dpia)
        if not ok:
            blockers.append(
                f"DPIA sign-off flag set but lacks required evidence: {missing}. "
                "A boolean flag alone is not sufficient  -  add reviewer_name and review_date."
            )

    # Privacy notice
    if not pn.get("drafted", False):
        blockers.append("Privacy notice not drafted  -  create at docs/privacy-notice-draft.md")
    elif not pn.get("legally_reviewed", False):
        blockers.append(
            "Privacy notice not legally reviewed. "
            "Complete docs/privacy-review-checklist.md and update compliance-signoff.json."
        )
    else:
        ok, missing = _evidence_ok(pn)
        if not ok:
            blockers.append(
                f"Privacy notice sign-off flag set but lacks required evidence: {missing}. "
                "A boolean flag alone is not sufficient  -  add reviewer_name and review_date."
            )

    return {"ready": len(blockers) == 0, "blockers": blockers}


def check_production(signoff: dict) -> dict:
    """Check compliance for full production (higher bar: approved + published)."""
    blockers: list[str] = []
    dpia = signoff.get("dpia", {})
    pn   = signoff.get("privacy_notice", {})

    if not dpia.get("approved", False):
        blockers.append("DPIA not approved  -  full legal sign-off required for production.")
    else:
        ok, missing = _evidence_ok(dpia)
        if not ok:
            blockers.append(f"DPIA approval lacks required evidence: {missing}")

    if not pn.get("published", False):
        blockers.append("Privacy notice not published  -  must be live for production.")
    else:
        ok, missing = _evidence_ok(pn)
        if not ok:
            blockers.append(f"Privacy notice publication lacks required evidence: {missing}")

    return {"ready": len(blockers) == 0, "blockers": blockers}


def get_compliance_status() -> dict:
    """Return full compliance status including thresholds, blockers, and required evidence."""
    signoff = load_signoff()
    cb      = check_controlled_beta(signoff)
    prod    = check_production(signoff)

    return {
        "signoff":                        signoff,
        "controlled_beta_ready":          cb["ready"],
        "controlled_beta_blockers":       cb["blockers"],
        "production_compliance_ready":    prod["ready"],
        "production_compliance_blockers": prod["blockers"],
        "required_evidence":              required_evidence(),
        "signoff_file_path":              str(_SIGNOFF_PATH),
        "signoff_file_exists":            _SIGNOFF_PATH.exists(),
        "checklists": {
            "dpia":           "docs/dpia-review-checklist.md",
            "privacy_notice": "docs/privacy-review-checklist.md",
        },
    }
