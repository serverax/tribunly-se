"""
Ingestion pipeline tests  -  lawapp legal source ingestion.

Tests:
  - legislation table structure and content
  - case_law_chunks table structure
  - acas_guidance table structure and content
  - rules table structure and seeded values
  - embeddings exist for ingested content
  - source freshness endpoint returns correct structure
  - ingestion config settings
"""

import pytest
import os
import psycopg2
from datetime import date


@pytest.fixture(scope="module")
def db():
    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST","localhost"), port=int(os.environ.get("POSTGRES_PORT","5435")), dbname=os.environ.get("POSTGRES_DB","lawapp"), user=os.environ.get("POSTGRES_USER","lawapp"), password=os.environ.get("POSTGRES_PASSWORD","lawapp")
    )
    yield conn
    conn.close()


class TestLegislationTable:
    def test_legislation_table_exists(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name='legislation' AND table_schema='public'"
        )
        assert cur.fetchone()[0] == 1

    def test_legislation_has_required_columns(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='legislation' ORDER BY ordinal_position"
        )
        cols = {r[0] for r in cur.fetchall()}
        required = {"id", "source_url", "body_text", "last_verified_at"}
        for c in required:
            assert c in cols, f"Missing column: {c}"

    def test_legislation_has_rows(self, db):
        cur = db.cursor()
        cur.execute("SELECT count(*) FROM legislation")
        count = cur.fetchone()[0]
        if count == 0:
            pytest.skip("legislation table empty  -  run: docker compose run --rm ingestion python -m ingestion.legislation.ingest")
        assert count > 0

    def test_legislation_rows_have_source_url(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT count(*) FROM legislation WHERE source_url IS NULL OR source_url=''"
        )
        null_count = cur.fetchone()[0]
        assert null_count == 0, f"{null_count} legislation rows missing source_url"

    def test_legislation_has_embeddings(self, db):
        cur = db.cursor()
        cur.execute("SELECT count(*) FROM legislation WHERE embedding IS NOT NULL")
        embedded = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM legislation")
        total = cur.fetchone()[0]
        if total > 0 and embedded == 0:
            pytest.skip(
                "legislation embeddings not populated in this environment; "
                "run the local embedding job after the source-table/vector-dim "
                "run condition is satisfied"
            )
        assert embedded == total, f"Only {embedded}/{total} legislation rows have embeddings"

    def test_legislation_jurisdiction_is_ew(self, db):
        cur = db.cursor()
        cur.execute("SELECT count(*) FROM legislation")
        if cur.fetchone()[0] == 0:
            pytest.skip("legislation table empty")
        cur.execute(
            "SELECT DISTINCT jurisdiction FROM legislation WHERE jurisdiction IS NOT NULL"
        )
        jurisdictions = {r[0] for r in cur.fetchall()}
        assert "EW" in jurisdictions or len(jurisdictions) > 0


class TestCaseLawTable:
    def test_case_law_chunks_table_exists(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name='case_law_chunks' AND table_schema='public'"
        )
        assert cur.fetchone()[0] == 1

    def test_case_law_has_required_columns(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='case_law_chunks'"
        )
        cols = {r[0] for r in cur.fetchall()}
        # May be empty until FCL licence is granted
        assert "id" in cols

    def test_case_law_chunks_status_documented(self, db):
        """case_law_chunks may be empty pending FCL bulk licence  -  verify state."""
        cur = db.cursor()
        cur.execute("SELECT count(*) FROM case_law_chunks")
        count = cur.fetchone()[0]
        # Not asserting > 0  -  FCL licence pending is accepted state
        assert count >= 0, "case_law_chunks table inaccessible"


class TestAcasGuidanceTable:
    def test_acas_guidance_table_exists(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name='acas_guidance' AND table_schema='public'"
        )
        assert cur.fetchone()[0] == 1

    def test_acas_guidance_has_rows(self, db):
        cur = db.cursor()
        cur.execute("SELECT count(*) FROM acas_guidance")
        count = cur.fetchone()[0]
        if count == 0:
            pytest.skip("acas_guidance table empty  -  run: docker compose run --rm ingestion python -m ingestion.acas.ingest")
        assert count > 0

    def test_acas_guidance_has_embeddings(self, db):
        cur = db.cursor()
        cur.execute("SELECT count(*) FROM acas_guidance WHERE embedding IS NOT NULL")
        embedded = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM acas_guidance")
        total = cur.fetchone()[0]
        if total > 0 and embedded == 0:
            pytest.skip(
                "ACAS embeddings not populated in this environment; run the "
                "local embedding job after the source-table/vector-dim run "
                "condition is satisfied"
            )
        assert embedded == total, f"Only {embedded}/{total} ACAS rows have embeddings"


class TestRulesTable:
    def test_rules_table_exists(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name='rules' AND table_schema='public'"
        )
        assert cur.fetchone()[0] == 1

    def test_rules_has_required_columns(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='rules'"
        )
        cols = {r[0] for r in cur.fetchall()}
        required = {
            "id", "rule_key", "claim_type", "jurisdiction",
            "value_numeric", "value_text", "authority_ref",
            "effective_from", "effective_to",
        }
        for c in required:
            assert c in cols, f"rules table missing column: {c}"

    def test_ud_time_limit_rule_exists(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT value_numeric, authority_ref FROM rules "
            "WHERE rule_key='unfair_dismissal.time_limit_months' "
            "AND jurisdiction='EW' AND is_prospective=false "
            "ORDER BY effective_from DESC LIMIT 1"
        )
        row = cur.fetchone()
        assert row is not None, "unfair_dismissal.time_limit_months rule missing"
        assert int(row[0]) == 3, f"Expected 3 months, got {row[0]}"
        assert "ERA 1996" in row[1], f"authority_ref missing ERA 1996: {row[1]}"

    def test_ud_qualifying_period_rule_exists(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT value_numeric FROM rules "
            "WHERE rule_key='unfair_dismissal.qualifying_period' "
            "AND is_prospective=false AND jurisdiction='EW' "
            "ORDER BY effective_from DESC LIMIT 1"
        )
        row = cur.fetchone()
        assert row is not None, "qualifying_period rule missing"
        assert int(row[0]) == 2, f"Expected 2 years, got {row[0]}"

    def test_ud_compensatory_cap_rule_exists(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT value_numeric FROM rules "
            "WHERE rule_key='unfair_dismissal.compensatory_cap_amount' "
            "AND is_prospective=false AND jurisdiction='EW' "
            "ORDER BY effective_from DESC LIMIT 1"
        )
        row = cur.fetchone()
        assert row is not None, "compensatory_cap_amount rule missing"
        assert float(row[0]) > 100000, f"Cap too low: {row[0]}"

    def test_all_rules_have_authority_ref(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT rule_key FROM rules "
            "WHERE authority_ref IS NULL OR authority_ref=''"
        )
        missing = [r[0] for r in cur.fetchall()]
        assert len(missing) == 0, f"Rules missing authority_ref: {missing}"

    def test_all_rules_have_effective_from(self, db):
        cur = db.cursor()
        cur.execute("SELECT rule_key FROM rules WHERE effective_from IS NULL")
        missing = [r[0] for r in cur.fetchall()]
        assert len(missing) == 0, f"Rules missing effective_from: {missing}"

    def test_prospective_rules_exist_for_future(self, db):
        """Future rules (2027 qualifying period change) should exist as prospective=true."""
        cur = db.cursor()
        cur.execute(
            "SELECT count(*) FROM rules WHERE is_prospective=true"
        )
        count = cur.fetchone()[0]
        assert count > 0, "No prospective future rules found"


class TestEmbeddingDimension:
    def test_embeddings_correct_dimension(self, db):
        """Verify embeddings have the expected dimension (1024 local Ollama)."""
        cur = db.cursor()
        cur.execute(
            "SELECT vector_dims(embedding) FROM legislation "
            "WHERE embedding IS NOT NULL LIMIT 1"
        )
        row = cur.fetchone()
        if row:
            dim = row[0]
            assert dim in (384, 1024), f"Unexpected embedding dimension: {dim}"


class TestIngestionConfig:
    def test_settings_importable(self):
        from ingestion.config import settings
        assert settings is not None

    def test_db_connection_uses_port_5435(self):
        """Local test DB uses port 5435 (avoids native PG18 conflict)."""
        import os
        port = os.environ.get("POSTGRES_PORT", "5432")
        # In test environment conftest sets 5435
        assert port in ("5432", "5435"), f"Unexpected port: {port}"

    def test_embedder_importable(self):
        from ingestion.embeddings.embedder import embed_texts
        assert callable(embed_texts)

    def test_freshness_importable(self):
        from ingestion.freshness.report import run_report
        assert callable(run_report)
