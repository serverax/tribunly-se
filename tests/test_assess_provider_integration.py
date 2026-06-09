"""
Workflow C /assess provider-stage integration tests (mock/no-key).

Proves the provider plug + 4 AIA validators are wired AFTER deterministic
RAG/rules and behave fail-closed: no provider call on weak RAG; only a
de-identified bundle reaches the provider; and hallucinated citations, altered
deterministic values, and reserved wording are rejected by the validators.
"""

from __future__ import annotations

from backend.core.workflow_c_provider import run_provider_stage

_GROUNDED = {
    "status": "ok",
    "insufficient_grounding": False,
    "citations": [{"cite": "Employment Rights Act 1996 s.98"}],
    "deadline_info": {"time_limit_months": 3},
}


class FakeProvider:
    name = "fake"

    def __init__(self, out=None, raises=False):
        self.out = out or {}
        self.raises = raises
        self.called = False
        self.seen = None

    def complete_json(self, *, system_prompt, payload, trace_id, case_id):
        self.called = True
        self.seen = payload
        if self.raises:
            raise RuntimeError("provider boom")
        return self.out


def test_skipped_when_weak_rag_provider_not_called():
    spy = FakeProvider(out={"x": 1})
    weak = {"status": "insufficient_grounding", "insufficient_grounding": True, "citations": []}
    r = run_provider_stage(query="q", facts={}, assessment_result=weak, provider=spy)
    assert r["status"] == "skipped_weak_rag"
    assert spy.called is False           # provider was NOT called on weak RAG


def test_works_with_stub_no_crash(monkeypatch):
    monkeypatch.delenv("OPENROUTER_ENABLED", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    r = run_provider_stage(query="q", facts={}, assessment_result=_GROUNDED)  # default = Stub
    assert r["status"] in ("insufficient_grounding", "skipped_weak_rag")  # safe, no crash
    assert r["status"] != "accepted"


def test_failsclosed_enabled_but_missing_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_ENABLED", "true")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    r = run_provider_stage(query="q", facts={}, assessment_result=_GROUNDED)
    assert r["status"] != "accepted"     # no key -> Stub -> not accepted (fail closed)


def test_only_deidentified_bundle_reaches_provider():
    spy = FakeProvider(out={"statutory_citations_used": ["Employment Rights Act 1996 s.98"],
                            "key_weaknesses": ["x"]})
    facts = {"employee": "NI AB123456C", "contact": "a@b.com phone 07911123456"}
    run_provider_stage(query="q", facts=facts, assessment_result=_GROUNDED, provider=spy)
    import json
    seen = json.dumps(spy.seen)
    assert "AB123456C" not in seen and "a@b.com" not in seen and "07911123456" not in seen


def test_validators_accept_clean_provider_output():
    good = FakeProvider(out={"statutory_citations_used": ["Employment Rights Act 1996 s.98"],
                             "key_weaknesses": ["short service"], "summary": "possibly eligible"})
    r = run_provider_stage(query="q", facts={}, assessment_result=_GROUNDED, provider=good)
    assert r["status"] == "accepted" and r["validators"] == "passed"


def test_hallucinated_citation_rejected():
    bad = FakeProvider(out={"statutory_citations_used": ["Fake v Nobody [2099] UKEAT 9999"],
                            "key_weaknesses": ["x"]})
    r = run_provider_stage(query="q", facts={}, assessment_result=_GROUNDED, provider=bad)
    assert r["status"] == "rejected_by_aia" and r["failures"]["citation"]


def test_changed_deterministic_value_rejected():
    bad = FakeProvider(out={"statutory_citations_used": ["Employment Rights Act 1996 s.98"],
                            "rule_values": {"time_limit_months": 12}, "key_weaknesses": ["x"]})
    r = run_provider_stage(query="q", facts={}, assessment_result=_GROUNDED, provider=bad)
    assert r["status"] == "rejected_by_aia" and r["failures"]["rules"]


def test_reserved_wording_rejected():
    bad = FakeProvider(out={"statutory_citations_used": ["Employment Rights Act 1996 s.98"],
                            "key_weaknesses": ["x"], "summary": "guaranteed win, we will file"})
    r = run_provider_stage(query="q", facts={}, assessment_result=_GROUNDED, provider=bad)
    assert r["status"] == "rejected_by_aia" and r["failures"]["legal_boundary"]
