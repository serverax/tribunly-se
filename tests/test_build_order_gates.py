"""Build order gates: LangGraph blocked, domain fail-closed."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app


def test_no_langgraph_legal_reason_routes():
    client = TestClient(app)
    for path in ("/api/v1/legal/reason", "/api/legal/reason"):
        r = client.post(path, json={"query": "test"})
        assert r.status_code in (404, 405), path


def test_assess_immigration_domain_fail_closed():
    client = TestClient(app)
    r = client.post(
        "/assess",
        json={
            "query": "visa refusal",
            "facts": {"domain_code": "immigration"},
            "jurisdiction": "UK",
            "use_model": False,
        },
        headers={"X-Lawapp-Domain": "immigration"},
    )
    body = r.json()
    assert body.get("status") == "domain_unavailable"
    assert body.get("domain_code") == "immigration"
    assert body.get("invokes_llm") is False


def test_domains_api_lists_employment_only_enabled():
    client = TestClient(app)
    r = client.get("/api/domains")
    assert r.status_code == 200
    domains = {d["code"]: d for d in r.json().get("domains", [])}
    assert domains["employment"]["enabled"] is True
    for code in ("immigration", "housing", "benefits", "debt"):
        assert domains[code]["enabled"] is False
