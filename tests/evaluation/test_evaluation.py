"""
Legal Evaluation AI tests.

Tests that the evaluation rubric correctly:
  - Blocks guarantee language
  - Blocks reserved activity language
  - Catches wrong deadlines
  - Passes valid assessments
  - Requires weaknesses for viable claims
  - Rejects PII in output
"""

import pytest
from backend.core.evaluator import evaluate_assessment


_BASE_ASSESSMENT = {
    "status": "ok",
    "has_viable_claim": "yes",
    "reasoning_summary": "Based on ERA 1996, the dismissal appears unfair.",
    "key_weaknesses": ["Procedure followed  -  weakens claim"],
    "citations": [{"cite": "ERA 1996 s.111", "url": "https://legislation.gov.uk/ukpga/1996/18/section/111/data.xml"}],
    "deadline_info": {"limitation_date": "2025-12-31", "source": "rules", "authority": "ERA 1996 s.111(2)"},
    "jurisdiction": "EW",
    "boundary_log": {"pii_in_output": []},
}

_BASE_FACTS = {"jurisdiction": "EW", "edt": "2025-10-01"}


class TestEvaluationPass:
    def test_valid_assessment_passes(self):
        result = evaluate_assessment(_BASE_ASSESSMENT, _BASE_FACTS)
        assert result["passed"] is True

    def test_insufficient_grounding_passes_evaluation(self):
        assessment = {"status": "insufficient_grounding", "message": "Not enough info."}
        result = evaluate_assessment(assessment, _BASE_FACTS)
        assert result["passed"] is True

    def test_not_supported_passes_evaluation(self):
        assessment = {"status": "not_supported", "message": "Out of scope."}
        result = evaluate_assessment(assessment, _BASE_FACTS)
        assert result["passed"] is True


class TestEvaluationFail:
    def test_guarantee_language_fails(self):
        assessment = {**_BASE_ASSESSMENT,
                      "reasoning_summary": "You are guaranteed to win your case."}
        result = evaluate_assessment(assessment, _BASE_FACTS)
        assert result["passed"] is False
        assert any("guarantee" in f for f in result["failures"])

    def test_reserved_activity_fails(self):
        assessment = {**_BASE_ASSESSMENT,
                      "reasoning_summary": "lawapp will file your ET1 on your behalf."}
        result = evaluate_assessment(assessment, _BASE_FACTS)
        assert result["passed"] is False
        assert any("reserved_activity" in f for f in result["failures"])

    def test_wrong_ud_deadline_fails(self):
        assessment = {**_BASE_ASSESSMENT,
                      "reasoning_summary": "You have 6 months to bring unfair dismissal claim."}
        result = evaluate_assessment(assessment, _BASE_FACTS)
        assert result["passed"] is False
        assert any("incorrect_deadline" in f for f in result["failures"])

    def test_viable_claim_without_weaknesses_fails(self):
        assessment = {**_BASE_ASSESSMENT, "key_weaknesses": []}
        result = evaluate_assessment(assessment, _BASE_FACTS)
        assert result["passed"] is False
        assert any("weaknesses" in f for f in result["failures"])

    def test_pii_in_output_fails(self):
        assessment = {**_BASE_ASSESSMENT,
                      "boundary_log": {"pii_in_output": ["full_name"]}}
        result = evaluate_assessment(assessment, _BASE_FACTS)
        assert result["passed"] is False
        assert any("pii_in_output" in f for f in result["failures"])

    def test_deadline_not_from_rules_fails(self):
        assessment = {**_BASE_ASSESSMENT,
                      "deadline_info": {"limitation_date": "2025-12-31", "source": "model_estimate"}}
        result = evaluate_assessment(assessment, _BASE_FACTS)
        assert result["passed"] is False
        assert any("deadline_not_from_rules" in f for f in result["failures"])


class TestEvaluationChecks:
    def test_evaluation_returns_checks_list(self):
        result = evaluate_assessment(_BASE_ASSESSMENT, _BASE_FACTS)
        assert isinstance(result["checks"], list)
        assert len(result["checks"]) > 0

    def test_each_check_has_required_fields(self):
        result = evaluate_assessment(_BASE_ASSESSMENT, _BASE_FACTS)
        for check in result["checks"]:
            assert "check" in check
            assert "passed" in check
            assert "severity" in check

    def test_critical_failures_counted(self):
        assessment = {**_BASE_ASSESSMENT,
                      "boundary_log": {"pii_in_output": ["email"]}}
        result = evaluate_assessment(assessment, _BASE_FACTS)
        assert result["critical_failures"] >= 1
