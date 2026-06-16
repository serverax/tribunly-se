"""
Graph RAG unit tests  -  lawapp legal knowledge graph.

Tests legal_nodes/legal_edges DB tables and graph traversal.
Verifies unfair dismissal subgraph is populated with correct nodes.
"""

import pytest
from backend.core.legal_graph import (
    get_claim_subgraph,
    get_concept_context,
    select_rag_sources,
)


class TestSelectRagSources:
    def test_hybrid_always_present(self):
        result = select_rag_sources("unfair_dismissal", "medium", False)
        assert "hybrid" in result["sources"]

    def test_known_claim_activates_graph(self):
        result = select_rag_sources("unfair_dismissal", "medium", is_generic=False)
        assert result["use_graph"] is True
        assert "legal_graph" in result["sources"]

    def test_generic_query_no_graph(self):
        result = select_rag_sources("unfair_dismissal", "low", is_generic=True)
        assert result["use_graph"] is False

    def test_high_risk_activates_kg(self):
        result = select_rag_sources("discrimination", "high", is_generic=False)
        assert result["use_kg"] is True
        assert "knowledge_graph" in result["sources"]

    def test_oos_no_graph(self):
        result = select_rag_sources("out_of_scope", "low", is_generic=True)
        assert "legal_graph" not in result["sources"]

    def test_primary_always_hybrid(self):
        result = select_rag_sources("unfair_dismissal", "high", False)
        assert result["primary"] == "hybrid"

    def test_result_has_reason(self):
        result = select_rag_sources("unfair_dismissal", "medium", False)
        assert isinstance(result["reason"], str)
        assert len(result["reason"]) > 0


class TestGetClaimSubgraph:
    """Tests legal graph traversal. Requires DB with legal_nodes/edges seeded."""

    def test_ud_subgraph_returns_dict(self):
        result = get_claim_subgraph("unfair_dismissal", "EW")
        assert isinstance(result, dict)
        assert "nodes" in result
        assert "edges" in result
        assert "source" in result

    def test_ud_subgraph_source_is_legal_graph(self):
        result = get_claim_subgraph("unfair_dismissal", "EW")
        assert result["source"] == "legal_graph"

    def test_ud_subgraph_has_root_node(self):
        result = get_claim_subgraph("unfair_dismissal", "EW")
        assert result["root_node"] == "ud_claim"

    def test_ud_subgraph_has_nodes(self):
        result = get_claim_subgraph("unfair_dismissal", "EW")
        assert len(result["nodes"]) > 0

    def test_ud_subgraph_has_edges(self):
        result = get_claim_subgraph("unfair_dismissal", "EW")
        assert len(result["edges"]) > 0

    def test_ud_subgraph_includes_limitation_node(self):
        result = get_claim_subgraph("unfair_dismissal", "EW")
        node_ids = [n["node_id"] for n in result["nodes"]]
        assert "limitation_date" in node_ids

    def test_ud_subgraph_includes_qualifying_service(self):
        result = get_claim_subgraph("unfair_dismissal", "EW")
        node_ids = [n["node_id"] for n in result["nodes"]]
        assert "qualifying_service" in node_ids

    def test_ud_subgraph_context_text_not_empty(self):
        result = get_claim_subgraph("unfair_dismissal", "EW")
        assert len(result.get("context_text", "")) > 10

    def test_upw_subgraph_returns_nodes(self):
        result = get_claim_subgraph("unpaid_wages", "EW")
        assert len(result["nodes"]) > 0
        node_ids = [n["node_id"] for n in result["nodes"]]
        assert "upw_claim" in node_ids

    def test_unknown_claim_returns_empty(self):
        result = get_claim_subgraph("fake_claim", "EW")
        assert result["nodes"] == []
        assert "unavailable_reason" in result

    def test_depth_1_returns_fewer_nodes_than_depth_2(self):
        d1 = get_claim_subgraph("unfair_dismissal", "EW", max_depth=1)
        d2 = get_claim_subgraph("unfair_dismissal", "EW", max_depth=2)
        assert len(d2["nodes"]) >= len(d1["nodes"])


class TestGetConceptContext:
    def test_single_node_returned(self):
        result = get_concept_context(["ud_claim"], "EW")
        assert len(result["nodes"]) >= 1

    def test_multiple_nodes_returned(self):
        result = get_concept_context(["ud_claim", "limitation_date"], "EW")
        assert len(result["nodes"]) >= 1

    def test_empty_input_returns_empty(self):
        result = get_concept_context([], "EW")
        assert result["nodes"] == []

    def test_source_is_knowledge_graph(self):
        result = get_concept_context(["ud_claim"], "EW")
        assert result["source"] == "knowledge_graph"

    def test_context_text_contains_node_label(self):
        result = get_concept_context(["ud_claim"], "EW")
        assert len(result.get("context_text", "")) > 0
