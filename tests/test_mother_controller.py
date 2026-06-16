"""Tests for MotherController control plane entry point."""

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


class TestMotherController:
    def test_process_factual_lane(self):
        from backend.core.control_plane.mother_controller import MotherController, MotherInput

        ctrl = MotherController()
        out = ctrl.process(
            MotherInput(
                query="What is the time limit to bring an unfair dismissal claim?",
                facts={},
                use_model=False,
            )
        )
        body = out.to_dict()
        assert body["status"] == "ok"
        assert body["source"] == "rules_table"
        assert out.governance_verdict in ("PASS", "FAIL", "ESCALATE", "HUMAN_REVIEW")
        assert body.get("control_plane_stages")
        assert any(s["stage"] == "intake" for s in body["control_plane_stages"])

    def test_assess_wires_mother_controller(self, client):
        r = client.post(
            "/assess",
            json={
                "query": "What is the time limit to bring an unfair dismissal claim?",
                "facts": {},
                "use_model": False,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("control_plane_stages") or body.get("governance_verdict")
        assert body.get("trace_id")

    def test_diagnosis_alias(self, client):
        r = client.post(
            "/api/diagnosis",
            json={
                "query": "What is the time limit to bring an unfair dismissal claim?",
                "facts": {},
                "use_model": False,
            },
        )
        assert r.status_code == 200, r.text
        assert r.json().get("result_type") == "final_governed_assessment"

    def test_out_of_scope_fail_closed(self):
        from backend.core.control_plane.mother_controller import MotherController, MotherInput

        out = MotherController().process(
            MotherInput(
                query="How do I get a divorce in France?",
                facts={},
                use_model=False,
            )
        )
        assert out.to_dict()["status"] == "not_supported"

    def test_swarm_agents_registered(self):
        from backend.core.agents.registry import get_registry

        reg = get_registry()
        for name in ("intake", "retrieval", "graph", "reasoning", "risk", "judge", "document"):
            assert reg.get(name) is not None, f"missing swarm agent: {name}"
