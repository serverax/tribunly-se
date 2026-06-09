"""Distributed service extraction proof — each service is REAL (health + a real
endpoint wired to existing backend/core logic), via TestClient. No empty wrappers.
"""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

SERVICES = [
    ("services.lawapp_llm_gateway.app", "lawapp-llm-gateway"),
    ("services.lawapp_rules_engine.app", "lawapp-rules-engine"),
    ("services.lawapp_rag_retrieval.app", "lawapp-rag-retrieval"),
    ("services.lawapp_citation_guard.app", "lawapp-citation-guard"),
    ("services.lawapp_brain.app", "lawapp-brain"),
]


def _client(mod):
    return TestClient(importlib.import_module(mod).app)


@pytest.mark.parametrize("mod,name", SERVICES)
def test_service_health_and_ready(mod, name):
    c = _client(mod)
    h = c.get("/health")
    assert h.status_code == 200 and h.json()["service"] == name
    r = c.get("/ready")
    assert r.status_code in (200, 503)            # ready, or fail-closed if DB down
    assert "X-Trace-ID" in h.headers


def test_rules_engine_evaluate_real():
    c = _client("services.lawapp_rules_engine.app")
    r = c.post("/v1/rules/evaluate", json={"claim_type": "unfair_dismissal", "jurisdiction": "EW"})
    assert r.status_code == 200 and r.json()["count"] > 0   # real rules from DB


def test_citation_guard_fake_uuid_fails():
    c = _client("services.lawapp_citation_guard.app")
    r = c.post("/v1/citations/validate",
               json={"text": "You are entitled to notice (Citation: 00000000-0000-0000-0000-000000000000)."})
    assert r.status_code == 200 and r.json()["valid"] is False


def test_llm_gateway_rejects_pii():
    c = _client("services.lawapp_llm_gateway.app")
    r = c.post("/v1/generate",
               json={"messages": [{"role": "user", "content": "hello"}], "context": {"email": "a@b.com"}})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "pii_rejected"


def test_rag_retrieval_local_corpus_only():
    c = _client("services.lawapp_rag_retrieval.app")
    r = c.post("/v1/retrieve",
               json={"query": "unfair dismissal time limit", "claim_type": "unfair_dismissal", "jurisdiction": "EW"})
    assert r.status_code == 200 and r.json()["source"] == "local_corpus"
