"""
Governance engine  -  wraps legal_truth_validator + citation guard.

Returns PASS | FAIL | ESCALATE | HUMAN_REVIEW for control plane metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.core.legal_truth_validator import validate_assessment_truth


GovernanceVerdict = str  # PASS | FAIL | ESCALATE | HUMAN_REVIEW


@dataclass
class GovernanceOutcome:
    verdict: GovernanceVerdict
    passed: bool
    failures: list[str]
    checks: list[dict]
    human_review: bool = False
    escalate: bool = False

    def to_metadata(self) -> dict:
        return {
            "governance_verdict": self.verdict,
            "governance_passed": self.passed,
            "governance_failures": self.failures,
            "governance_checks": self.checks,
            "human_review_required": self.human_review,
            "escalate": self.escalate,
        }


class GovernanceEngine:
    """Evaluate governed assessment output before user delivery."""

    def evaluate(self, assessment: dict, *, trace_id: Optional[str] = None) -> GovernanceOutcome:
        truth = validate_assessment_truth(assessment, trace_id=trace_id)
        gov = assessment.get("governance_result") or {}
        status = assessment.get("status", "")

        human_review = False
        escalate = False
        verdict: GovernanceVerdict = "FAIL"

        if status in ("not_supported", "insufficient_grounding", "low_confidence"):
            if status == "insufficient_grounding":
                escalate = True
                verdict = "ESCALATE"
            else:
                verdict = "FAIL"
        elif truth.passed and gov.get("passes") is True:
            verdict = "PASS"
        elif assessment.get("recommended_next_step") == "human_review":
            human_review = True
            verdict = "HUMAN_REVIEW"
        elif not truth.passed:
            if any("citation" in f for f in truth.failures):
                escalate = True
                verdict = "ESCALATE"
            else:
                verdict = "FAIL"
        else:
            verdict = "HUMAN_REVIEW" if gov.get("passes") is False else "FAIL"
            human_review = gov.get("passes") is False

        orch = assessment.get("orchestration") or assessment.get("orchestration_summary") or {}
        if orch.get("human_review_required"):
            human_review = True
            if verdict == "PASS":
                verdict = "HUMAN_REVIEW"

        deadline = assessment.get("deadline_info") or {}
        if isinstance(deadline, dict) and deadline.get("urgency_level") in ("critical", "expired"):
            human_review = True
            verdict = "HUMAN_REVIEW"
            escalate = False

        return GovernanceOutcome(
            verdict=verdict,
            passed=verdict == "PASS",
            failures=truth.failures,
            checks=truth.checks,
            human_review=human_review,
            escalate=escalate,
        )
