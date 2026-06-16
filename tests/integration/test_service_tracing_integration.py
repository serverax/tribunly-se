"""Cross-service INTEGRATION proof (T-006 rule engine + T-007 deadline calc).

These are not single-service contract tests  -  they wire the real distributed
service apps together in-process (Starlette TestClient bridges each ASGI app to a
sync transport) and assert the behaviour the task requires:

  1. The rules-engine `/v1/deadline/calculate` produces a REAL limitation date from
     the rules table (the prior wrong-signature stub always returned 422).
  2. ONE trace id is propagated, unchanged, from the brain through BOTH the
     rules-engine and the llm-gateway  -  and each service echoes it back
     (cross-service tracing).
  3. The deterministic deadline is routed THROUGH the llm-gateway for explanation
     (deadline_calc wired through the gateway), dates only  -  no PII to the model.
  4. Fail-closed everywhere: rules DB down → no fabricated deadline; model
     unavailable → real deadline but an honest explanation_unavailable, never a
     hallucinated explanation.

The DB and Ollama are stubbed so the proof is hermetic and deterministic; the wiring
and arithmetic under test are the real production code paths.
"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

import services.lawapp_brain.app as brain_app
from services.lawapp_brain.app import app as brain
from services.lawapp_llm_gateway.app import app as gateway
from services.lawapp_rules_engine.app import app as rules

TRACE = "11111111-1111-1111-1111-111111111111"

# A realistic time_limit_months rule row (what retrieve_rules returns from the DB).
_TL_RULE = {
    "rule_key": "unfair_dismissal.time_limit_months",
    "value_numeric": 3,
    "authority_ref": "ERA 1996 s.111(2)",
    "authority_url": "https://www.legislation.gov.uk/ukpga/1996/18/section/111",
}


# ── stubs for the external dependencies (DB + local model) ────────────────────

@pytest.fixture
def rules_db(monkeypatch):
    """Stub the rules table read so the deadline math runs on a known statutory value."""
    import backend.core.retrieve as retr
    monkeypatch.setattr(retr, "retrieve_rules", lambda *a, **k: [dict(_TL_RULE)])


def _patch_model(monkeypatch, chunks):
    import backend.core.models as models

    class _FakeModel:
        def __init__(self, *a, **k):
            pass

        def stream_chat(self, messages, max_tokens=512):
            for c in chunks:
                yield c

    monkeypatch.setattr(models, "LocalInferenceReasoningModel", _FakeModel)


@pytest.fixture
def wire_brain(monkeypatch):
    """Point the brain's downstream client factories at in-process TestClients of the
    real sibling apps, and spy on call_service to capture the trace id sent to  -  and
    echoed by  -  each downstream service."""
    monkeypatch.setattr(brain_app, "RULES_ENGINE_CLIENT_FACTORY", lambda base: TestClient(rules))
    monkeypatch.setattr(brain_app, "LLM_GATEWAY_CLIENT_FACTORY", lambda base: TestClient(gateway))

    calls = []
    real_call = brain_app.call_service

    def _spy(base_url, method, path, **kw):
        resp = real_call(base_url, method, path, **kw)
        calls.append({
            "path": path,
            "sent_trace": kw.get("trace_id"),
            "echoed_trace": resp.headers.get("X-Trace-ID"),
            "status": resp.status_code,
        })
        return resp

    monkeypatch.setattr(brain_app, "call_service", _spy)
    return calls


# ── 1. rules-engine deadline is REAL (the defect is fixed) ────────────────────

def test_rules_engine_deadline_returns_real_date(rules_db):
    c = TestClient(rules)
    r = c.post("/v1/deadline/calculate",
               json={"claim_type": "unfair_dismissal", "jurisdiction": "EW",
                     "relevant_date": "2024-01-31"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["llm_called"] is False
    assert body["source"] == "rules_table"
    assert body["time_limit_months"] == 3
    # 3 months "beginning with" 31 Jan 2024 → 30 Apr (clamped) − 1 day = 29 Apr 2024.
    assert body["result"]["limitation_date"] == "2024-04-29"
    assert body["result"]["source"] == "rules"


def test_rules_engine_deadline_with_ec_stopclock(rules_db):
    c = TestClient(rules)
    r = c.post("/v1/deadline/calculate",
               json={"claim_type": "unfair_dismissal", "jurisdiction": "EW",
                     "relevant_date": "2024-01-31",
                     "ec_day_a": "2024-02-10", "ec_day_b": "2024-03-10"})
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert result["ec_applied"] is True
    # base 2024-04-29 + 29 EC pause days = 2024-05-28 (above the 1-month floor).
    assert result["limitation_date"] == "2024-05-28"


def test_rules_engine_deadline_db_down_fails_closed(monkeypatch):
    import backend.core.retrieve as retr

    def _boom(*a, **k):
        raise RuntimeError("rules db down")

    monkeypatch.setattr(retr, "retrieve_rules", _boom)
    c = TestClient(rules)
    r = c.post("/v1/deadline/calculate",
               json={"claim_type": "unfair_dismissal", "jurisdiction": "EW",
                     "relevant_date": "2024-01-31"})
    assert r.status_code == 503, r.text
    assert "limitation_date" not in r.text


# ── 2. single-service trace echo (factory middleware) ─────────────────────────

def test_trace_echo_single_service(rules_db):
    c = TestClient(rules)
    r = c.post("/v1/deadline/calculate",
               headers={"X-Trace-ID": TRACE},
               json={"claim_type": "unfair_dismissal", "jurisdiction": "EW",
                     "relevant_date": "2024-01-31"})
    assert r.status_code == 200
    assert r.headers["X-Trace-ID"] == TRACE


# ── 3 + 4. cross-service: one trace id through BOTH services; deadline via gateway ─

def test_cross_service_trace_and_deadline_through_gateway(rules_db, wire_brain, monkeypatch):
    """Model AVAILABLE: brain → rules-engine (deadline) → llm-gateway (explain),
    all carrying ONE trace id that both downstreams echo. Deadline is real and the
    LLM explanation is returned without changing any date."""
    _patch_model(monkeypatch, ["The deadline to start your tribunal claim is "
                               "2024-04-29. Missing it is usually fatal to the claim."])
    c = TestClient(brain)
    r = c.post("/v1/deadline/explain",
               headers={"X-Trace-ID": TRACE},
               json={"user_id": "u1", "workspace_id": "w1", "case_id": "c1",
                     "claim_type": "unfair_dismissal", "jurisdiction": "EW",
                     "edt": "2024-01-31"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trace_id"] == TRACE
    assert r.headers["X-Trace-ID"] == TRACE
    assert body["source"] == "rules"
    assert body["limitation_date"] == "2024-04-29"
    assert body["llm_called"] is True
    assert body["explanation_unavailable"] is False
    assert "2024-04-29" in body["explanation"]
    assert body["gateway_status"] == 200

    # The SAME trace id was sent to AND echoed by both downstream services.
    paths = {ci["path"] for ci in wire_brain}
    assert paths == {"/v1/deadline/calculate", "/v1/generate"}
    for ci in wire_brain:
        assert ci["sent_trace"] == TRACE, ci
        assert ci["echoed_trace"] == TRACE, ci


def test_cross_service_model_unavailable_fails_closed(rules_db, wire_brain, monkeypatch):
    """Model UNAVAILABLE: the real deterministic deadline is still returned and the
    trace still flows to both services, but the explanation is honestly marked
    unavailable  -  never a fabricated explanation."""
    _patch_model(monkeypatch, ["[MODEL_UNAVAILABLE]"])
    c = TestClient(brain)
    r = c.post("/v1/deadline/explain",
               headers={"X-Trace-ID": TRACE},
               json={"user_id": "u1", "workspace_id": "w1", "case_id": "c1",
                     "edt": "2024-01-31"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trace_id"] == TRACE
    assert body["limitation_date"] == "2024-04-29"      # deterministic truth survives
    assert body["llm_called"] is False
    assert body["explanation_unavailable"] is True
    assert body["explanation"] is None                  # no hallucinated explanation
    assert body["gateway_status"] == 503
    # trace still propagated to both services
    for ci in wire_brain:
        assert ci["sent_trace"] == TRACE and ci["echoed_trace"] == TRACE, ci


def test_deadline_explain_requires_tenancy(wire_brain):
    c = TestClient(brain)
    r = c.post("/v1/deadline/explain",
               json={"user_id": "u1", "edt": "2024-01-31"})  # workspace_id/case_id missing
    assert r.status_code == 400
    assert wire_brain == []   # fails before any downstream call


def test_deadline_explain_requires_edt(wire_brain):
    c = TestClient(brain)
    r = c.post("/v1/deadline/explain",
               json={"user_id": "u1", "workspace_id": "w1", "case_id": "c1"})
    assert r.status_code == 400


def test_deadline_explain_rules_unavailable_fails_closed(wire_brain, monkeypatch):
    """If the rules-engine cannot produce a deadline, the orchestrator fails closed
    (502 at the rules stage) and never invents a date or calls the model."""
    import backend.core.retrieve as retr
    monkeypatch.setattr(retr, "retrieve_rules",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    c = TestClient(brain)
    r = c.post("/v1/deadline/explain",
               headers={"X-Trace-ID": TRACE},
               json={"user_id": "u1", "workspace_id": "w1", "case_id": "c1",
                     "edt": "2024-01-31"})
    assert r.status_code == 502, r.text
    assert "limitation_date" not in r.text
    # only the rules-engine was called; the gateway was never reached
    assert [ci["path"] for ci in wire_brain] == ["/v1/deadline/calculate"]
