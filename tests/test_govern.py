"""
Tests for the governance gate.

No DB, no model. Tests all five checks and all fallback paths.
"""

from datetime import date
from shared.schemas import Citation, Deadline, StructuredAssessment, ValueRange
from backend.core.govern import (
    govern, build_not_supported_response, build_insufficient_grounding_response,
)
from backend.core.score import GROUNDING_THRESHOLD, CONFIDENCE_THRESHOLD


def _make_assessment(**kwargs) -> StructuredAssessment:
    defaults = dict(
        claim_type="unfair_dismissal",
        jurisdiction="EW",
        has_viable_claim="yes",
        strength="medium",
        reasoning_summary="Employee was dismissed without a fair process.",
        value_range=ValueRange(low=5000, high=15000, currency="GBP", basis="rules"),
        key_weaknesses=["Short service may affect compensation."],
        deadline=Deadline(
            limitation_date=date(2026, 8, 9),
            source="rules",
            authority="ERA 1996 s.111(2)",
        ),
        recommended_next_step="prepare_documents",
        citations=[Citation(cite="ERA 1996 s.98", url="https://legislation.gov.uk/...")],
        grounding_score=0.8,
        confidence_score=0.7,
        insufficient_grounding=False,
    )
    defaults.update(kwargs)
    return StructuredAssessment(**defaults)


# ── Check 1: insufficient_grounding flag ─────────────────────────────────────

def test_insufficient_grounding_blocks():
    a = _make_assessment(insufficient_grounding=True)
    result = govern(a)
    assert result.passes is False
    assert "insufficient_grounding" in result.failure_reason


# ── Check 2: score thresholds ─────────────────────────────────────────────────

def test_low_grounding_score_blocks():
    a = _make_assessment(grounding_score=GROUNDING_THRESHOLD - 0.01)
    result = govern(a)
    assert result.passes is False
    assert "score_threshold" in result.failure_reason

def test_low_confidence_score_blocks():
    a = _make_assessment(confidence_score=CONFIDENCE_THRESHOLD - 0.01)
    result = govern(a)
    assert result.passes is False
    assert "score_threshold" in result.failure_reason

def test_both_scores_above_threshold_passes():
    a = _make_assessment(
        grounding_score=GROUNDING_THRESHOLD + 0.1,
        confidence_score=CONFIDENCE_THRESHOLD + 0.1,
    )
    result = govern(a)
    # May still fail on other checks — just verify scores aren't the reason
    if not result.passes:
        assert "score_threshold" not in result.failure_reason


# ── Check 3: determinism — deadline.source must be "rules" ───────────────────

def test_pydantic_enforces_rules_source():
    """
    Pydantic's Literal["rules"] on Deadline.source rejects any other value
    at construction time. This is the enforcement point — governance check 3
    is belt-and-suspenders for JSON parsed from model output. The schema
    itself is the primary guard.
    """
    import pytest as _pytest
    with _pytest.raises(Exception):  # pydantic ValidationError
        Deadline(
            limitation_date=date(2026, 8, 9),
            source="model",   # invalid — Pydantic rejects this
            authority="ERA 1996 s.111(2)",
        )

def test_rules_deadline_source_passes_check3():
    a = _make_assessment(
        deadline=Deadline(
            limitation_date=date(2026, 8, 9),
            source="rules",
            authority="ERA 1996 s.111(2)",
        )
    )
    result = govern(a)
    if not result.passes:
        assert "determinism_violation" not in result.failure_reason


# ── Check 4: legal boundary ───────────────────────────────────────────────────

def test_reserved_activity_phrase_blocked():
    a = _make_assessment(
        reasoning_summary="We will file your claim at the tribunal next week."
    )
    result = govern(a)
    assert result.passes is False
    assert "boundary_violation" in result.failure_reason

def test_outcome_guarantee_blocked():
    a = _make_assessment(
        reasoning_summary="You are guaranteed to win this claim and receive compensation."
    )
    result = govern(a)
    assert result.passes is False
    assert "boundary_violation" in result.failure_reason


# ── Check 5: honesty — key_weaknesses required for non-trivial cases ──────────

def test_missing_weaknesses_blocked_for_viable_claim():
    a = _make_assessment(has_viable_claim="yes", key_weaknesses=[])
    result = govern(a)
    assert result.passes is False
    assert "honesty_violation" in result.failure_reason

def test_missing_weaknesses_blocked_for_uncertain():
    a = _make_assessment(has_viable_claim="uncertain", key_weaknesses=[""])
    result = govern(a)
    assert result.passes is False
    assert "honesty_violation" in result.failure_reason

def test_weaknesses_required_not_for_no_claim():
    # "no" claim — governance doesn't require weaknesses (it's already the honest answer)
    a = _make_assessment(
        has_viable_claim="no",
        strength="low",
        key_weaknesses=[],
        recommended_next_step="free_diagnosis_only",
    )
    result = govern(a)
    if not result.passes:
        assert "honesty_violation" not in result.failure_reason


# ── Passing assessment ────────────────────────────────────────────────────────

def test_clean_assessment_passes_all_checks():
    a = _make_assessment(
        grounding_score=0.8,
        confidence_score=0.7,
        insufficient_grounding=False,
        deadline=Deadline(
            limitation_date=date(2026, 8, 9),
            source="rules",
            authority="ERA 1996 s.111(2)",
        ),
        reasoning_summary="Employee was dismissed for alleged misconduct without a fair process.",
        key_weaknesses=["Short service.", "Employer may argue conduct was gross misconduct."],
    )
    result = govern(a)
    assert result.passes is True
    assert result.patched_assessment is not None


# ── Fallback response builders ────────────────────────────────────────────────

def test_not_supported_response_structure():
    r = build_not_supported_response("tenancy")
    assert r["status"] == "not_supported"
    assert r["matter_type"] == "tenancy"
    assert any(phrase in r["message"].lower() for phrase in [
        "not supported", "not currently", "currently handles", "only", "scope"
    ])

def test_insufficient_grounding_response_routes_to_solicitor():
    r = build_insufficient_grounding_response("test reason")
    assert r["status"] == "insufficient_grounding"
    assert r["recommended_next_step"] == "seek_solicitor"
