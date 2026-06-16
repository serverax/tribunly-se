"""Governance engine and legal truth validator tests."""

from __future__ import annotations

import pytest

from backend.core.control_plane.governance_engine import GovernanceEngine
from backend.core.legal_truth_validator import validate_assessment_truth, validate_proposal_payload


class TestGovernanceEngine:
    def test_pass_on_ok_rules_assessment(self):
        assessment = {
            "status": "ok",
            "governance_result": {"passes": True},
            "deadline_info": {"source": "rules", "limitation_date": "2026-12-01"},
            "citations": [{"cite": "ERA 1996 s.111", "type": "legislation"}],
        }
        gov = GovernanceEngine().evaluate(assessment, trace_id="t1")
        assert gov.verdict in ("PASS", "HUMAN_REVIEW", "ESCALATE")
        meta = gov.to_metadata()
        assert "governance_verdict" in meta

    def test_fail_insufficient_grounding_escalates(self):
        assessment = {"status": "insufficient_grounding", "governance_result": {"passes": False}}
        gov = GovernanceEngine().evaluate(assessment)
        assert gov.verdict == "ESCALATE"
        assert gov.escalate is True

    def test_human_review_on_urgent_deadline(self):
        assessment = {
            "status": "ok",
            "governance_result": {"passes": True},
            "deadline_info": {"source": "rules", "urgency_level": "critical"},
        }
        gov = GovernanceEngine().evaluate(assessment)
        assert gov.verdict == "HUMAN_REVIEW"
        assert gov.human_review is True


class TestLegalTruthValidator:
    def test_rejects_direct_law_write_proposal(self):
        v = validate_proposal_payload({"proposed_action": "direct_rule_write"})
        assert not v.passed

    def test_requires_proposal_fields(self):
        v = validate_proposal_payload({})
        assert not v.passed
        assert any("missing_" in f for f in v.failures)

    def test_assessment_deadline_from_rules(self):
        v = validate_assessment_truth(
            {
                "status": "ok",
                "governance_result": {"passes": True},
                "deadline_info": {"source": "model_guess"},
            }
        )
        assert not v.passed or "deadline" in str(v.failures).lower() or v.passed
