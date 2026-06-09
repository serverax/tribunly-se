"""Behavioural tests: required legal-DB extensions, indexes, views and corpus integrity."""
from __future__ import annotations

import pytest

from ingestion.db import get_connection


@pytest.fixture(scope="module")
def cur():
    conn = get_connection()
    c = conn.cursor()
    yield c
    c.close()
    conn.close()


def _idx_exists(cur, name) -> bool:
    cur.execute("SELECT count(*) FROM pg_indexes WHERE indexname=%s", (name,))
    return cur.fetchone()[0] >= 1


def test_extensions(cur):
    cur.execute("SELECT extname FROM pg_extension")
    ext = {r[0] for r in cur.fetchall()}
    assert {"vector", "pgcrypto", "pg_trgm"}.issubset(ext)


def test_vector_index_present(cur):
    cur.execute("SELECT count(*) FROM pg_indexes WHERE indexname LIKE '%emb_hnsw' OR indexname LIKE '%emb_ivf' OR indexname LIKE '%embedding_idx'")
    assert cur.fetchone()[0] >= 1


def test_fulltext_indexes(cur):
    cur.execute("SELECT count(*) FROM pg_indexes WHERE indexname LIKE '%_fts_idx'")
    assert cur.fetchone()[0] >= 3


def test_trigram_indexes(cur):
    cur.execute("SELECT count(*) FROM pg_indexes WHERE indexname LIKE '%_trgm'")
    assert cur.fetchone()[0] >= 5


def test_rules_composite_indexes(cur):
    assert _idx_exists(cur, "rules_key_juris_eff_idx")
    assert _idx_exists(cur, "rules_claim_juris_eff_idx")


def test_views_and_mv_exist(cur):
    cur.execute("SELECT count(*) FROM information_schema.views WHERE table_name IN ('source_freshness','corpus_quality_report')")
    assert cur.fetchone()[0] == 2
    cur.execute("SELECT count(*) FROM pg_matviews WHERE matviewname='mv_current_employment_legal_chunks'")
    assert cur.fetchone()[0] == 1


def test_corpus_chunks_no_missing_provenance(cur):
    cur.execute("SELECT count(*) FROM corpus_chunks WHERE source_url IS NULL OR source_url='' OR chunk_hash IS NULL OR jurisdiction_code IS NULL")
    assert cur.fetchone()[0] == 0


def test_corpus_chunks_idempotent_no_duplicates(cur):
    cur.execute("SELECT count(*)-count(DISTINCT chunk_hash) FROM corpus_chunks")
    assert cur.fetchone()[0] == 0


def test_required_sources_seeded(cur):
    cur.execute("SELECT source_id FROM legal_sources")
    ids = {r[0] for r in cur.fetchall()}
    required = {"legislation_gov_uk", "find_case_law", "acas", "govuk_et_decisions",
                "govuk_eat_decisions", "parliament_bills", "govuk_courts_tribunals_publishing"}
    assert required.issubset(ids), f"missing sources: {required - ids}"


def test_fcl_application_required_until_granted(cur):
    cur.execute("SELECT application_status FROM legal_sources WHERE source_id='find_case_law'")
    assert cur.fetchone()[0] in ("pending", "unknown", "rejected"), "FCL must not be 'granted' without owner action"
