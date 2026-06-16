"""
Claim checker (the assessment engine)  -  HTTP + logic proof.

Endpoints under test (backend/api/main.py):
  POST /assess            -  the full path-split assessment pipeline
  POST /api/diagnosis     -  canonical alias of /assess

The "claim checker" is the assessment pipeline: it classifies the matter, routes
to the FAST_DETERMINISTIC (rules-only) lane or the REASONING lane, retrieves from
the local rules table, and FAILS CLOSED when out of scope / unsupported.

Proven (conftest -> localhost:5435 lawapp DB):
  HAPPY PATH
    - an in-scope factual query (use_model=False) -> grounded rules-table answer
      with real citations, invokes_llm == False, lane == FAST_DETERMINISTIC
    - /api/diagnosis returns the same governed result shape as /assess
  FAIL-CLOSED / ERROR CASES
    - an out-of-scope query -> status "not_supported" (no guess, no fabricated law)
    - an unsupported jurisdiction -> status "not_supported"
    - a missing required field -> 422

GUARDRAIL: every successful answer is sourced from the rules table
("source": "rules_table") and carries citations  -  never an ungrounded LLM guess.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app
    try:
        app.state.limiter.enabled = False
    except Exception:
        pass
    return TestClient(app, raise_server_exceptions=False)


_IN_SCOPE_QUERY = "What is the time limit to bring an unfair dismissal claim?"


# ── happy path: grounded, deterministic answer ────────────────────────────────────

class TestClaimCheckerHappyPath:
    def test_in_scope_factual_query_is_grounded(self, client):
        r = client.post("/assess",
                        json={"query": _IN_SCOPE_QUERY, "facts": {}, "use_model": False})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "ok"
        assert body["source"] == "rules_table"
        assert body["invokes_llm"] is False
        assert body["lane"] == "FAST_DETERMINISTIC"
        assert body.get("rules"), "a grounded answer must carry rules-table rows"
        assert body.get("trace_id")

    def test_answer_carries_real_citations(self, client):
        r = client.post("/assess",
                        json={"query": _IN_SCOPE_QUERY, "facts": {}, "use_model": False})
        body = r.json()
        rules = body.get("rules") or []
        # Every rule row is an authority with a stable rule_key  -  no fabricated cites.
        assert all(row.get("rule_key") for row in rules)

    def test_diagnosis_alias_matches_assess_shape(self, client):
        r = client.post("/api/diagnosis",
                        json={"query": _IN_SCOPE_QUERY, "facts": {}, "use_model": False})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "ok"
        assert body["result_type"] == "final_governed_assessment"


# ── fail-closed: out of scope / unsupported ──────────────────────────────────────

class TestClaimCheckerFailClosed:
    def test_out_of_scope_query_is_not_supported(self, client):
        r = client.post("/assess",
                        json={"query": "How do I get a divorce in France?",
                              "facts": {}, "use_model": False})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "not_supported"
        # No fabricated legal content for an out-of-scope matter.
        assert not body.get("rules")

    def test_unsupported_jurisdiction_is_not_supported(self, client):
        r = client.post("/assess",
                        json={"query": _IN_SCOPE_QUERY, "facts": {},
                              "jurisdiction": "ZZ", "use_model": False})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "not_supported"
        assert "not verified" in body["message"].lower() or "fail closed" in body["message"].lower()

    def test_missing_query_is_422(self, client):
        r = client.post("/assess", json={"facts": {}})
        assert r.status_code == 422, r.text
