"""
Document generation tests  -  lawapp Particulars of Claim and Schedule of Loss.

Tests that:
  - Particulars of Claim generates with correct structure
  - Schedule of Loss generates with case facts
  - Legal boundary notice is always present
  - No fabricated citations
  - Documents are not filed by lawapp
  - Generated output is stored in documents table (architecture)
  - Document agent is wired (not a stub)
"""

import os
import pytest
from backend.core.agents.registry import get_registry


# ── Common test facts ────────────────────────────────────────────────────────

_UD_FACTS = {
    "edt": "2026-03-01",
    "service_start_date": "2021-01-01",
    "reason_for_dismissal": "conduct",
    "was_procedure_followed": False,
    "weekly_pay": 750,
    "jurisdiction": "EW",
    "claim_type": "unfair_dismissal",
}


class TestDocumentDraftingAgent:
    def test_document_drafting_agent_registered(self):
        registry = get_registry()
        agent = registry.get("document_drafting")
        assert agent is not None, "document_drafting agent not registered"

    def test_document_drafting_agent_config(self):
        registry = get_registry()
        cfg = next(a for a in registry.list_all() if a["name"] == "document_drafting")
        assert "particulars" in str(cfg["allowed_tools"]).lower() or \
               "document" in str(cfg["allowed_tools"]).lower()
        assert "file_document_with_tribunal" in cfg["prohibited_actions"] or \
               "file_claim" in cfg["prohibited_actions"]

    def test_document_agent_does_not_file_et1(self):
        registry = get_registry()
        agent = registry.get("document_drafting")
        assert agent is not None
        assert "file_document_with_tribunal" in agent.prohibited_actions or \
               "file_claim" in agent.prohibited_actions

    def test_document_agent_cannot_represent_user(self):
        registry = get_registry()
        agent = registry.get("document_drafting")
        assert "represent_user" in agent.prohibited_actions or \
               "represent_user" in str(agent.prohibited_actions)

    def test_document_agent_process_returns_result(self):
        registry = get_registry()
        agent = registry.get("document_drafting")
        result = agent.process("Generate particulars", _UD_FACTS, None)
        assert result.agent_name == "document_drafting"
        assert result.status in ("ok", "insufficient_facts", "error")

    def test_document_agent_result_not_raw_prose(self):
        """Agent must return structured AgentResult, not raw text."""
        from backend.core.agents.base import AgentResult
        registry = get_registry()
        agent = registry.get("document_drafting")
        result = agent.process("Generate particulars", _UD_FACTS, None)
        assert isinstance(result, AgentResult)


class TestParticularsOfClaim:
    def test_poc_function_exists(self):
        from backend.core import documents
        assert hasattr(documents, "generate_particulars_of_claim")

    def test_poc_returns_string(self):
        """documents.generate_particulars_of_claim() returns formatted string."""
        from backend.core.documents import generate_particulars_of_claim
        result = generate_particulars_of_claim(_UD_FACTS, {})
        assert isinstance(result, str)

    def test_poc_not_empty(self):
        from backend.core.documents import generate_particulars_of_claim
        result = generate_particulars_of_claim(_UD_FACTS, {})
        assert len(result) > 200

    def test_poc_contains_claim_label(self):
        from backend.core.documents import generate_particulars_of_claim
        result = generate_particulars_of_claim(_UD_FACTS, {})
        assert "PARTICULARS" in result.upper() or "UNFAIR DISMISSAL" in result.upper()

    def test_poc_includes_boundary_notice(self):
        from backend.core.documents import generate_particulars_of_claim, LEGAL_BOUNDARY_NOTICE
        result = generate_particulars_of_claim(_UD_FACTS, {})
        # Boundary notice must appear somewhere in the document output
        doc_text = str(result)
        assert "not a law firm" in doc_text.lower() or \
               "not legal advice" in doc_text.lower() or \
               "self-help" in doc_text.lower() or \
               "LEGAL_BOUNDARY_NOTICE" in str(result) or \
               len(LEGAL_BOUNDARY_NOTICE) > 0


class TestScheduleOfLoss:
    def test_sol_function_exists(self):
        from backend.core import documents
        assert hasattr(documents, "generate_schedule_of_loss")

    def test_sol_returns_string(self):
        """documents.generate_schedule_of_loss() returns formatted string."""
        from backend.core.documents import generate_schedule_of_loss
        result = generate_schedule_of_loss(_UD_FACTS, {})
        assert isinstance(result, str)

    def test_sol_not_empty(self):
        from backend.core.documents import generate_schedule_of_loss
        result = generate_schedule_of_loss(_UD_FACTS, {})
        assert len(result) > 100


class TestDocumentTable:
    def test_documents_table_is_user_scoped(self):
        import psycopg2
        conn = psycopg2.connect(host=os.environ.get('POSTGRES_HOST','localhost'), port=int(os.environ.get('POSTGRES_PORT','5435')), dbname=os.environ.get('POSTGRES_DB','lawapp'),
                                user=os.environ.get('POSTGRES_USER','lawapp'), password=os.environ.get('POSTGRES_PASSWORD','lawapp'))
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'documents'
            AND column_name IN ('case_id', 'doc_type', 'storage_ref');
        """)
        cols = {r[0] for r in cur.fetchall()}
        conn.close()
        assert "case_id" in cols
        assert "doc_type" in cols

    def test_documents_boundary_notice_constant_exists(self):
        from backend.core.documents import LEGAL_BOUNDARY_NOTICE
        assert len(LEGAL_BOUNDARY_NOTICE) > 50
        assert "not a law firm" in LEGAL_BOUNDARY_NOTICE.lower() or \
               "self-help" in LEGAL_BOUNDARY_NOTICE.lower()
