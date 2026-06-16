"""
Legal truth validator  -  DB-backed citation and rule integrity checks.

GUARDRAIL: Validates against existing DB rows only. Never writes law tables.
Used by GovernanceEngine and the Mother control plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LegalTruthVerdict:
    passed: bool
    failures: list[str] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "failures": self.failures,
            "checks": self.checks,
        }


def validate_assessment_truth(assessment: dict, *, trace_id: Optional[str] = None) -> LegalTruthVerdict:
    """
    Run legal-truth checks on a governed assessment dict.

    Combines pipeline governance, brain safety policy, and citation verification.
    """
    failures: list[str] = []
    checks: list[dict] = []

    gov = assessment.get("governance_result") or {}
    gov_pass = gov.get("passes") is True
    checks.append({"check": "governance_passes", "passed": gov_pass})
    if not gov_pass:
        failures.append(gov.get("failure_reason") or "governance_failed")

    try:
        from backend.core.brain import _run_safety_checks

        safety = _run_safety_checks(
            assessment, trace_id or assessment.get("trace_id") or "", None
        )
        checks.append({"check": "safety_policy", "passed": safety.get("passed", False)})
        if safety.get("blocked"):
            failures.extend(safety.get("failures") or [])
    except Exception as exc:
        checks.append({"check": "safety_policy", "passed": False, "error": str(exc)})
        failures.append("safety_policy_unavailable")

    cites = assessment.get("citations") or []
    if cites and isinstance(cites[0], dict):
        try:
            from backend.core.citation_verifier import verify_bundle_citations

            v = verify_bundle_citations(cites)
            cite_ok = v.get("failed", 1) == 0
            checks.append({
                "check": "citation_db_integrity",
                "passed": cite_ok,
                "verified": v.get("verified"),
                "total": v.get("total"),
            })
            if not cite_ok:
                failures.append("citation_verification_failed")
        except Exception as exc:
            checks.append({"check": "citation_db_integrity", "passed": False, "error": str(exc)})
            failures.append("citation_verification_unavailable")

    deadline = assessment.get("deadline_info") or assessment.get("deadline") or {}
    if isinstance(deadline, dict) and deadline:
        src = deadline.get("source", "")
        dl_ok = src in ("rules", "rules_engine") or not deadline.get("limitation_date")
        checks.append({"check": "deadline_from_rules", "passed": dl_ok, "source": src})
        if not dl_ok:
            failures.append("deadline_not_from_rules")

    return LegalTruthVerdict(passed=len(failures) == 0, failures=failures, checks=checks)


def validate_proposal_payload(payload: dict) -> LegalTruthVerdict:
    """Validate an ingestion proposal before queue insert (no direct law writes)."""
    failures: list[str] = []
    checks: list[dict] = []

    for key in ("source_type", "authority_ref", "content_hash"):
        ok = bool(payload.get(key))
        checks.append({"check": f"proposal_{key}", "passed": ok})
        if not ok:
            failures.append(f"missing_{key}")

    if payload.get("proposed_action") in ("direct_rule_write", "direct_legislation_write"):
        checks.append({"check": "no_direct_law_write", "passed": False})
        failures.append("direct_law_write_forbidden")

    return LegalTruthVerdict(passed=len(failures) == 0, failures=failures, checks=checks)
