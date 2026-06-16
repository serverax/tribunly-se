"""Distributed service CONTRACT + NEGATIVE proof.

For every in-scope distributed service this asserts the 10-point contract
(app exists, built via shared create_service, real /health JSON, X-Trace-ID,
name/version, business endpoint is not static fake success, dependency failure
is a controlled 4xx/5xx not a fake 200, no raw FastAPI() in the app source,
non-empty route inventory) plus the mandatory negative tests proving the system
does not fake success.

In scope (the 5 services restored to the shared factory):
    lawapp-rules-engine, lawapp-rag-retrieval, lawapp-citation-guard,
    lawapp-brain, lawapp-llm-gateway

NOT in scope (documented, not asserted here): lawapp-api, lawapp-crawler,
lawapp-rag-ingestion, lawapp-document-service, lawapp-worker  -  these are
pre-existing bare-FastAPI stubs and are excluded from this contract suite.
"""
from __future__ import annotations

import importlib
import pathlib

import pytest
from fastapi.testclient import TestClient

# (module path, declared service name)
SERVICES = [
    ("services.lawapp_rules_engine.app", "lawapp-rules-engine"),
    ("services.lawapp_rag_retrieval.app", "lawapp-rag-retrieval"),
    ("services.lawapp_citation_guard.app", "lawapp-citation-guard"),
    ("services.lawapp_brain.app", "lawapp-brain"),
    ("services.lawapp_llm_gateway.app", "lawapp-llm-gateway"),
]

# A representative business endpoint per service (method, path, body) used to
# prove the route executes real logic rather than returning a static success.
BUSINESS = {
    "lawapp-rules-engine": ("POST", "/v1/rules/evaluate",
                            {"claim_type": "unfair_dismissal", "jurisdiction": "EW"}),
    "lawapp-rag-retrieval": ("POST", "/v1/retrieve",
                             {"query": "unfair dismissal time limit",
                              "claim_type": "unfair_dismissal", "jurisdiction": "EW"}),
    "lawapp-citation-guard": ("POST", "/v1/citations/validate",
                              {"text": "Notice pay applies (Citation: "
                                       "00000000-0000-0000-0000-000000000000)."}),
    "lawapp-brain": ("POST", "/v1/assess",
                     {"user_id": "u", "workspace_id": "w", "case_id": "c"}),
    "lawapp-llm-gateway": ("POST", "/v1/generate",
                           {"messages": [{"role": "user", "content": "hi"}]}),
}


def _mod(modname):
    return importlib.import_module(modname)


def _client(modname):
    return TestClient(_mod(modname).app)


# ── 10-point structural contract (parametrised over every in-scope service) ──

@pytest.mark.parametrize("modname,name", SERVICES)
def test_contract_app_and_factory(modname, name):
    mod = _mod(modname)
    # 1. app object exists
    assert hasattr(mod, "app"), f"{name}: no app object"
    app = mod.app
    # 2. created via shared create_service (source proof) + 9. no raw FastAPI()
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert "from services._common import create_service" in src, f"{name}: not using shared factory"
    assert "create_service(" in src, f"{name}: create_service() not called"
    assert "FastAPI(" not in src, f"{name}: raw FastAPI() constructor present"
    # 6. service name + version in app metadata (factory sets these)
    assert app.title == name, f"{name}: app.title mismatch ({app.title})"
    assert app.version, f"{name}: no app.version"
    # 10. route inventory non-empty (default + health/ready + business)
    paths = {r.path for r in app.routes}
    assert {"/health", "/ready"} <= paths, f"{name}: missing health/ready routes"
    assert len(paths) > 3, f"{name}: route inventory too small: {paths}"


@pytest.mark.parametrize("modname,name", SERVICES)
def test_contract_health_json_and_trace(modname, name):
    c = _client(modname)
    h = c.get("/health")
    # 3. health endpoint exists  4. returns JSON  5. X-Trace-ID header
    assert h.status_code == 200, f"{name}: health {h.status_code}"
    body = h.json()
    assert body["service"] == name, f"{name}: health service mismatch"
    assert body.get("status") == "healthy", f"{name}: factory health status missing"
    assert "X-Trace-ID" in h.headers, f"{name}: no X-Trace-ID header"


@pytest.mark.parametrize("modname,name", SERVICES)
def test_contract_business_endpoint_not_static_fake(modname, name):
    """7. The business endpoint must reflect real execution, never a bare
    {"status":"accepted"} static success."""
    c = _client(modname)
    method, path, body = BUSINESS[name]
    r = c.request(method, path, json=body)
    # Controlled outcome only: real success, controlled client/dep error.
    assert r.status_code in (200, 422, 503), f"{name}: uncontrolled {r.status_code}"
    if r.status_code == 200:
        j = r.json()
        # A bare static {"status":"accepted"} with no real signal is forbidden.
        assert j != {"status": "accepted"}, f"{name}: static fake success"
        if name == "lawapp-rules-engine":
            assert "count" in j and isinstance(j["count"], int), f"{name}: no real count"
        if name == "lawapp-rag-retrieval":
            assert j.get("source") == "local_corpus" and j.get("llm_called") is False
        if name == "lawapp-citation-guard":
            # fake all-zeros UUID must NOT validate
            assert j.get("valid") is False, f"{name}: fake UUID accepted"


# ── 8 / 9. NEGATIVE tests  -  prove the system does not fake success ──

def test_neg_missing_dependency_returns_503_not_200(monkeypatch):
    """9.1 + 9.4  -  RAG with an unavailable retrieval dependency returns a
    controlled 503 and NOT a hallucinated 200 answer."""
    import backend.core.retrieve as retr

    def _boom(*a, **k):
        raise RuntimeError("corpus/model unavailable")

    monkeypatch.setattr(retr, "retrieve", _boom)
    c = _client("services.lawapp_rag_retrieval.app")
    r = c.post("/v1/retrieve", json={"query": "x", "claim_type": "unfair_dismissal",
                                     "jurisdiction": "EW"})
    assert r.status_code == 503, f"expected controlled 503, got {r.status_code}"
    assert "answer" not in r.json(), "must not return a fabricated answer"


def test_neg_invalid_input_returns_4xx_not_success():
    """9.2  -  brain with missing tenancy returns 400, not a success."""
    c = _client("services.lawapp_brain.app")
    r = c.post("/v1/assess", json={"user_id": "u"})  # workspace_id/case_id missing
    assert r.status_code in (400, 422), f"expected 4xx, got {r.status_code}"


def test_neg_rules_engine_not_hardcoded(monkeypatch):
    """9.3  -  rules-engine cannot return success without actually querying rules:
    if the rules source raises, it must fail closed (503), not fake-accept."""
    import backend.core.retrieve as retr

    def _boom(*a, **k):
        raise RuntimeError("rules db down")

    monkeypatch.setattr(retr, "retrieve_rules", _boom)
    c = _client("services.lawapp_rules_engine.app")
    r = c.post("/v1/rules/evaluate", json={"claim_type": "unfair_dismissal",
                                           "jurisdiction": "EW"})
    assert r.status_code == 503, f"expected fail-closed 503, got {r.status_code}"


def test_neg_citation_guard_not_always_valid(monkeypatch):
    """9.5  -  citation guard rejects an unsupported answer; it is not valid=True
    by default. With no real corpus UUID match, valid must be False."""
    import backend.core.agentic.corpus_citation_guard as cg

    monkeypatch.setattr(cg, "valid_corpus_uuids", lambda uuids, get_conn=None: set())
    c = _client("services.lawapp_citation_guard.app")
    r = c.post("/v1/citations/validate",
               json={"text": "Claim (Citation: 11111111-1111-1111-1111-111111111111)."})
    assert r.status_code == 200
    assert r.json()["valid"] is False, "citation guard must not default to valid=True"


def test_neg_citation_guard_no_citation_is_invalid():
    """9.5 (extra)  -  an answer with no citation at all is invalid (fail-closed)."""
    c = _client("services.lawapp_citation_guard.app")
    r = c.post("/v1/citations/validate", json={"text": "You will definitely win."})
    assert r.status_code == 200 and r.json()["valid"] is False


def test_neg_llm_gateway_rejects_pii():
    """9.2 (PII variant)  -  llm-gateway rejects raw PII with 422, not success."""
    c = _client("services.lawapp_llm_gateway.app")
    r = c.post("/v1/generate", json={"messages": [{"role": "user", "content": "hi"}],
                                     "context": {"email": "a@b.com"}})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "pii_rejected"
