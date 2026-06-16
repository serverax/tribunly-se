"""Tests for Graph RAG Layer v1 hybrid merge (Postgres mode minimum)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


class TestGraphEnginePostgresMode:
    def test_neo4j_disabled_uses_postgres_engine(self, monkeypatch):
        monkeypatch.delenv("NEO4J_ENABLED", raising=False)
        from backend.core.rag.graph_engine import build_graph_chain

        with patch("backend.core.rag.graph_engine._postgres_chain") as mock_pg:
            mock_pg.return_value = {
                "engine": "postgres",
                "path": [{"node_id": "ud_claim"}],
                "edges": [],
                "confidence": 0.6,
            }
            result = build_graph_chain("unfair_dismissal", use_cache=False)
        assert result["engine"] == "postgres"
        mock_pg.assert_called_once()

    def test_search_maps_reasonable_responses_to_unfair_dismissal(self, monkeypatch):
        monkeypatch.delenv("NEO4J_ENABLED", raising=False)
        from backend.core.rag.graph_rag_chain import search_legal_chain

        with patch("backend.core.rag.graph_engine.build_graph_chain") as mock_build:
            mock_build.return_value = {
                "engine": "postgres",
                "path": [{"node_id": "reasonableness_test", "label": "Band of reasonable responses"}],
                "edges": [],
                "confidence": 0.7,
            }
            result = search_legal_chain("unfair dismissal band of reasonable responses")
        assert result["matched_claim_type"] == "unfair_dismissal"
        mock_build.assert_called_once()


class TestRetrieveHybrid:
    def test_retrieve_hybrid_context_shape(self, monkeypatch):
        monkeypatch.delenv("NEO4J_ENABLED", raising=False)
        from backend.core.retrieve import retrieve_hybrid_context
        from shared.schemas import RetrievalBundle

        mock_bundle = RetrievalBundle(
            exact_rules=[{"rule_key": "unfair_dismissal.time_limit_months"}],
            authorities=[{"cite": "ERA 1996 s.98", "type": "legislation"}],
            insufficient_grounding=False,
        )
        mock_graph = {
            "path": [{"node_id": "reasonableness_test"}],
            "engine": "postgres",
        }

        with patch("backend.core.retrieve.retrieve", return_value=mock_bundle):
            with patch("backend.core.retrieve.retrieve_graph_context", return_value=mock_graph):
                ctx = retrieve_hybrid_context(
                    "unfair dismissal band of reasonable responses",
                    "unfair_dismissal",
                    "EW",
                    date.today(),
                )

        assert "semantic" in ctx and "graph" in ctx and "rules" in ctx
        assert len(ctx["rules"]) == 1
        assert ctx["graph"]["engine"] == "postgres"

    def test_retrieve_hybrid_bundle_has_graph_semantic_rules(self, monkeypatch):
        monkeypatch.delenv("NEO4J_ENABLED", raising=False)
        from backend.core.retrieve import retrieve_hybrid

        mock_bundle = MagicMock()
        mock_bundle.authorities = [{"cite": "ERA 1996 s.98"}]
        mock_bundle.exact_rules = [{"rule_key": "test"}]
        mock_bundle.grounding_score = 0.8
        mock_bundle.model_copy = lambda update: MagicMock(**{**mock_bundle.__dict__, **update})

        with patch("backend.core.retrieve.retrieve", return_value=mock_bundle):
            with patch("backend.core.rag.graph_rag_chain.build_legal_chain") as mock_chain:
                mock_chain.return_value = {
                    "path": [{"node_id": "ud_claim"}],
                    "edges": [],
                    "engine": "postgres",
                    "confidence": 0.5,
                }
                bundle = retrieve_hybrid("unfair dismissal", "unfair_dismissal", "EW", date.today())

        assert bundle.graph.get("engine") == "postgres"
        assert bundle.semantic.get("authorities")
        assert bundle.rules


class TestGraphRagServiceModels:
    def test_graph_engine_mode_postgres_by_default(self, monkeypatch):
        monkeypatch.setenv("NEO4J_ENABLED", "false")
        from backend.core.rag.graphrag_traversal import graph_engine_mode

        assert graph_engine_mode() == "postgres"
