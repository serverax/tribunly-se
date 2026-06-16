"""
Brain Algorithm unit tests  -  Phase 1 (19-step Brain).

Tests the 19-step Brain Algorithm in isolation using StubReasoningModel.
No real LLM calls. No external network required.
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.core.brain import run_brain, BrainTrace, _AGENT_MAP, BRAIN_STEPS
from backend.core.models import StubReasoningModel

STUB = StubReasoningModel()

_UD_FACTS = {
    "edt":                "2025-10-01",
    "service_start_date": "2022-01-01",
    "reason_for_dismissal": "conduct",
    "was_procedure_followed": False,
    "weekly_pay": 700,
    "jurisdiction": "EW",
}

_UPW_FACTS = {
    "wages_due_date": "2025-11-01",
    "unpaid_amount": 1500,
    "jurisdiction": "EW",
}


# ── BrainTrace unit tests ─────────────────────────────────────────────────────

class TestBrainTrace:
    def test_trace_records_steps(self):
        trace = BrainTrace("t1", "2026-01-01T00:00:00Z")
        trace.record_step("authenticate", "ok", {"user_id_present": True})
        assert len(trace.steps) == 1
        assert trace.steps[0]["step"] == "authenticate"
        assert trace.steps[0]["status"] == "ok"

    def test_trace_to_dict_has_all_fields(self):
        trace = BrainTrace("t2", "2026-01-01T00:00:00Z")
        d = trace.to_dict()
        required_fields = [
            "trace_id", "started_at", "jurisdiction", "claim_type",
            "agents_selected", "missing_facts", "rag_sources",
            "evaluation_passed", "safety_passed", "final_status", "steps",
        ]
        for field in required_fields:
            assert field in d, f"Missing field: {field}"

    def test_trace_id_preserved(self):
        trace = BrainTrace("my-trace-id", "2026-01-01T00:00:00Z")
        assert trace.to_dict()["trace_id"] == "my-trace-id"

    def test_trace_step_has_ts(self):
        trace = BrainTrace("t3", "2026-01-01T00:00:00Z")
        trace.record_step("authenticate", "ok")
        assert "ts" in trace.steps[0]

    def test_trace_missing_facts_default_empty(self):
        trace = BrainTrace("t4", "2026-01-01T00:00:00Z")
        assert trace.missing_facts == []

    def test_trace_rag_sources_default_empty(self):
        trace = BrainTrace("t5", "2026-01-01T00:00:00Z")
        assert trace.rag_sources == []


# ── BRAIN_STEPS completeness ──────────────────────────────────────────────────

class TestBrainSteps:
    def test_exactly_19_steps_defined(self):
        assert len(BRAIN_STEPS) == 19, (
            f"Expected 19 steps, got {len(BRAIN_STEPS)}: {BRAIN_STEPS}"
        )

    def test_all_required_steps_present(self):
        required = [
            "authenticate",
            "load_context",
            "detect_jurisdiction",
            "detect_legal_area",
            "detect_claim_type",
            "detect_urgency",
            "detect_missing_facts",
            "select_agents",
            "select_rag_source",
            "run_rules_engine",
            "retrieve_legal_evidence",
            "verify_citations",
            "compress_context",
            "generate_draft",
            "evaluate_draft",
            "apply_safety_policy",
            "save_case_memory",
            "store_audit_log",
            "return_answer",
        ]
        for step in required:
            assert step in BRAIN_STEPS, f"Missing step: {step}"

    def test_step_order_correct(self):
        idx = {step: i for i, step in enumerate(BRAIN_STEPS)}
        assert idx["authenticate"]          < idx["detect_claim_type"]
        assert idx["detect_missing_facts"]  < idx["select_agents"]
        assert idx["select_agents"]         < idx["select_rag_source"]
        assert idx["select_rag_source"]     < idx["run_rules_engine"]
        assert idx["run_rules_engine"]      < idx["retrieve_legal_evidence"]
        assert idx["retrieve_legal_evidence"] < idx["verify_citations"]
        assert idx["verify_citations"]      < idx["compress_context"]
        assert idx["compress_context"]      < idx["generate_draft"]
        assert idx["generate_draft"]        < idx["evaluate_draft"]
        assert idx["evaluate_draft"]        < idx["apply_safety_policy"]
        assert idx["apply_safety_policy"]   < idx["save_case_memory"]
        assert idx["save_case_memory"]      < idx["store_audit_log"]
        assert idx["store_audit_log"]       < idx["return_answer"]

    def test_detect_missing_facts_before_select_agents(self):
        idx = {step: i for i, step in enumerate(BRAIN_STEPS)}
        assert idx["detect_missing_facts"] < idx["select_agents"]

    def test_safety_policy_after_evaluate_draft(self):
        idx = {step: i for i, step in enumerate(BRAIN_STEPS)}
        assert idx["apply_safety_policy"] > idx["evaluate_draft"]

    def test_save_memory_before_audit_log(self):
        idx = {step: i for i, step in enumerate(BRAIN_STEPS)}
        assert idx["save_case_memory"] < idx["store_audit_log"]

    def test_no_deprecated_step_names(self):
        deprecated = ["detect_legal_domain", "retrieve_sources", "detect_evidence_gaps",
                      "write_audit_trail", "calculate_deterministic"]
        for dep in deprecated:
            assert dep not in BRAIN_STEPS, f"Deprecated step still present: {dep}"


# ── Agent map ─────────────────────────────────────────────────────────────────

class TestAgentMap:
    def test_ud_agents_include_citation_verification(self):
        assert "citation_verification" in _AGENT_MAP["unfair_dismissal"]

    def test_ud_agents_include_deadline(self):
        assert "deadline" in _AGENT_MAP["unfair_dismissal"]

    def test_oos_routes_to_safety_agent(self):
        assert _AGENT_MAP["out_of_scope"] == ["safety_abuse"]

    def test_default_agents_present(self):
        assert "_default" in _AGENT_MAP
        assert len(_AGENT_MAP["_default"]) >= 3

    def test_all_claim_types_have_evaluation(self):
        for ct, agents in _AGENT_MAP.items():
            if ct != "out_of_scope":
                assert "evaluation" in agents, f"{ct} missing evaluation agent"


# ── run_brain integration (uses StubReasoningModel) ───────────────────────────

class TestRunBrain:
    def test_brain_returns_trace(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        assert "trace" in result
        assert result["trace"]["trace_id"]

    def test_brain_trace_has_19_steps(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        steps = [s["step"] for s in result["trace"]["steps"]]
        for step in BRAIN_STEPS:
            assert step in steps, f"Step missing from trace: {step}"

    def test_brain_trace_19_steps_exactly(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        # Each step should appear at least once
        steps_recorded = [s["step"] for s in result["trace"]["steps"]]
        assert len(set(steps_recorded)) >= len(BRAIN_STEPS), (
            f"Expected at least {len(BRAIN_STEPS)} distinct steps, "
            f"got {len(set(steps_recorded))}: {set(steps_recorded)}"
        )

    def test_brain_detects_jurisdiction(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        assert result["trace"]["jurisdiction"] == "EW"

    def test_brain_detects_legal_area(self):
        result = run_brain("I was unfairly dismissed", _UD_FACTS, model=STUB)
        assert result["trace"]["legal_area"] == "employment_law"

    def test_brain_detects_claim_type(self):
        result = run_brain("I was unfairly dismissed", _UD_FACTS, model=STUB)
        assert result["trace"]["claim_type"] == "unfair_dismissal"

    def test_brain_selects_agents(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        assert len(result["trace"]["agents_selected"]) > 0
        assert "deadline" in result["trace"]["agents_selected"]

    def test_brain_selects_rag_sources(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        assert isinstance(result["trace"]["rag_sources"], list)
        assert "hybrid" in result["trace"]["rag_sources"]

    def test_oos_exits_early(self):
        result = run_brain("My landlord is evicting me", {}, model=STUB)
        assert result["assessment"]["status"] == "not_supported"
        assert result["trace"]["final_status"] == "not_supported"

    def test_oos_skips_remaining_steps(self):
        result = run_brain("My landlord is evicting me", {}, model=STUB)
        skipped = [s for s in result["trace"]["steps"] if s["status"] == "skipped"]
        assert len(skipped) > 0

    def test_brain_returns_agents_list(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        assert isinstance(result["agents_selected"], list)
        assert len(result["agents_selected"]) > 0

    def test_brain_returns_missing_facts(self):
        incomplete = {"jurisdiction": "EW"}
        result = run_brain("I was dismissed", incomplete, model=STUB)
        assert isinstance(result["missing_facts"], list)

    def test_brain_detects_missing_facts_before_agents(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        steps = [s["step"] for s in result["trace"]["steps"]]
        mf_idx = steps.index("detect_missing_facts")
        ag_idx = steps.index("select_agents")
        assert mf_idx < ag_idx

    def test_brain_returns_evaluation(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        assert "evaluation" in result
        assert "required" in result["evaluation"]
        assert "passed"   in result["evaluation"]

    def test_brain_evaluation_required_for_ud(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        assert result["evaluation"]["required"] is True

    def test_brain_returns_safety_result(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        assert "safety" in result
        assert "passed"   in result["safety"]
        assert "blocked"  in result["safety"]
        assert "failures" in result["safety"]

    def test_brain_safety_passes_for_normal_query(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        assert result["safety"]["blocked"] is False

    def test_brain_urgency_detected(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        assert "urgency" in result
        assert result["urgency"] in ("safe", "urgent", "critical", "expired", "unknown")

    def test_brain_oos_no_agents_beyond_safety(self):
        result = run_brain("My neighbour is noisy", {}, model=STUB)
        assert "safety_abuse" in result["agents_selected"]

    def test_brain_memory_not_saved_without_consent(self):
        result = run_brain("I was dismissed", _UD_FACTS,
                           user_id="user-123", case_id="case-456",
                           memory_consent=False, model=STUB)
        assert result["trace"]["memory_saved"] is False

    def test_brain_memory_not_saved_without_user_id(self):
        result = run_brain("I was dismissed", _UD_FACTS,
                           user_id=None, case_id=None,
                           memory_consent=True, model=STUB)
        assert result["trace"]["memory_saved"] is False

    def test_brain_compress_context_step_recorded(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        step_names = [s["step"] for s in result["trace"]["steps"]]
        assert "compress_context" in step_names

    def test_brain_store_audit_log_step_recorded(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        step_names = [s["step"] for s in result["trace"]["steps"]]
        assert "store_audit_log" in step_names

    def test_brain_apply_safety_policy_step_recorded(self):
        result = run_brain("I was dismissed", _UD_FACTS, model=STUB)
        step_names = [s["step"] for s in result["trace"]["steps"]]
        assert "apply_safety_policy" in step_names

    def test_brain_upw_claim(self):
        # "haven't been paid" is in _UPW_KEYWORDS in classify.py
        result = run_brain("I haven't been paid my wages this month", _UPW_FACTS, model=STUB)
        assert "trace" in result
        assert result["trace"]["claim_type"] == "unpaid_wages"
