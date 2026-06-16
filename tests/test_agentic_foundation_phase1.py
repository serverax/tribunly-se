"""Phase 1 agentic foundation scaffolding tests."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from backend.core.orchestrator import Orchestrator
from backend.core.agents.domain_plugins import EmploymentUkPlugin, list_domain_plugins
from backend.core.retrieval.rerank import rerank_authorities
from backend.core.tool_registry import get_tool_registry
from backend.core.agent_memory import mask_pii


def test_employment_uk_plugin_loads_config():
    plugin = EmploymentUkPlugin()
    assert plugin.spec.retrieval_domain == "employment_uk"
    assert "unfair_dismissal" in plugin.claim_types()
    assert "deadline" in plugin.agents_for("unfair_dismissal")


def test_list_domain_plugins_includes_employment():
    plugins = list_domain_plugins()
    ids = {p["domain_id"] for p in plugins}
    assert "employment" in ids


def test_orchestrator_classify_route_delegate_merge():
    orch = Orchestrator()
    facts = {"edt": "2025-10-01", "service_start_date": "2019-01-01", "jurisdiction": "EW"}
    message = "Was my dismissal unfair after three years?"

    classification = orch.classify(message, facts)
    assert classification["in_scope"] is True
    assert classification["claim_type"] in ("unfair_dismissal", "out_of_scope")

    route = orch.route(classification["claim_type"], urgency="safe")
    assert "employment_law" in route["agents"]
    assert "deadline_calculate" in route["tools"]

    bundle = MagicMock()
    bundle.exact_rules = []
    bundle.authorities = []

    results = orch.delegate(["evidence"], message, facts, bundle, "EW")
    assert len(results) == 1
    assert results[0].agent_name == "evidence"

    merged = orch.merge(results, route)
    assert merged.agents_run == ["evidence"]
    assert isinstance(merged.to_dict(), dict)


def test_orchestrator_run_stages_records_audit_trail():
    orch = Orchestrator()
    bundle = MagicMock()
    bundle.exact_rules = []
    bundle.authorities = []
    out = orch.run_stages(
        "I was dismissed without warning",
        {"edt": "2025-10-01", "service_start_date": "2019-01-01"},
        bundle,
        claim_type="unfair_dismissal",
        agent_names=["evidence", "deadline"],
    )
    stage_names = [s["stage"] for s in out.stages]
    assert stage_names == ["classify", "route", "delegate", "merge"]
    assert len(out.agents_run) == 2


def test_rerank_authorities_orders_by_combined_score():
    authorities = [
        {"cite": "A", "rrf_score": 0.1, "trust_score": 30, "exact_citation_match": False},
        {"cite": "B", "rrf_score": 0.5, "trust_score": 100, "exact_citation_match": True},
    ]
    ranked = rerank_authorities(authorities)
    assert ranked[0]["cite"] == "B"
    assert "rerank_score" in ranked[0]


def test_mask_pii_strips_email():
    masked = mask_pii("Contact me at user@example.com please")
    assert "[email]" in masked
    assert "user@example.com" not in masked


def test_tool_registry_deadline_calculate():
    reg = get_tool_registry()
    with patch("backend.core.tools.calculate_deadline") as mock_calc:
        mock_calc.return_value = {"limitation_date": "2026-01-01", "source": "rules_table"}
        result = reg.invoke("deadline_calculate", event_date="2025-10-01", event_type="dismissal")
    assert result.status == "ok"
    assert result.data["limitation_date"] == "2026-01-01"


def test_companies_house_stub_without_api_key():
    reg = get_tool_registry()
    result = reg.invoke("companies_house_lookup", company_number="12345678")
    assert result.status == "unavailable"
    assert result.experimental is True


def test_feedback_endpoint_requires_auth_in_jwt_mode():
    from fastapi.testclient import TestClient
    from backend.api.main import app

    client = TestClient(app)
    with patch("backend.core.user_auth.get_auth_mode", return_value="jwt"):
        with patch("backend.core.user_auth.get_current_user", return_value=None):
            r = client.post("/api/feedback", json={"corrected_value": "The EDT was wrong"})
    assert r.status_code == 401


def test_feedback_endpoint_accepts_correction_when_authed():
    from fastapi.testclient import TestClient
    from backend.api.main import app

    client = TestClient(app)
    uid = "00000000-0000-0000-0000-000000000099"
    with patch("backend.core.user_auth.get_auth_mode", return_value="jwt"):
        with patch("backend.core.user_auth.get_current_user", return_value=uid):
            with patch("backend.api.feedback_routes.record_feedback") as mock_rec:
                mock_rec.return_value = {"feedback_id": "fb-1", "status": "pending", "pii_stripped": False}
                r = client.post(
                    "/api/feedback",
                    json={"corrected_value": "Limitation date should be 2026-02-01", "trace_id": "t-1"},
                    headers={"Authorization": "Bearer test"},
                )
    assert r.status_code == 201
    assert r.json()["feedback_id"] == "fb-1"


def test_retrieve_applies_rerank(monkeypatch):
    """retrieve() should attach rerank_score after trust scoring."""
    from backend.core.retrieve import retrieve

    fake_rules = [{"rule_key": "test.rule", "authority_ref": "ERA 1996 s.1", "authority_url": "http://x"}]
    fake_auth = [
        {
            "source_type": "legislation",
            "cite": "ERA 1996 s.98",
            "heading": "ERA 1996 s.98",
            "text": "fairness",
            "url": "http://leg",
            "jurisdiction": "EW",
            "effective_from": date.today(),
            "effective_to": None,
            "rrf_score": 0.2,
            "retrieval": "hybrid",
        }
    ]

    monkeypatch.setattr("backend.core.retrieve.retrieve_rules", lambda *a, **k: fake_rules)
    monkeypatch.setattr(
        "backend.core.retrieve.reciprocal_rank_fusion",
        lambda *a, **k: fake_auth,
    )
    monkeypatch.setattr("backend.core.retrieve._write_retrieval_audit", lambda *a, **k: None)

    bundle = retrieve("unfair dismissal s.98", "unfair_dismissal", "EW", date.today())
    assert bundle.authorities
    assert "rerank_score" in bundle.authorities[0]
