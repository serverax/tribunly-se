"""
Graph-Awareness integration proof — System Update 001 (Knowledge Wiring).

Proves the "variable drop" is closed: the legal relationship map produced by the
BFS graph traversal (legal_nodes/legal_edges) is now INGESTED by the reasoning
engine (Agent ART) before reasoning commences — not computed and dropped.

Two assertions, matching the directive:
  1. ART's input graph_context is non-null AND its nodes match the BFS traversal.
  2. The relationship map is rendered into ART's actual prompt, PRIORITISED above
     the isolated retrieved-authority snippets.

No Apache AGE: this exercises the existing, proven pgvector-backed relational
graph. The graph engine is untouched.
"""
from __future__ import annotations

import pytest

from backend.core.legal_graph import get_claim_subgraph
from backend.core.models import StubReasoningModel
from backend.core.pipeline import assess


class _CapturingModel(StubReasoningModel):
    """Wraps the deterministic stub model and records exactly what ART received,
    so we can assert the graph relationship map reached the reasoning input."""

    def __init__(self) -> None:
        super().__init__()
        self.captured_safe_facts: dict | None = None

    def reason(self, safe_facts, bundle, deadline_info, boundary_log):
        self.captured_safe_facts = dict(safe_facts)
        return super().reason(safe_facts, bundle, deadline_info, boundary_log)


def test_art_input_graph_context_is_nonnull_and_matches_bfs():
    """trace.ART.input.graph_context is non-null and matches the BFS nodes."""
    subgraph = get_claim_subgraph("unfair_dismissal", "EW", max_depth=2)
    if not subgraph.get("nodes"):
        pytest.skip("legal_nodes/legal_edges not seeded in this DB — BFS empty")

    capture = _CapturingModel()
    facts = {
        "edt": "2024-05-01",
        "service_start_date": "2020-01-01",
        "jurisdiction": "EW",
    }
    result = assess(
        "I was dismissed after four years and believe it was unfair.",
        facts,
        model=capture,
        jurisdiction="EW",
        graph_context=subgraph,
    )

    # 1) ART actually received the relationship map (non-null in its input).
    assert capture.captured_safe_facts is not None, "ART.reason() was never called"
    assert capture.captured_safe_facts.get("_legal_relationship_map"), \
        "ART input graph_context is null — the variable was dropped before reasoning"

    # 2) What ART saw matches the BFS traversal node set, exactly.
    used = result["graph_context_used"]
    assert used["used"] is True
    bfs_node_ids = {n["node_id"] for n in subgraph["nodes"]}
    assert set(used["node_ids"]) == bfs_node_ids, \
        "ART input graph nodes do not match the BFS traversal nodes"
    assert used["node_count"] == len(subgraph["nodes"])


def test_relationship_map_is_rendered_and_prioritised_in_art_prompt():
    """The map appears in ART's prompt, ABOVE the isolated authority snippets.
    No DB / no API key required — exercises the prompt builder directly."""
    from backend.core.models import ClaudeReasoningModel
    from shared.schemas import RetrievalBundle

    # Construct without __init__ to avoid requiring an API key for a pure prompt test.
    model = ClaudeReasoningModel.__new__(ClaudeReasoningModel)
    bundle = RetrievalBundle(
        exact_rules=[],
        authorities=[{"cite": "ERA 1996 s.94", "url": "https://example/era94"}],
        insufficient_grounding=False,
    )
    safe_facts = {
        "_legal_relationship_map": (
            "LEGAL KNOWLEDGE GRAPH:\n  [statute] ERA 1996 s.98\n"
            "RELATIONSHIPS:\n  ud_claim --[requires]--> qualifying_service"
        )
    }
    prompt = model._build_prompt(safe_facts, bundle, {})

    assert "LEGAL RELATIONSHIP MAP" in prompt
    assert "ERA 1996 s.98" in prompt
    assert "ud_claim --[requires]--> qualifying_service" in prompt
    # Prioritisation: the map must appear before the isolated authority snippets.
    assert prompt.index("LEGAL RELATIONSHIP MAP") < prompt.index("RETRIEVED AUTHORITIES")


def test_no_graph_context_is_failsoft():
    """When no subgraph exists, reasoning still proceeds (fail-soft, no crash)."""
    from backend.core.models import ClaudeReasoningModel
    from shared.schemas import RetrievalBundle

    model = ClaudeReasoningModel.__new__(ClaudeReasoningModel)
    bundle = RetrievalBundle(exact_rules=[], authorities=[], insufficient_grounding=False)
    prompt = model._build_prompt({}, bundle, {})  # no _legal_relationship_map key
    assert "LEGAL RELATIONSHIP MAP" not in prompt  # section omitted cleanly
    assert "Assess the following unfair dismissal matter." in prompt
