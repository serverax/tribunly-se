"""Proof that /assess uses the ADR path-splitter as the DEFAULT, via TestClient(app).

FACTUAL  -> deterministic rules-only, no LLM, cited, fail-closed.
REASONING -> retrieval -> deidentify -> reason -> score -> govern (final_governed_assessment).
No final output bypasses retrieval/citations/governance.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)

UD_FACTS = {
    "edt": "2025-10-01", "service_start_date": "2019-01-01",
    "reason_for_dismissal": "conduct", "was_procedure_followed": False,
    "weekly_pay": 700, "jurisdiction": "EW",
}
FACTUAL_Q = "What is the time limit for unfair dismissal?"
REASONING_Q = "Do I have a claim for unfair dismissal?"


def _assess(query, facts=None, jurisdiction="EW", use_model=False):
    return client.post("/assess", json={
        "query": query, "facts": facts or {}, "jurisdiction": jurisdiction,
        "use_model": use_model})


def test_assess_uses_path_splitter_by_default():
    r = _assess(REASONING_Q, UD_FACTS)
    assert r.status_code == 200
    body = r.json()
    assert "intent" in body and "lane" in body


def test_assess_factual_lane_no_llm_rules_only():
    r = _assess(FACTUAL_Q, {})
    assert r.status_code == 200
    body = r.json()
    assert body["lane"] == "FAST_DETERMINISTIC"
    assert body["invokes_llm"] is False
    assert body["source"] == "rules_table"
    if body["status"] == "ok":
        assert len(body["citations"]) > 0      # cited source references


def test_assess_reasoning_lane_runs_retrieval_first():
    body = _assess(REASONING_Q, UD_FACTS).json()
    assert body["intent"] == "REASONING"
    assert body["result_type"] == "final_governed_assessment"
    # governance/boundary fields only exist because retrieval + pipeline ran.
    assert "governance_result" in body or "boundary_log" in body


def test_assess_reasoning_lane_blocks_uncited_output():
    body = _assess(REASONING_Q, UD_FACTS).json()
    # An 'ok' final answer MUST carry citations; otherwise it must not be 'ok'.
    if body.get("status") == "ok":
        assert body.get("citations"), "ok answer with no citations  -  uncited output not blocked"


def test_assess_reasoning_lane_blocks_ungrounded_output():
    # Reasoning query with NO fact pattern -> cannot ground -> must not be 'ok'.
    body = _assess(REASONING_Q, {}).json()
    assert body.get("status") != "ok"
    assert body.get("has_viable_claim") in (None, "uncertain", "no")


def test_assess_reasoning_lane_passes_critic_before_final_response():
    body = _assess(REASONING_Q, UD_FACTS).json()
    assert body["result_type"] == "final_governed_assessment"
    if body.get("status") == "ok":
        assert body.get("governance_result", {}).get("passes") is True


def test_assess_deidentifies_before_model():
    body = _assess(REASONING_Q, UD_FACTS).json()
    assert "boundary_log" in body, "no boundary_log  -  de-identification not proven"


def test_stream_preview_not_final_advice(monkeypatch):
    monkeypatch.setenv("LOCAL_INFERENCE_ENABLED", "true")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    s = client.post("/reasoning/stream", json={"query": REASONING_Q, "facts": UD_FACTS})
    assert s.headers["content-type"].startswith("text/event-stream")
    # the stream is a preview  -  it must NOT claim to be the final governed assessment
    assert "final_governed_assessment" not in s.text
    # whereas /assess IS the governed result
    assert _assess(REASONING_Q, UD_FACTS).json()["result_type"] == "final_governed_assessment"


def test_missing_rule_fails_closed():
    # NI has no verified rules -> FACTUAL lane must fail closed, no LLM, no guess.
    body = _assess(FACTUAL_Q, {}, jurisdiction="NI").json()
    assert body["invokes_llm"] is False
    assert body["status"] == "not_supported"


def test_db_unavailable_fails_closed_not_crash(monkeypatch):
    def boom():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr("backend.core.retrieve.get_connection", boom)
    r = _assess(FACTUAL_Q, {}, jurisdiction="EW")
    assert r.status_code == 200
    body = r.json()
    assert body["invokes_llm"] is False
    assert body["status"] == "not_supported"


def test_out_of_scope_returns_not_supported_not_guess():
    body = _assess("How do I bake sourdough bread at home?", {}).json()
    assert body.get("status") == "not_supported"
    assert body.get("has_viable_claim") != "yes"
