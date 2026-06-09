"""LOCAL OLLAMA ONLY policy — proves lawapp legal routes can never use an external
/ cloud LLM, fail closed when Ollama is unavailable, and keep deterministic routes
independent of inference.

These are enforcement tests (not skipped): with cloud keys/modes set, the system
must still refuse external providers.
"""
from __future__ import annotations

import json

import pytest

from backend.core import inference_policy as ip
from backend.core.inference_policy import ExternalLLMForbidden, InferenceUnavailable


def _clear_provider_env(mp):
    for k in ("AI_PROVIDER", "LLM_PROVIDER", "LAWAPP_LLM_PROVIDER", "EXTERNAL_LLM", "CLOUD_LLM"):
        mp.delenv(k, raising=False)


# 1-3: external keys PRESENT must not enable a cloud model.
def test_external_keys_present_do_not_enable_cloud(monkeypatch):
    _clear_provider_env(monkeypatch)
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.setenv(k, "sk-real-looking-value-aaaaaaaaaaaaaaaa")
    from backend.core.models import select_model
    from ingestion.config import settings
    m = select_model(settings)
    assert type(m).__name__ not in ("ClaudeReasoningModel", "OpenRouterReasoningModel"), \
        f"cloud model selected despite local-only policy: {type(m).__name__}"


# 4-5: explicit external provider MODE fails closed (policy + select_model).
@pytest.mark.parametrize("mode", ["anthropic", "openrouter", "openai", "gemini"])
def test_external_provider_mode_fails_closed(monkeypatch, mode):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", mode)
    with pytest.raises(ExternalLLMForbidden):
        ip.assert_no_external_llm_enabled()
    from backend.core.models import select_model
    from ingestion.config import settings
    with pytest.raises(ExternalLLMForbidden):
        select_model(settings)


# 6: legal LLM route requires LAWAPP_LLM_PROVIDER=ollama_local (missing/other => fail).
def test_legal_llm_requires_ollama_local(monkeypatch):
    _clear_provider_env(monkeypatch)
    with pytest.raises(ExternalLLMForbidden):
        ip.require_ollama_local_provider()              # unset
    monkeypatch.setenv("LAWAPP_LLM_PROVIDER", "anthropic")
    with pytest.raises(ExternalLLMForbidden):
        ip.require_ollama_local_provider()              # wrong value
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("LAWAPP_LLM_PROVIDER", "ollama_local")
    ip.require_ollama_local_provider()                  # correct -> no raise


# 7: missing/unreachable Ollama for the legal LLM route => INFERENCE_UNAVAILABLE,
#    never a cloud fallback.
def test_missing_ollama_raises_inference_unavailable(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("LAWAPP_LLM_PROVIDER", "ollama_local")
    import backend.core.models as models

    def _boom(*a, **k):
        raise RuntimeError("connection refused to ollama-inference:11434")

    monkeypatch.setattr(models, "LocalInferenceReasoningModel", _boom)
    with pytest.raises(InferenceUnavailable) as ei:
        ip.build_legal_inference_model()
    assert ei.value.code == "INFERENCE_UNAVAILABLE"


# 8: deterministic RULES route does not construct/call inference.
def test_rules_route_does_not_call_ollama(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(ip, "build_legal_inference_model",
                        lambda: calls.__setitem__("n", calls["n"] + 1))
    from backend.core.brain import get_deterministic_guide
    guide = get_deterministic_guide("unfair_dismissal", "EW")
    assert calls["n"] == 0, "deterministic RULES route must not invoke Ollama"
    assert isinstance(guide, dict)


# 10: the legal LLM route builds ONLY a local Ollama model, at the mandated URL.
def test_local_llm_route_builds_only_ollama(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("LAWAPP_LLM_PROVIDER", "ollama_local")
    monkeypatch.setenv("LAWAPP_OLLAMA_BASE_URL",
                       "http://ollama-inference.lawapp-ai.svc.cluster.local:11434")
    monkeypatch.setenv("LAWAPP_OLLAMA_MODEL", "qwen2.5:3b-instruct-q6_K")
    import backend.core.models as models

    class _FakeLocal:
        def __init__(self, base_url, model_id):
            self.base_url, self.model_id = base_url, model_id

    monkeypatch.setattr(models, "LocalInferenceReasoningModel", _FakeLocal)
    m = ip.build_legal_inference_model()
    assert type(m).__name__ == "_FakeLocal"
    assert m.base_url == "http://ollama-inference.lawapp-ai.svc.cluster.local:11434"
    assert m.model_id == "qwen2.5:3b-instruct-q6_K"


# 11: a fake UUID in (hypothetical) Ollama output is rejected by CitationGuard.
def test_fake_uuid_from_output_is_rejected():
    from backend.core.agentic.corpus_citation_guard import response_has_valid_corpus_citation
    text = "You are entitled to notice (Citation: 00000000-0000-0000-0000-000000000000)."
    assert response_has_valid_corpus_citation(text) is False


# 12: PII is scrubbed before it could reach the model boundary.
def test_pii_scrubbed_before_inference():
    from backend.core.agentic.pii import redact_text, residual_pii
    out = redact_text("Contact me at john.doe@example.com or 07700900123")
    assert "john.doe@example.com" not in out
    assert "07700900123" not in out
    assert residual_pii(out) is None


# transparency: external key presence report is REDACTED (booleans only).
def test_external_key_report_is_redacted(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-value-zzzz")
    rep = ip.external_llm_keys_present_redacted()
    assert rep["OPENAI_API_KEY"] is True
    assert all(isinstance(v, bool) for v in rep.values())
    assert "sk-super-secret-value-zzzz" not in json.dumps(rep)


def test_allowed_backend_is_ollama():
    assert ip.get_allowed_inference_backend() == "ollama"
