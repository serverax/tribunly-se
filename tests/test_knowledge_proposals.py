"""Tests for controlled write-back (knowledge proposals) and ingestion-only guard."""

from unittest.mock import MagicMock, patch

import pytest

from backend.core.ingestion_write_guard import (
    assert_brain_path_cannot_write_knowledge,
    scan_module_for_direct_sql_writes,
    INGESTION_WRITE_FUNCTIONS,
)
from backend.core.knowledge_proposer import propose_knowledge_gap, approve_proposal


class TestIngestionWriteGuard:
    def test_brain_path_does_not_import_ingestion_writes(self):
        assert_brain_path_cannot_write_knowledge()

    def test_brain_module_has_no_direct_rules_insert(self):
        hits = scan_module_for_direct_sql_writes("backend.core.brain")
        assert hits == []

    def test_pipeline_module_has_no_direct_rules_insert(self):
        hits = scan_module_for_direct_sql_writes("backend.core.pipeline")
        assert hits == []

    def test_ingestion_write_functions_documented(self):
        assert "upsert_rule" in INGESTION_WRITE_FUNCTIONS
        assert "upsert_legislation" in INGESTION_WRITE_FUNCTIONS


class TestKnowledgeProposals:
    def test_propose_creates_row_only(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = (
            "11111111-1111-1111-1111-111111111111",
            "llm",
            "missing_rule",
            {"gap": "test"},
            "unverified",
            "pending",
            "trace-1",
            None,
        )

        with patch("ingestion.db.get_connection", return_value=mock_conn):
            row = propose_knowledge_gap(
                "missing_rule",
                {"rule_key": "test.rule", "claim_type": "unfair_dismissal"},
                trace_id="trace-1",
            )

        assert row is not None
        assert row["approval_status"] == "pending"
        sql = mock_cur.execute.call_args[0][0]
        assert "knowledge.ingestion_proposals" in sql
        assert "rules" not in sql.lower().split("insert into knowledge")[0]

    def test_approve_does_not_insert_rules(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = (
            "11111111-1111-1111-1111-111111111111",
            "missing_rule",
            {"rule_key": "test.rule"},
            "trace-1",
        )

        with patch("ingestion.db.get_connection", return_value=mock_conn), patch(
            "backend.core.outbox.publish",
            return_value="evt-1",
        ) as mock_publish:
            result = approve_proposal("11111111-1111-1111-1111-111111111111")

        assert result["ok"] is True
        mock_publish.assert_called_once()
        assert mock_publish.call_args[0][0] == "ingestion_proposal_approved"
        for call in mock_cur.execute.call_args_list:
            sql = (call[0][0] or "").upper()
            assert "INSERT INTO RULES" not in sql
            assert "INSERT INTO LEGISLATION" not in sql

    def test_propose_invalid_proposer_raises(self):
        with pytest.raises(ValueError):
            propose_knowledge_gap("missing_rule", {}, proposed_by="auto_bot")
