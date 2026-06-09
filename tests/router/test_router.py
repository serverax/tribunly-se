"""
AI Router tests.

Tests that the router correctly routes to the appropriate processing path
based on query complexity, risk level, and personal facts presence.
"""

import pytest
from backend.core.router import route, RoutingDecision


class TestRouterPaths:
    def test_generic_question_routes_to_lite_llm(self):
        decision = route("What is unfair dismissal?", {})
        assert decision.path == "lite_llm_plus_glossary"
        assert decision.lite_llm_safe is True
        assert decision.risk_level == "low"

    def test_generic_acas_question_routes_to_lite_llm(self):
        decision = route("What is ACAS early conciliation?", {})
        assert decision.path == "lite_llm_plus_glossary"
        assert decision.lite_llm_safe is True

    def test_personal_case_routes_to_full_pipeline(self):
        decision = route("I was dismissed after 3 years for conduct", {
            "edt": "2025-10-01",
            "service_start_date": "2022-01-01",
        })
        assert "full_legal_pipeline" in decision.path
        assert decision.lite_llm_safe is False

    def test_deadline_only_routes_to_rules_engine(self):
        decision = route("When is my claim deadline?", {
            "edt": "2025-10-01",
        })
        assert decision.path == "rules_engine_only" or decision.use_rules_engine is True

    def test_whistleblowing_routes_to_high_risk(self):
        decision = route("I was dismissed after whistleblowing", {
            "edt": "2025-10-01",
        })
        assert decision.risk_level == "high"
        assert decision.human_review_flag is True
        assert "human_review" in decision.agents

    def test_discrimination_routes_to_high_risk(self):
        decision = route("I was dismissed due to my disability", {"edt": "2025-10-01"})
        assert decision.risk_level == "high"
        assert decision.evaluation_required is True

    def test_settlement_agreement_requires_human_review(self):
        decision = route("Can you help me with a settlement agreement?", {})
        assert decision.human_review_flag is True or decision.risk_level == "high"

    def test_personal_facts_disable_lite_llm(self):
        decision = route("What is unfair dismissal?", {
            "edt": "2025-10-01",
            "service_start_date": "2022-01-01",
        })
        assert decision.lite_llm_safe is False

    def test_full_pipeline_requires_evaluation(self):
        decision = route("I was dismissed", {
            "edt": "2025-10-01",
            "service_start_date": "2022-01-01",
        })
        if "full" in decision.path:
            assert decision.evaluation_required is True

    def test_routing_decision_to_dict(self):
        decision = route("I was dismissed", {"edt": "2025-10-01"})
        d = decision.to_dict()
        required_keys = [
            "selected_path", "risk_level", "agents", "use_llm",
            "use_rag", "use_rules_engine", "evaluation_required",
            "human_review_flag", "reason", "lite_llm_safe",
        ]
        for key in required_keys:
            assert key in d, f"Missing key: {key}"

    def test_agents_list_not_empty(self):
        decision = route("I was dismissed", {})
        assert len(decision.agents) > 0


class TestRouterGuardrails:
    def test_lite_llm_safe_never_for_personal_facts(self):
        """GUARDRAIL: Lite LLM must never be used with personal case facts."""
        personal_queries = [
            ("I was dismissed yesterday", {"edt": "2025-10-01"}),
            ("My employer dismissed me after 5 years", {"service_start_date": "2020-01-01"}),
            ("When is my wages claim deadline?", {"wages_due_date": "2025-09-01"}),
        ]
        for query, facts in personal_queries:
            decision = route(query, facts)
            assert decision.lite_llm_safe is False, \
                f"lite_llm_safe=True for personal query: {query}"
