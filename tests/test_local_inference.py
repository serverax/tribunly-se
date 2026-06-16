"""
Local Inference Fabric  -  offline unit proof.

Runs with NO cluster and NO network: proves the provider is wired and FAILS SOFT.
  1. select_model() returns the LocalInferenceReasoningModel when enabled.
  2. The provider's prompt carries the de-identified facts + the legal
     relationship map (graph context prioritised).
  3. When the inference endpoint is unreachable, reason() returns a safe
     insufficient_grounding assessment (MODEL_UNAVAILABLE)  -  it does NOT crash
     the Mother Algorithm.
  4. De-identification is enforced: reason() refuses an empty boundary_log.
"""
from __future__ import annotations

import pytest

from backend.core.models import (
    LocalInferenceReasoningModel,
    StubReasoningModel,
    select_model,
)
from shared.schemas import RetrievalBundle


class _Settings:
    local_inference_enabled = True
    local_inference_url = "http://127.0.0.1:1"  # not listening -> unreachable
    local_inference_model = "qwen2.5-3b-instruct"
    openrouter_enabled = False
    anthropic_api_key = "placeholder"
    workhorse_model_id = ""


def test_select_model_prefers_local_inference_when_enabled(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    model = select_model(_Settings())
    assert isinstance(model, LocalInferenceReasoningModel)


def test_select_model_falls_back_to_stub_when_local_disabled(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("LAWAPP_LLM_PROVIDER", raising=False)

    class _Off(_Settings):
        local_inference_enabled = False
    assert isinstance(select_model(_Off()), StubReasoningModel)


def test_reason_requires_deidentification():
    model = LocalInferenceReasoningModel(base_url="http://127.0.0.1:1")
    bundle = RetrievalBundle(exact_rules=[], authorities=[], insufficient_grounding=False)
    with pytest.raises(RuntimeError):
        model.reason({"jurisdiction": "EW"}, bundle, {}, boundary_log={})


def test_reason_fails_soft_when_endpoint_unreachable():
    # Port 1 is not listening -> connection refused -> MODEL_UNAVAILABLE, no crash.
    model = LocalInferenceReasoningModel(base_url="http://127.0.0.1:1")
    bundle = RetrievalBundle(exact_rules=[], authorities=[], insufficient_grounding=False)
    safe_facts = {
        "jurisdiction": "EW",
        "_legal_relationship_map": "LEGAL KNOWLEDGE GRAPH:\n  [statute] ERA 1996 s.98",
    }
    result = model.reason(safe_facts, bundle, {"limitation_date": None},
                          boundary_log={"fields_stripped": ["name"]})
    assert result.insufficient_grounding is True
    assert result.has_viable_claim == "uncertain"
    assert result.deadline.source == "rules"  # deadline source never model-derived

    # The prompt actually built carried the relationship map + de-identified facts.
    payload = model.get_boundary_payload()
    assert payload["provider"] == "local_inference"
    assert "_legal_relationship_map" in payload["safe_facts_keys"]
