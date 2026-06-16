"""Hybrid Graph RAG tests (Postgres mode minimum)."""

from unittest.mock import MagicMock, patch

import pytest

from backend.core.rag.graph_engine import build_graph_chain, search_graph_by_query
from backend.core.rag.graph_rag_chain import build_legal_chain, format_chain, score_path
from backend.core.retrieve import retrieve_hybrid


class TestGraphRagChain:
  def test_format_chain_includes_engine(self):
        chain = {
            "engine": "postgres",
            "confidence": 0.7,
            "path": [{"node_id": "a", "node_type": "legal_test", "label": "Test"}],
            "edges": [],
        }
        text = format_chain(chain)
        assert "postgres" in text
        assert "Test" in text

    def test_score_path_bounded(self):
        chain = {
            "confidence": 0.6,
            "path": [
                {"node_type": "legal_test", "source_url": "https://example.com"},
                {"node_type": "legal_test"},
            ],
        }
        assert 0.0 <= score_path(chain) <= 1.0

    @patch("backend.core.rag.graph_engine._neo4j_enabled", return_value=False)
    @patch("backend.core.rag.graph_engine._postgres_chain")
    def test_build_graph_chain_postgres_mode(self, mock_pg, _neo):
        mock_pg.return_value = {
            "engine": "postgres",
            "path": [],
            "edges": [],
            "confidence": 0.0,
            "missing_prerequisites": [],
            "context_text": "",
        }
        result = build_graph_chain("unfair_dismissal", use_cache=False)
        assert result["engine"] == "postgres"
        mock_pg.assert_called_once()

    def test_search_maps_reasonable_responses_query(self):
        with patch("backend.core.rag.graph_engine.build_graph_chain") as mock_chain:
            mock_chain.return_value = {
                "engine": "postgres",
                "path": [],
                "edges": [],
                "confidence": 0.5,
                "context_text": "",
            }
            out = search_graph_by_query("unfair dismissal band of reasonable responses")
            assert out["matched_claim_type"] == "unfair_dismissal"


class TestRetrieveHybrid:
    @patch("backend.core.retrieve.retrieve")
    @patch("backend.core.rag.graph_rag_chain.build_legal_chain")
    def test_retrieve_hybrid_merges_graph(self, mock_chain, mock_retrieve):
        from datetime import date
        from shared.schemas import RetrievalBundle

        mock_retrieve.return_value = RetrievalBundle(
            exact_rules=[{"rule_key": "qualifying_period"}],
            authorities=[{"cite": "ERA s.98", "type": "legislation"}],
            insufficient_grounding=False,
            grounding_score=0.8,
            confidence_score=0.8,
        )
        mock_chain.return_value = {
            "path": [{"node_id": "ud_claim", "label": "Unfair dismissal"}],
            "edges": [],
            "engine": "postgres",
            "confidence": 0.6,
        }

        bundle = retrieve_hybrid(
            "unfair dismissal",
            "unfair_dismissal",
            "EW",
            date.today(),
            use_graph=True,
        )
        assert bundle.graph.get("engine") == "postgres"
        assert len(bundle.graph.get("nodes", [])) == 1
        assert bundle.rules == bundle.exact_rules
        assert bundle.semantic.get("query") == "unfair dismissal"

    @patch("backend.core.retrieve.retrieve")
    def test_retrieve_hybrid_skips_graph_when_disabled(self, mock_retrieve):
        from datetime import date
        from shared.schemas import RetrievalBundle

        mock_retrieve.return_value = RetrievalBundle(
            exact_rules=[],
            authorities=[],
            insufficient_grounding=True,
        )
        bundle = retrieve_hybrid("x", "unfair_dismissal", "EW", date.today(), use_graph=False)
        assert bundle.graph == {}
