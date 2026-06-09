"""
Stage 5 — Governance gate (the honesty layer in code).

Applies five checks in order before any assessment proceeds to display.
This is the UVP made into architecture: the gate enforces what the system
promises about honesty and legal safety.

Checks (in order, per 04_RAG_REASONING_SPEC.md §6):
1. Grounding: every legal claim cited? Below threshold → strip/flag.
2. Confidence: above threshold? Below → "can't say confidently" + human route.
3. Determinism: deadline.source == "rules" (assert).
4. Boundary: no reserved-activity language, no outcome guarantee, no solicitor implication.
5. Honesty: key_weaknesses populated for non-trivial cases; weak/no-claim stated plainly.

Only a passing assessment exits the gate. Failing assessments return the
appropriate fallback response — never a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from shared.schemas import StructuredAssessment
from backend.core.score import below_threshold

# Reserved-activity phrases that must never appear in output
_RESERVED_PHRASES = [
    "we will file", "we will represent", "we will act",
    "we are your solicitor", "we are lawyers",
    "guaranteed to win", "you will win", "certain to succeed",
    "we will conduct", "rights of audience",
]

# Outcome-guarantee phrases
_GUARANTEE_PHRASES = [
    "guaranteed", "certain to", "definitely win", "you will receive",
    "you are entitled to", "you will get",
]


@dataclass
class GovernanceResult:
    passes: bool
    failure_reason: str = ""
    patched_assessment: StructuredAssessment | None = None


def govern(assessment: StructuredAssessment) -> GovernanceResult:
    """
    Run the five-check governance gate.

    Returns GovernanceResult. If passes=True, patched_assessment contains
    the final (possibly patched) assessment. If passes=False, the caller
    must use the appropriate fallback response.
    """
    # Check 1: insufficient_grounding flag (set upstream, checked here)
    if assessment.insufficient_grounding:
        return GovernanceResult(
            passes=False,
            failure_reason="insufficient_grounding: retrieval bundle too weak to support assessment",
        )

    # Check 2: grounding/confidence scores
    failed, reason = below_threshold(assessment)
    if failed:
        return GovernanceResult(passes=False, failure_reason=f"score_threshold: {reason}")

    # Check 3: determinism — deadline must come from rules, not generation
    if assessment.deadline is not None:
        if assessment.deadline.source != "rules":
            return GovernanceResult(
                passes=False,
                failure_reason=(
                    f"determinism_violation: deadline.source='{assessment.deadline.source}' "
                    f"must be 'rules'. Model generated or recalled a deadline."
                ),
            )

    # Check 4: legal boundary — no reserved-activity or outcome-guarantee language
    full_text = " ".join([
        assessment.reasoning_summary or "",
        " ".join(assessment.key_weaknesses),
    ]).lower()

    for phrase in _RESERVED_PHRASES:
        if phrase in full_text:
            return GovernanceResult(
                passes=False,
                failure_reason=f"boundary_violation: reserved-activity phrase detected: '{phrase}'",
            )
    for phrase in _GUARANTEE_PHRASES:
        if phrase in full_text:
            return GovernanceResult(
                passes=False,
                failure_reason=f"boundary_violation: outcome-guarantee phrase detected: '{phrase}'",
            )

    # Check 5: honesty — key_weaknesses required for non-trivial cases
    if assessment.has_viable_claim in ("yes", "uncertain"):
        if not assessment.key_weaknesses or all(
            w.strip() == "" for w in assessment.key_weaknesses
        ):
            return GovernanceResult(
                passes=False,
                failure_reason=(
                    "honesty_violation: key_weaknesses must be populated when "
                    "has_viable_claim is 'yes' or 'uncertain'"
                ),
            )

    return GovernanceResult(passes=True, patched_assessment=assessment)


def build_insufficient_grounding_response(reason: str = "") -> dict:
    """
    Standardised response when grounding is insufficient.
    Routed to the honesty/uncertainty path.
    """
    return {
        "status": "insufficient_grounding",
        "message": (
            "We don't have enough authority to assess your situation reliably. "
            "Fabricating an answer would be worse than admitting we can't help here. "
            "Please seek specialist employment law advice."
        ),
        "recommended_next_step": "seek_solicitor",
        "reason": reason,
    }


def build_not_supported_response(matter_type: str = "unknown") -> dict:
    """
    Standardised response for out-of-scope queries.
    Never a guess, never a hedged attempt.
    """
    return {
        "status": "not_supported",
        "matter_type": matter_type,
        "message": (
            "This service currently handles unfair dismissal claims in England and Wales only. "
            "Your query doesn't match that scope. "
            "Please seek advice appropriate to your situation."
        ),
    }


def build_low_confidence_response(assessment: StructuredAssessment, reason: str) -> dict:
    """
    Response when confidence is below threshold but grounding is adequate.
    """
    return {
        "status": "low_confidence",
        "message": (
            "We can see your situation but can't assess it confidently enough "
            "to give you a reliable answer. "
            "Please seek specialist employment law advice."
        ),
        "recommended_next_step": "seek_solicitor",
        "reason": reason,
    }
