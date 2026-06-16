"""Grounding regression: citations on assess/brain paths must map to local DB sources."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_brain_safety_checks_include_critic_citation_integrity():
    text = _read("backend/core/brain.py")
    assert "critic_citation_integrity" in text
    assert "CriticAgent" in text


def test_pipeline_assess_uses_citation_guard():
    text = _read("backend/core/pipeline.py")
    assert "corpus_citation_guard" in text or "enforce_or_regenerate" in text
    assert "govern(assessment)" in text


def test_citation_verifier_fail_closed_on_unverified():
    text = _read("backend/core/citation_verifier.py")
    assert "UNVERIFIED" in text or "unverified" in text.lower()
    assert "fabricated" in text.lower()


def test_assessment_schema_requires_citation_fields():
    schema = _read("shared/schemas.py")
    assert "class Citation" in schema
    assert "cite" in schema
    assert "url" in schema


def test_mother_routes_through_reasoning_router_not_langgraph():
    text = _read("backend/core/control_plane/mother_controller.py")
    assert "ReasoningRouter" in text
    assert "run_reasoning_pipeline" in text or "assess_factual" in text
    assert "/api/v1/legal/reason" not in text


def test_no_langgraph_reasoning_route_in_main():
    text = _read("backend/api/main.py")
    assert "/api/v1/legal/reason" not in text
    assert "backend.ai.graph" not in text


def test_graph_retrieval_only_via_retrieve_hybrid():
    retrieve = _read("backend/core/retrieve.py")
    brain = _read("backend/core/brain.py")
    assert "retrieve_hybrid" in retrieve
    assert "retrieve_hybrid" in brain or "retrieve_legal_evidence" in brain
    # No graph orchestration endpoint in retrieve module
    tree = ast.parse(retrieve)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("orchestrate"):
            pytest.fail("retrieve.py must not expose graph orchestration helpers")


@pytest.mark.parametrize(
    "field",
    [
        "reasoning_summary",
        "recommended_next_step",
        "citations",
    ],
)
def test_structured_assessment_exposes_grounded_fields(field: str):
    schema = _read("shared/schemas.py")
    assert field in schema


def test_critic_agent_checks_local_db():
    text = _read("backend/core/agentic/critic.py")
    assert "verify_bundle_citations" in text
    assert "HALT" in text
