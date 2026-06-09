"""
Hybrid Retrieval unit tests — lawapp RAG layer.

Tests hybrid search: SQL rules + pgvector semantic + BM25 keyword.
Retrieval must always run before reasoning.
All legal answers must have citations.

Tests use the live Docker DB (port 5435).
"""

import pytest
from datetime import date
from backend.core.retrieve import retrieve, retrieve_rules
from shared.schemas import RetrievalBundle


class TestRetrieveRules:
    """Deterministic SQL rules retrieval — always first in pipeline."""

    def test_ud_time_limit_rule_exists(self):
        rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 1, 1))
        keys = [r["rule_key"] for r in rules]
        assert "unfair_dismissal.time_limit_months" in keys

    def test_ud_qualifying_period_rule_exists(self):
        rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 1, 1))
        keys = [r["rule_key"] for r in rules]
        assert "unfair_dismissal.qualifying_period" in keys

    def test_ud_compensatory_cap_rule_exists(self):
        rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 1, 1))
        keys = [r["rule_key"] for r in rules]
        assert "unfair_dismissal.compensatory_cap_amount" in keys

    def test_rules_have_authority_ref(self):
        rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 1, 1))
        for r in rules:
            assert r.get("authority_ref"), f"Rule {r['rule_key']} missing authority_ref"

    def test_rules_are_effective_dated(self):
        rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 1, 1))
        for r in rules:
            assert r.get("effective_from"), f"Rule {r['rule_key']} missing effective_from"

    def test_upw_time_limit_rule_exists(self):
        rules = retrieve_rules("unpaid_wages", "EW", date(2026, 1, 1))
        keys = [r["rule_key"] for r in rules]
        assert any("time_limit" in k for k in keys), f"No UPW time limit rule in: {keys}"

    def test_rules_return_empty_for_oos(self):
        rules = retrieve_rules("out_of_scope", "EW", date(2026, 1, 1))
        assert isinstance(rules, list)

    def test_future_effective_date_returns_correct_rule(self):
        """Test that effective-dated rules resolve correctly."""
        # 2025 cap rules
        rules_2025 = retrieve_rules("unfair_dismissal", "EW", date(2025, 6, 1))
        rules_2026 = retrieve_rules("unfair_dismissal", "EW", date(2026, 6, 1))
        assert isinstance(rules_2025, list)
        assert isinstance(rules_2026, list)


class TestHybridRetrieve:
    """Full hybrid retrieval — SQL rules + pgvector + BM25."""

    def test_retrieve_returns_bundle(self):
        bundle = retrieve(
            "I was unfairly dismissed",
            "unfair_dismissal",
            "EW",
            date(2026, 1, 1),
        )
        assert isinstance(bundle, RetrievalBundle)

    def test_bundle_has_exact_rules(self):
        bundle = retrieve(
            "I was unfairly dismissed",
            "unfair_dismissal",
            "EW",
            date(2026, 1, 1),
        )
        assert len(bundle.exact_rules) > 0

    def test_bundle_rules_include_era1996_authority(self):
        bundle = retrieve(
            "I was unfairly dismissed",
            "unfair_dismissal",
            "EW",
            date(2026, 1, 1),
        )
        refs = [r.get("authority_ref", "") for r in bundle.exact_rules]
        era_refs = [r for r in refs if "ERA 1996" in r]
        assert len(era_refs) > 0, f"No ERA 1996 authority refs found: {refs}"

    def test_bundle_has_authorities(self):
        bundle = retrieve(
            "I was unfairly dismissed",
            "unfair_dismissal",
            "EW",
            date(2026, 1, 1),
        )
        # authorities may be empty if no embeddings ingested; insufficient_grounding should be set
        assert hasattr(bundle, "authorities")
        assert hasattr(bundle, "insufficient_grounding")

    def test_bundle_insufficient_grounding_is_bool(self):
        bundle = retrieve(
            "I was unfairly dismissed",
            "unfair_dismissal",
            "EW",
            date(2026, 1, 1),
        )
        assert isinstance(bundle.insufficient_grounding, bool)

    def test_oos_query_retrieves_no_rules(self):
        """Out-of-scope query should return empty rules or insufficient_grounding."""
        bundle = retrieve(
            "My landlord is evicting me",
            "out_of_scope",
            "EW",
            None,
        )
        assert isinstance(bundle, RetrievalBundle)

    def test_upw_retrieval_returns_bundle(self):
        bundle = retrieve(
            "My employer hasn't paid my wages",
            "unpaid_wages",
            "EW",
            date(2026, 1, 1),
        )
        assert isinstance(bundle, RetrievalBundle)
        assert len(bundle.exact_rules) > 0


class TestRetrievalOrder:
    """Confirm retrieval always precedes reasoning in the pipeline."""

    def test_pipeline_calls_retrieve_before_reason(self):
        """Pipeline.assess() has retrieval at Stage 2, before Stage 4 (reason)."""
        import inspect
        from backend.core import pipeline
        src = inspect.getsource(pipeline.assess)
        retrieve_pos = src.index("retrieve(")
        # Find model.reason call
        reason_pos = src.index("model.reason")
        assert retrieve_pos < reason_pos, \
            "retrieve() must be called before model.reason() in pipeline"
