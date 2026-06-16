"""
RAG (Retrieval-Augmented Generation) tests.

Tests hybrid search: SQL rules + BM25 keyword + pgvector semantic.
Tests citation grounding, authority ranking, jurisdiction filtering.
"""

import pytest
from backend.core.retrieve import retrieve, retrieve_rules, retrieve_keyword


# ── SQL rules retrieval ───────────────────────────────────────────────────────

class TestRetrieveRules:
    def test_ud_rules_returned(self):
        rules = retrieve_rules("unfair_dismissal", "EW", "2025-10-01")
        assert len(rules) > 0

    def test_time_limit_rule_present(self):
        rules = retrieve_rules("unfair_dismissal", "EW", "2025-10-01")
        keys = [r["rule_key"] for r in rules]
        assert any("time_limit_months" in k for k in keys)

    def test_qualifying_period_rule_present(self):
        rules = retrieve_rules("unfair_dismissal", "EW", "2025-10-01")
        keys = [r["rule_key"] for r in rules]
        assert any("qualifying_period" in k for k in keys)

    def test_upw_rules_returned(self):
        rules = retrieve_rules("unpaid_wages", "EW", "2025-10-01")
        assert len(rules) > 0

    def test_rules_have_authority_ref(self):
        rules = retrieve_rules("unfair_dismissal", "EW", "2025-10-01")
        for r in rules:
            assert r.get("authority_ref"), f"Rule missing authority_ref: {r}"

    def test_rules_have_authority_url(self):
        rules = retrieve_rules("unfair_dismissal", "EW", "2025-10-01")
        for r in rules:
            assert r.get("authority_url"), f"Rule missing authority_url: {r}"

    def test_prospective_rules_excluded(self):
        rules = retrieve_rules("unfair_dismissal", "EW", "2025-10-01")
        # No future-only rules should appear
        for r in rules:
            assert not r.get("is_prospective", False), f"Prospective rule in results: {r}"


# ── Hybrid retrieval (retrieve()) ─────────────────────────────────────────────

class TestHybridRetrieve:
    def test_retrieve_returns_bundle(self):
        from backend.core.retrieve import RetrievalBundle
        bundle = retrieve("unfair dismissal conduct no procedure", "unfair_dismissal", "EW", "2025-10-01")
        assert bundle is not None

    def test_bundle_has_exact_rules(self):
        bundle = retrieve("unfair dismissal", "unfair_dismissal", "EW", "2025-10-01")
        assert hasattr(bundle, "exact_rules")
        assert len(bundle.exact_rules) > 0

    def test_bundle_has_authorities(self):
        import psycopg2, os
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", 5435)),
            dbname=os.environ.get("POSTGRES_DB", "lawapp"),
            user=os.environ.get("POSTGRES_USER", "lawapp"),
            password=os.environ.get("POSTGRES_PASSWORD", "lawapp"),
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM legislation")
        leg_count = cur.fetchone()[0]
        conn.close()
        if leg_count == 0:
            pytest.skip("legislation table empty  -  run ingestion to populate semantic authorities")
        bundle = retrieve("unfair dismissal section 98", "unfair_dismissal", "EW", "2025-10-01")
        assert hasattr(bundle, "authorities")
        assert len(bundle.authorities) > 0

    def test_authorities_have_cite_and_url(self):
        bundle = retrieve("unfair dismissal", "unfair_dismissal", "EW", "2025-10-01")
        for a in bundle.authorities:
            assert a.get("cite"), f"Authority missing cite: {a}"
            assert a.get("url"), f"Authority missing url: {a}"

    def test_authorities_have_trust_score(self):
        bundle = retrieve("dismissal procedure ACAS", "unfair_dismissal", "EW", "2025-10-01")
        for a in bundle.authorities:
            assert "trust_score" in a, f"Authority missing trust_score: {a}"

    def test_insufficient_grounding_flag(self):
        bundle = retrieve("unfair dismissal", "unfair_dismissal", "EW", "2025-10-01")
        assert hasattr(bundle, "insufficient_grounding")
        assert isinstance(bundle.insufficient_grounding, bool)

    def test_no_hallucinated_sources(self):
        bundle = retrieve("unfair dismissal ERA 1996", "unfair_dismissal", "EW", "2025-10-01")
        for a in bundle.authorities:
            cite = a.get("cite", "")
            # All sources must have a real url or source_id
            assert a.get("url") or a.get("source_id"), f"Source with no reference: {cite}"

    def test_jurisdiction_filtering(self):
        # EW jurisdiction retrieval
        bundle = retrieve("unfair dismissal", "unfair_dismissal", "EW", "2025-10-01")
        # All returned rules must be EW jurisdiction
        for r in bundle.exact_rules:
            assert r.get("jurisdiction", "EW") == "EW"


# ── BM25 keyword retrieval ────────────────────────────────────────────────────

class TestKeywordRetrieval:
    def test_keyword_search_returns_results(self):
        results = retrieve_keyword("unfair dismissal s.98", "EW", "2025-10-01")
        assert isinstance(results, list)

    def test_keyword_results_have_cite(self):
        results = retrieve_keyword("dismissal procedure ACAS code", "EW", "2025-10-01")
        for r in results:
            assert "cite" in r or "text" in r
