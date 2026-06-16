"""Tests for Postgres-backed GraphRAG traversal (port 8018)."""

from unittest.mock import MagicMock, patch

import pytest

from backend.core.rag.graphrag_traversal import (
    GraphRAGTraversal,
    _empty_path,
    build_legal_path,
    health,
)


class TestGraphRAGTraversalClass:
    def test_health_ok_when_db_reachable(self):
        engine = GraphRAGTraversal()
        engine._db_ok = True
        assert engine.health()["mode"] == "postgres"

    def test_health_fail_closed_when_db_down(self):
        engine = GraphRAGTraversal()
        engine._db_ok = False
        h = engine.health()
        assert h["status"] == "degraded"
        assert h["mode"] == "fail_closed"

    def test_traverse_returns_empty_when_db_down(self):
        engine = GraphRAGTraversal()
        engine._db_ok = False
        assert engine.traverse("unfair_dismissal") == []

    def test_module_health_function(self):
        h = health()
        assert "status" in h
        assert "mode" in h


class TestBuildLegalPath:
    def test_unsupported_claim_type_fail_closed(self):
        result = build_legal_path("not_a_real_claim", "x")
        assert result["path"] == []
        assert result["confidence"] == 0.0
        assert result["missing_prerequisites"]

    @patch("backend.core.rag.graphrag_traversal.get_connection")
    def test_db_error_fail_closed(self, mock_conn):
        mock_conn.side_effect = RuntimeError("db down")
        result = build_legal_path("unfair_dismissal", "unfair_dismissal")
        assert result["path"] == []
        assert "unavailable" in result["missing_prerequisites"][0].lower()

    @patch("backend.core.rag.graphrag_traversal.get_connection")
    def test_recursive_cte_path_when_root_exists(self, mock_conn):
        conn = MagicMock()
        mock_conn.return_value = conn
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        root = {"node_id": "ud_claim", "label": "Unfair dismissal", "description": "root"}
        node_row = {
            "node_id": "ud_claim",
            "node_type": "claim_type",
            "label": "Unfair dismissal",
            "description": "root",
            "authority_level": 1,
            "source_ref": "ERA s.94",
            "source_url": "https://example",
            "depth": 0,
        }
        edge_row = {
            "from_node_id": "ud_claim",
            "to_node_id": "qualifying_service",
            "relationship_type": "requires",
            "weight": 1.0,
            "notes": None,
        }

        cur.fetchone.return_value = root
        cur.fetchall.side_effect = [[node_row], [edge_row]]

        result = build_legal_path("unfair_dismissal", "unfair_dismissal")
        assert result["claim_type"] == "unfair_dismissal"
        assert len(result["path"]) == 1
        assert result["path"][0]["node_id"] == "ud_claim"
        assert result["confidence"] > 0


class TestEmptyPathHelper:
    def test_empty_path_shape(self):
        p = _empty_path("x", "EW", ["reason"])
        assert p["path"] == []
        assert p["missing_prerequisites"] == ["reason"]
