"""
Workflow C OpenRouter provider-plug + 4 AIA validator tests (mocked; no real key).

Proves: provider is a swappable plug; disabled/missing-key falls back to the
deterministic StubProvider fail-closed (no crash); and the 4 AIA validators reject
hallucinated citations, altered deterministic values, PII, and reserved wording.
"""

from __future__ import annotations

import pytest

from backend.core import llm_provider as P
from backend.core.agentic import aia_validators as V
from backend.core.agentic.errors import PolicyViolation
from backend.core.inference_policy import ExternalLLMForbidden


# ── provider plug ─────────────────────────────────────────────────────────────
def test_stub_provider_is_failclosed(monkeypatch):
    monkeypatch.delenv("OPENROUTER_ENABLED", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    prov = P.get_provider()
    assert prov.name == "stub"
    out = prov.complete_json(system_prompt="x", payload={}, trace_id="t", case_id="c")
    assert out["insufficient_grounding"] is True


def test_missing_key_does_not_crash_defaults_to_stub(monkeypatch):
    monkeypatch.setenv("OPENROUTER_ENABLED", "true")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    prov = P.get_provider()
    assert prov.name == "stub"          # no key -> not available -> Stub, no crash


def test_openrouter_not_available_when_disabled(monkeypatch):
    monkeypatch.setenv("OPENROUTER_ENABLED", "false")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-fakefortest")
    assert P.OpenRouterProvider().available() is False


def test_openrouter_call_failsclosed_when_unavailable(monkeypatch):
    monkeypatch.setenv("OPENROUTER_ENABLED", "false")
    with pytest.raises(ExternalLLMForbidden):
        P.OpenRouterProvider().complete_json(system_prompt="x", payload={}, trace_id="t", case_id="c")


def test_provider_abstraction_is_swappable():
    assert P.get_provider("gemini").name == "gemini"
    assert P.get_provider("local").name == "local"
    assert P.get_provider("gemini").available() is False   # placeholder, disabled
    with pytest.raises(PolicyViolation):
        P.get_provider("does_not_exist")


# ── AIA validators ────────────────────────────────────────────────────────────
_BUNDLE = ["Employment Rights Act 1996 s.98", "Employment Rights Act 1996 s.111",
           "ACAS Code of Practice on Disciplinary and Grievance Procedures"]


def test_aia1_citation_real_passes_hallucinated_fails():
    ok, _ = V.validate_citations(["Employment Rights Act 1996 s.98"], _BUNDLE)
    assert ok
    bad, fails = V.validate_citations(["Smith v Made Up Corp [2099] UKEAT 9999"], _BUNDLE)
    assert not bad and fails


def test_aia2_rules_changed_deadline_rejected():
    ok, _ = V.validate_rules({"time_limit_months": 3}, {"time_limit_months": 3})
    assert ok
    bad, fails = V.validate_rules({"time_limit_months": 12}, {"time_limit_months": 3})
    assert not bad and fails


def test_aia3_pii_boundary_rejects_pii():
    ok, _ = V.validate_pii_boundary({"reason": "conduct"})
    assert ok
    bad, fails = V.validate_pii_boundary({"raw": "NI AB123456C email a@b.com"})
    assert not bad and fails


def test_aia4_legal_boundary_blocks_reserved_and_requires_weaknesses():
    ok, _ = V.validate_legal_boundary("Likely eligible; weaknesses noted.", has_weaknesses=True)
    assert ok
    bad, fails = V.validate_legal_boundary("We will file and you will win, guaranteed win.")
    assert not bad and fails
    miss, mfails = V.validate_legal_boundary("Strong case.", non_trivial=True, has_weaknesses=False)
    assert not miss and "missing_weaknesses_for_non_trivial_case" in mfails


def test_run_all_validators_accepts_clean_rejects_dirty():
    good, rep = V.run_all_validators(
        cited=["Employment Rights Act 1996 s.98"], rag_bundle_citations=_BUNDLE,
        claimed_rule_values={"time_limit_months": 3}, rules_values={"time_limit_months": 3},
        outbound_payload={"reason": "conduct"},
        answer_text="Possibly eligible; key weaknesses noted.", has_weaknesses=True)
    assert good and all(not v for v in rep.values())

    bad, rep2 = V.run_all_validators(
        cited=["Fake v Nobody [2099]"], rag_bundle_citations=_BUNDLE,
        claimed_rule_values={"time_limit_months": 99}, rules_values={"time_limit_months": 3},
        outbound_payload={"raw": "AB123456C"},
        answer_text="guaranteed win, we will file", has_weaknesses=False)
    assert not bad
    assert rep2["citation"] and rep2["rules"] and rep2["pii"] and rep2["legal_boundary"]
