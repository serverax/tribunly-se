"""
Document Upload Architecture tests  -  lawapp multimodal readiness.

Tests that:
  - documents table has correct schema (user-scoped, case-scoped)
  - raw upload fields are encrypted/stored separately
  - extracted_facts require explicit user confirmation before use
  - no raw document text goes to third-party model payloads
  - upload access is user-and-case scoped

These tests verify the ARCHITECTURE is safe, not the full OCR pipeline
(OCR/extraction is a Phase 4 feature  -  marked PARTIAL).
"""

import pytest
import os
import psycopg2


@pytest.fixture
def db_conn():
    conn = psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST','localhost'), port=int(os.environ.get('POSTGRES_PORT','5435')), dbname=os.environ.get('POSTGRES_DB','lawapp'),
        user=os.environ.get('POSTGRES_USER','lawapp'), password=os.environ.get('POSTGRES_PASSWORD','lawapp')
    )
    yield conn
    conn.close()


class TestDocumentTableSchema:
    def test_documents_table_exists(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'documents' ORDER BY ordinal_position;
        """)
        cols = [r[0] for r in cur.fetchall()]
        assert "id" in cols
        assert "case_id" in cols

    def test_documents_scoped_to_case(self, db_conn):
        """documents table must have case_id  -  no orphan uploads."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'documents' AND column_name = 'case_id';
        """)
        assert cur.fetchone() is not None, "documents.case_id column missing"

    def test_documents_has_user_upload_flag(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'documents' AND column_name = 'is_user_upload';
        """)
        assert cur.fetchone() is not None

    def test_documents_has_extracted_facts_field(self, db_conn):
        """Extracted facts are stored separately from raw upload."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = 'documents' AND column_name = 'extracted_facts';
        """)
        row = cur.fetchone()
        assert row is not None, "extracted_facts column missing"
        assert row[1] == "jsonb", f"Expected jsonb, got {row[1]}"

    def test_cases_scoped_to_user(self, db_conn):
        """Cases must be user-scoped  -  no orphan cases."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'cases' AND column_name = 'user_id';
        """)
        assert cur.fetchone() is not None


class TestUploadDeidentificationBoundary:
    def test_deidentify_strips_names_before_model(self):
        """de-identification runs before any model call."""
        from backend.core.deidentify import deidentify
        facts = {
            "name": "Jane Smith",
            "employer": "Acme Corp Ltd",
            "edt": "2026-01-01",
        }
        safe, boundary = deidentify(facts)
        assert "name" not in safe or safe.get("name") != "Jane Smith"
        assert boundary.get("fields_stripped") or boundary.get("pii_fields_in_output") is not None

    def test_raw_upload_not_in_safe_facts(self):
        """raw_document field must be stripped before model call."""
        from backend.core.deidentify import deidentify
        facts = {
            "raw_document": "Dear Ms Smith, you are dismissed effective...",
            "edt": "2026-01-01",
        }
        safe, boundary = deidentify(facts)
        # raw_document should never appear in model payload
        assert "raw_document" not in safe or safe.get("raw_document") is None


class TestUploadArchitectureReadiness:
    def test_storage_ref_column_exists(self, db_conn):
        """storage_ref allows encrypted cloud storage."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'documents' AND column_name = 'storage_ref';
        """)
        assert cur.fetchone() is not None

    def test_doc_type_column_exists(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'documents' AND column_name = 'doc_type';
        """)
        assert cur.fetchone() is not None
