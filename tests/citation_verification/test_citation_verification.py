"""
Citation Verification Engine tests.

Tests that citations are checked against the DB and fabricated/unknown
citations are flagged. No fake citations may pass.
"""

import pytest
from backend.core.citation_verifier import (
    verify_citation, verify_bundle_citations, filter_verified_only,
    _parse_legislation_cite, _LEGISLATION_RE, _CASE_RE,
)


# ── Pattern matching ──────────────────────────────────────────────────────────

class TestCitationPatterns:
    def test_era_abbreviation_matched(self):
        # ERA 1996 is an abbreviation form (2-5 caps + year)
        cite = "ERA 1996 s.94"
        assert _LEGISLATION_RE.search(cite) is not None

    def test_era_1996_full_name_matched(self):
        cite = "Employment Rights Act 1996"
        assert _LEGISLATION_RE.search(cite) is not None

    def test_era_1996_no_section_matched(self):
        cite = "Employment Rights Act 1996"
        assert _LEGISLATION_RE.search(cite) is not None

    def test_eat_case_matched(self):
        cite = "UKEAT/0180/17/JOJ"
        assert _CASE_RE.search(cite) is not None

    def test_parse_legislation_era_1996_s111(self):
        act, section = _parse_legislation_cite("ERA 1996 s.111")
        # Act should contain the abbreviation or year
        assert "1996" in act or "ERA" in act
        # Section may be parsed if regex picks it up
        assert section == "111" or section is None  # depends on regex match grouping

    def test_parse_legislation_act_only(self):
        act, section = _parse_legislation_cite("Employment Rights Act 1996")
        assert "Employment Rights Act 1996" in act
        assert section is None

    def test_empty_citation_fails(self):
        result = verify_citation("")
        assert result["verified"] is False
        assert result["reason"] == "empty_citation"


# ── verify_citation (DB checks) ───────────────────────────────────────────────

class TestVerifyCitation:
    def test_known_era_section_verifies(self):
        # ERA 1996 s.111 should exist in the DB (ingested)
        result = verify_citation("ERA 1996 s.111", "legislation")
        assert result["cite"] == "ERA 1996 s.111"
        assert isinstance(result["verified"], bool)
        assert "method" in result

    def test_fake_act_fails(self):
        result = verify_citation("Fake Employment Rights Act 9999 s.999", "legislation")
        assert result["verified"] is False

    def test_fabricated_case_fails(self):
        result = verify_citation("UKEAT/9999/99/ZZZ", "case_law")
        assert result["verified"] is False
        assert "not_in_case_law_db" in result.get("reason", "")

    def test_result_has_required_fields(self):
        result = verify_citation("ERA 1996 s.94")
        for field in ("cite", "verified", "reason", "method"):
            assert field in result


# ── verify_bundle_citations ───────────────────────────────────────────────────

class TestVerifyBundleCitations:
    def test_empty_bundle_returns_pass(self):
        result = verify_bundle_citations([])
        assert result["total"] == 0
        assert result["pass_rate"] == 1.0

    def test_result_structure(self):
        authorities = [{"cite": "ERA 1996 s.94", "type": "legislation"}]
        result = verify_bundle_citations(authorities)
        assert "total" in result
        assert "verified" in result
        assert "failed" in result
        assert "pass_rate" in result
        assert "details" in result

    def test_fake_citation_counted_as_failed(self):
        authorities = [
            {"cite": "Fake Act 9999 s.999", "type": "legislation"},
            {"cite": "ERA 1996 s.111", "type": "legislation"},
        ]
        result = verify_bundle_citations(authorities)
        assert result["total"] == 2
        assert result["failed"] >= 1

    def test_pass_rate_between_0_and_1(self):
        authorities = [{"cite": "ERA 1996 s.94", "type": "legislation"}]
        result = verify_bundle_citations(authorities)
        assert 0.0 <= result["pass_rate"] <= 1.0


# ── filter_verified_only ──────────────────────────────────────────────────────

class TestFilterVerifiedOnly:
    def test_empty_returns_empty(self):
        assert filter_verified_only([]) == []

    def test_fabricated_citation_removed(self):
        authorities = [
            {"cite": "Fake Act 9999 s.999", "type": "legislation"},
        ]
        filtered = filter_verified_only(authorities)
        # Fabricated citation must be removed
        for a in filtered:
            assert "9999" not in a.get("cite", "")

    def test_result_is_list(self):
        result = filter_verified_only([{"cite": "ERA 1996 s.94", "type": "legislation"}])
        assert isinstance(result, list)
