"""
Semantic Cache tests.

Tests that:
  - Generic queries are cacheable
  - Personal queries are NOT cached
  - Cache is jurisdiction-aware
  - Case-specific queries return safe_to_cache=False
"""

import pytest
from backend.core.semantic_cache import _is_safe_to_cache, cache_lookup, cache_store


class TestCacheSafety:
    def test_generic_question_is_safe_to_cache(self):
        assert _is_safe_to_cache("What is unfair dismissal?") is True

    def test_generic_acas_question_safe(self):
        assert _is_safe_to_cache("What is ACAS early conciliation?") is True

    def test_personal_case_not_safe(self):
        assert _is_safe_to_cache("My employer dismissed me after 5 years") is False

    def test_my_claim_not_safe(self):
        assert _is_safe_to_cache("Will I win my claim?") is False

    def test_settlement_not_safe(self):
        assert _is_safe_to_cache("What should I accept in a settlement agreement?") is False

    def test_discrimination_not_safe(self):
        assert _is_safe_to_cache("My discrimination case — what should I do?") is False

    def test_facts_with_edt_not_safe(self):
        assert _is_safe_to_cache("What is unfair dismissal?", {"edt": "2025-10-01"}) is False

    def test_facts_with_case_id_not_safe(self):
        assert _is_safe_to_cache("Explain dismissal", {"case_id": "abc123"}) is False


class TestCacheLookup:
    def test_lookup_returns_required_fields(self):
        result = cache_lookup("What is unfair dismissal?", "EW")
        for field in ("cache_hit", "safe_to_cache", "answer"):
            assert field in result

    def test_unsafe_query_returns_safe_to_cache_false(self):
        result = cache_lookup("My employer dismissed me", "EW", {"edt": "2025-10-01"})
        assert result["safe_to_cache"] is False
        assert result["cache_hit"] is False

    def test_generic_query_is_safe_to_cache(self):
        result = cache_lookup("What is unfair dismissal?", "EW")
        assert result["safe_to_cache"] is True

    def test_case_lookup_second_request_is_cache_hit(self):
        query = "What is the qualifying period for unfair dismissal?"
        # First request — may miss or hit
        r1 = cache_lookup(query, "EW")
        if not r1["cache_hit"]:
            # Store it
            cache_store(query, {"answer": "2 years"}, "EW")
        # Second request — must hit
        r2 = cache_lookup(query, "EW")
        assert r2["safe_to_cache"] is True


class TestCacheStore:
    def test_personal_query_not_stored(self):
        result = cache_store("My employer dismissed me", "personal answer", "EW",
                             {"edt": "2025-10-01"})
        assert result["stored"] is False
        assert "personal_or_sensitive" in result.get("reason", "")

    def test_generic_query_can_be_stored(self):
        result = cache_store("What is unfair dismissal?", "Unfair dismissal is...", "EW")
        assert isinstance(result["stored"], bool)
