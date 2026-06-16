"""Tests for Legal Truth Validator (DB-first cross-check)."""

from unittest.mock import patch, MagicMock

import pytest

from backend.core.legal_truth_validator import (
    validate_legal_truth,
    apply_validation_to_assessment,
    LegalTruthValidationResult,
)


class TestLegalTruthValidator:
    def test_ok_when_citations_verify(self):
        assessment = {
            "status": "ok",
            "citations": [{"cite": "ERA 1996 s.111", "url": "https://example.com"}],
            "rules_used": ["unfair_dismissal.time_limit_months"],
        }
        bundle = MagicMock()
        bundle.insufficient_grounding = False
        bundle.exact_rules = [{"rule_key": "unfair_dismissal.time_limit_months"}]

        with patch(
            "backend.core.citation_verifier.verify_citation",
            return_value={"verified": True, "reason": None, "method": "legislation_db"},
        ):
            result = validate_legal_truth(
                assessment,
                bundle=bundle,
                rules=[{"rule_key": "unfair_dismissal.time_limit_months"}],
            )

        assert result.passed is True
        assert result.status == "ok"

    def test_insufficient_grounding_on_citation_mismatch(self):
        assessment = {
            "status": "ok",
            "citations": [{"cite": "Fake Act 2099 s.1", "url": "https://example.com"}],
        }
        bundle = {"exact_rules": [], "authorities": [], "insufficient_grounding": False}

        with patch(
            "backend.core.citation_verifier.verify_citation",
            return_value={"verified": False, "reason": "not_in_legislation_db", "method": "legislation_db"},
        ):
            result = validate_legal_truth(assessment, bundle=bundle, rules=[])

        assert result.passed is False
        assert result.status in ("insufficient_grounding", "rejected")
        assert result.failed_count >= 1

    def test_missing_citations_on_ok_assessment(self):
        assessment = {"status": "ok", "citations": []}
        result = validate_legal_truth(assessment, bundle=None, rules=[])
        assert result.passed is False
        assert "missing_citations" in result.gaps_detected

    def test_apply_validation_blocks_assessment(self):
        assessment = {"status": "ok", "citations": []}
        vr = LegalTruthValidationResult(
            passed=False,
            status="insufficient_grounding",
            gaps_detected=["missing_citations"],
        )
        out = apply_validation_to_assessment(assessment, vr)
        assert out["status"] == "insufficient_grounding"
        assert out["insufficient_grounding"] is True

    def test_rejected_when_pipeline_already_blocked(self):
        result = validate_legal_truth({"status": "blocked"}, bundle=None, rules=[])
        assert result.passed is False
        assert result.status == "rejected"

    def test_rule_not_in_retrieval_flagged(self):
        assessment = {
            "status": "ok",
            "citations": [{"cite": "ERA 1996 s.111", "url": "https://example.com"}],
            "rules_used": ["invented.rule.key"],
        }
        with patch(
            "backend.core.citation_verifier.verify_citation",
            return_value={"verified": True, "reason": None, "method": "legislation_db"},
        ):
            result = validate_legal_truth(
                assessment,
                bundle={"exact_rules": [], "insufficient_grounding": False},
                rules=[],
            )
        assert any(m.get("kind") == "rule_not_in_retrieval" for m in result.mismatches)
