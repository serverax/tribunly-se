"""
Hybrid RAG corpus retrieval tests (order Workflow G + addendum §7).

Repeatable proof that hybrid search returns BOTH vector and lexical results from
the real local corpus, that citations carry official source URLs, that a grounded
query is not insufficient_grounding, and that with no sources and no rules the
bundle fails closed (insufficient_grounding=True).

Requires a reachable Postgres with the corpus ingested. On the host set:
  POSTGRES_HOST=localhost POSTGRES_PORT=5435 POSTGRES_USER=lawapp
  POSTGRES_PASSWORD=lawapp POSTGRES_DB=lawapp
"""

from __future__ import annotations

from datetime import date

import pytest

import backend.core.retrieve as R


def _db_available() -> bool:
    try:
        from ingestion.db import get_connection
        c = get_connection()
        c.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres/corpus not reachable")

_Q = "unfair dismissal fair reason ERA 1996 s98 ACAS disciplinary procedure"


def _bundle(query: str, claim_type: str = "unfair_dismissal") -> dict:
    return R.retrieve(query, claim_type, "EW", date(2026, 5, 10)).model_dump()


def _corpus_populated() -> bool:
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM legislation")
                return cur.fetchone()[0] > 0
        finally:
            conn.close()
    except Exception:
        return False


@pytest.mark.skipif(not _corpus_populated(), reason="corpus empty  -  run ingest script first")
def test_hybrid_returns_vector_and_lexical():
    d = _bundle(_Q)
    auths = d["authorities"]
    assert len(auths) > 0, "no authorities returned"
    methods = {a.get("retrieval") for a in auths}
    # vector path contributed (vector or hybrid) AND lexical path contributed (lexical or hybrid)
    assert any(m in ("vector", "hybrid") for m in methods), f"no vector hits: {methods}"
    assert any(m in ("lexical", "hybrid") for m in methods), f"no lexical hits: {methods}"
    assert d["insufficient_grounding"] is False


@pytest.mark.skipif(not _corpus_populated(), reason="corpus empty  -  run ingest script first")
def test_citations_have_official_source_urls():
    d = _bundle("unfair dismissal fair reason capability conduct")
    urls = [a.get("url") for a in d["authorities"] if a.get("url")]
    assert urls, "no source URLs on authorities"
    assert any(("legislation.gov.uk" in u) or ("acas.org.uk" in u) for u in urls), urls


def test_no_sources_and_no_rules_fails_closed(monkeypatch):
    # Force both retrieval paths to return nothing and use an unknown claim type
    # (no rules). The bundle MUST fail closed rather than fabricate grounding.
    monkeypatch.setattr(R, "retrieve_keyword", lambda *a, **k: [])
    monkeypatch.setattr(R, "retrieve_semantic", lambda *a, **k: [])
    d = R.retrieve("anything at all", "not_a_real_claim_type", "EW", date(2026, 5, 10)).model_dump()
    assert d["authorities"] == [] or len(d["authorities"]) == 0
    assert d["insufficient_grounding"] is True
