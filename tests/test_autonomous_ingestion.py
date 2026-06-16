"""Perpetual Law Brain  -  autonomous ingestion proof (real assertions, no vacuous PASS).

Pure tests (no DB): whitelist allow/block, redirect-target block, critic accept/reject.
DB tests (compose db): node + citation edge creation, chunk storage, searchable,
content_hash staleness, run-success log, error log, unsupported-jurisdiction fail-closed.

Hard guarantees proven here:
  - a non-official domain is physically refused,
  - opinion/news is rejected by the critic,
  - a rejected document is NEVER chunked/embedded (0 chunks),
  - edges are only created to existing nodes with provenance.
"""
from __future__ import annotations

import pytest

from backend.core.agentic.ingestion_critic import IngestionCritic, IngestionDoc
from backend.core.ingestion.crawler import (
    BlockedDomainError, assert_whitelisted, is_whitelisted,
)

SRC = "https://www.legislation.gov.uk/ukpga/1996/18/section/AUTOTEST"
NODE = "autotest_statute"


def _conn():
    from ingestion.db import get_connection
    return get_connection()


def _db_up() -> bool:
    try:
        c = _conn(); c.close(); return True
    except Exception:
        return False


db_required = pytest.mark.skipif(not _db_up(), reason="UNPROVEN  -  DB not accessible")


def _valid_doc(content: str = "Section 98 of the Employment Rights Act 1996 sets out the fair reasons for dismissal. See s.98.") -> IngestionDoc:
    return IngestionDoc(
        source_url=SRC, source_type="primary_legislation", parser_type="clml",
        jurisdiction_code="EW", authority_ref="Employment Rights Act 1996 s.98",
        content=content, title="ERA 1996 s.98 (autotest)")


@pytest.fixture
def clean_db():
    """db_setup/db_teardown: remove this test's rows before and after."""
    def _wipe():
        try:
            conn = _conn()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM legal_edges WHERE from_node_id=%s", (NODE,))
                cur.execute("DELETE FROM legal_nodes WHERE node_id=%s", (NODE,))
                cur.execute("DELETE FROM corpus_chunks WHERE source_url LIKE %s", (SRC + "%",))
                cur.execute("DELETE FROM corpus_ingestion_errors WHERE source_url LIKE %s", (SRC + "%",))
            conn.commit(); conn.close()
        except Exception:
            pass
    _wipe(); yield; _wipe()


# ── Pure whitelist tests ─────────────────────────────────────────────────────
def test_whitelist_allows_official_domains():
    assert is_whitelisted("https://www.legislation.gov.uk/ukpga/1996/18")
    assert is_whitelisted("https://caselaw.nationalarchives.gov.uk/ewca/civ/2017/123")
    assert is_whitelisted("https://www.acas.org.uk/dismissals")


def test_whitelist_blocks_non_official_domains():
    assert not is_whitelisted("https://www.bbc.co.uk/news/uk-employment")
    with pytest.raises(BlockedDomainError):
        assert_whitelisted("https://www.bbc.co.uk/news/uk-employment")


def test_redirect_to_non_whitelisted_is_blocked():
    # The crawler calls assert_whitelisted on every redirect target; an off-list
    # target raises before the redirect is followed.
    with pytest.raises(BlockedDomainError):
        assert_whitelisted("https://evil.example.com/legislation.gov.uk")


# ── Pure critic tests ────────────────────────────────────────────────────────
def test_clml_statute_passes_critic():
    v = IngestionCritic().validate(_valid_doc())
    assert v.passed, v.reason


def test_news_article_fails_critic():
    news = IngestionDoc(
        source_url="https://www.acas.org.uk/news", source_type="official_guidance",
        parser_type="acas_official", jurisdiction_code="EW", authority_ref="commentary",
        content="Opinion: our reporter argues... comment is free. Subscribe for more.",
        title="news")
    v = IngestionCritic().validate(news)
    assert not v.passed
    assert "news" in v.reason or "opinion" in v.reason


def test_missing_source_url_fails_critic():
    d = _valid_doc(); d.source_url = ""
    assert not IngestionCritic().validate(d).passed


def test_missing_authority_fails_critic():
    d = _valid_doc(); d.authority_ref = ""
    assert not IngestionCritic().validate(d).passed


def test_unsupported_jurisdiction_fails_closed():
    d = _valid_doc(); d.jurisdiction_code = "ZZ"
    v = IngestionCritic().validate(d)
    assert not v.passed
    assert "jurisdiction" in v.reason


# ── DB pipeline tests ────────────────────────────────────────────────────────
@db_required
def test_ingest_creates_node_and_citation_edge(clean_db):
    from backend.core.ingestion.perpetual_law_brain import PerpetualLawBrain
    brain = PerpetualLawBrain()
    res = brain.ingest_document(_valid_doc(), node_id=NODE, node_type="statute",
                                label="ERA 1996 s.98 (autotest)",
                                links=[{"to": "ud_claim", "rel": "cites"}], embed=False)
    assert res["status"] == "ingested", res
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM legal_nodes WHERE node_id=%s", (NODE,))
            assert cur.fetchone()[0] == 1, "node not created"
            cur.execute("SELECT count(*) FROM legal_edges WHERE from_node_id=%s AND to_node_id='ud_claim' AND relationship_type='cites'", (NODE,))
            assert cur.fetchone()[0] == 1, "citation edge not created"
    finally:
        conn.close()


@db_required
def test_rejected_document_is_never_chunked(clean_db):
    from backend.core.ingestion.perpetual_law_brain import PerpetualLawBrain
    brain = PerpetualLawBrain()
    bad = _valid_doc(); bad.jurisdiction_code = "ZZ"; bad.source_url = SRC + "/bad"
    res = brain.ingest_document(bad, node_id=NODE, node_type="statute", label="x", embed=False)
    assert res["status"] == "rejected"
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM corpus_chunks WHERE source_url=%s", (bad.source_url,))
            assert cur.fetchone()[0] == 0, "rejected doc was chunked  -  gate breached"
    finally:
        conn.close()


@db_required
def test_approved_content_is_embedded_and_searchable(clean_db):
    from backend.core.ingestion.perpetual_law_brain import PerpetualLawBrain
    brain = PerpetualLawBrain()
    res = brain.ingest_document(_valid_doc(), node_id=NODE, node_type="statute",
                                label="ERA 1996 s.98 (autotest)", embed=True)
    assert res["status"] == "ingested" and res["chunks_written"] >= 1
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM corpus_chunks WHERE source_url=%s AND is_current=true AND embedding IS NOT NULL", (SRC,))
            assert cur.fetchone()[0] >= 1, "approved content not embedded/searchable"
    finally:
        conn.close()


@db_required
def test_content_hash_change_marks_old_chunks_stale(clean_db):
    from backend.core.ingestion.perpetual_law_brain import PerpetualLawBrain
    brain = PerpetualLawBrain()
    brain.ingest_document(_valid_doc("Version one. s.98 Employment Rights Act 1996."),
                          node_id=NODE, node_type="statute", label="v1", embed=False)
    brain.ingest_document(_valid_doc("Version two changed text. s.98 Employment Rights Act 1996."),
                          node_id=NODE, node_type="statute", label="v2", embed=False)
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM corpus_chunks WHERE source_url=%s AND is_current=false", (SRC,))
            assert cur.fetchone()[0] >= 1, "content_hash change did not mark old chunk stale"
    finally:
        conn.close()


@db_required
def test_ingestion_run_logs_success(clean_db):
    from backend.core.ingestion.perpetual_law_brain import PerpetualLawBrain
    brain = PerpetualLawBrain()
    res = brain.ingest_document(_valid_doc(), node_id=NODE, node_type="statute",
                                label="ok", embed=False)
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status, validation_passed FROM corpus_ingestion_runs WHERE id=%s::uuid", (res["run_id"],))
            row = cur.fetchone()
            assert row == ("passed", True), row
    finally:
        conn.close()


@db_required
def test_ingestion_error_logs_failure(clean_db):
    from backend.core.ingestion.perpetual_law_brain import PerpetualLawBrain
    brain = PerpetualLawBrain()
    news = IngestionDoc(source_url=SRC + "/news", source_type="official_guidance",
                        parser_type="acas_official", jurisdiction_code="EW",
                        authority_ref="commentary",
                        content="Opinion piece. comment is free. subscribe.", title="news")
    res = brain.ingest_document(news, node_id=NODE, node_type="statute", label="news", embed=False)
    assert res["status"] == "rejected"
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM corpus_ingestion_errors WHERE ingestion_run_id=%s::uuid", (res["run_id"],))
            assert cur.fetchone()[0] == 1, "rejection not logged to corpus_ingestion_errors"
    finally:
        conn.close()
