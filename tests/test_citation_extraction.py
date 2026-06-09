"""Tests for UK-aware citation extraction + normalisation (backend/core/citations).

Extraction/normalisation tests run offline (no DB, no eyecite required). The
linker test is DB-backed and skips cleanly if the corpus is unreachable.
"""
from __future__ import annotations

import pytest

from backend.core.citations.extract import (
    Citation,
    CitationType,
    extract_citations,
    eyecite_available,
)
from backend.core.citations.normalize import normalize_citation


def test_extracts_uk_neutral_citation():
    cits = extract_citations("The leading authority is Uber BV v Aslam [2021] UKSC 1.")
    neutral = [c for c in cits if c.type == CitationType.NEUTRAL]
    assert len(neutral) == 1
    assert neutral[0].normalized == "[2021] UKSC 1"
    assert neutral[0].jurisdiction_hint == "UK"


def test_extracts_eat_and_ewca_citations():
    text = "See [2019] UKEAT 0123 and the appeal [2020] EWCA Civ 456."
    cits = extract_citations(text)
    norms = {c.normalized for c in cits if c.type == CitationType.NEUTRAL}
    assert "[2019] UKEAT 0123" in norms
    assert "[2020] EWCA Civ 456" in norms


def test_extracts_uk_law_report():
    cits = extract_citations("reported at [2004] IRLR 358 and [2011] 1 WLR 1")
    reports = {c.normalized for c in cits if c.type == CitationType.LAW_REPORT}
    assert "[2004] IRLR 358" in reports
    assert "[2011] 1 WLR 1" in reports


def test_extracts_legislation_section_full_and_abbrev():
    text = "Under section 98 of the Employment Rights Act 1996 and s.13 EqA 2010."
    cits = extract_citations(text)
    leg = [c for c in cits if c.type == CitationType.LEGISLATION]
    norms = {c.normalized for c in leg}
    assert any(n.startswith("s 98 Employment Rights Act 1996") for n in norms)
    assert any(n.startswith("s 13 EqA 2010") for n in norms)


def test_unknown_token_is_not_fabricated():
    # A bare phrase with no recognisable citation yields zero citations —
    # nothing is invented.
    cits = extract_citations("the manager was unfair and rude to the claimant")
    assert cits == []


def test_us_citation_only_when_eyecite_present():
    text = "Brown v. Board of Education, 347 U.S. 483 (1954)"
    cits = extract_citations(text)
    us = [c for c in cits if c.type == CitationType.US]
    if eyecite_available():
        assert len(us) >= 1
    else:
        # eyecite absent => US citation simply not extracted (fail closed),
        # and crucially NOT mis-tagged as a UK authority.
        assert us == []
        assert all(c.jurisdiction_hint != "US" for c in cits)


def test_normalize_neutral_casing_and_spacing():
    assert normalize_citation("[2021]   uksc   1", CitationType.NEUTRAL) == "[2021] UKSC 1"
    assert normalize_citation("[2020] ewca civ 456", CitationType.NEUTRAL) == "[2020] EWCA Civ 456"


def test_normalize_section_prefix():
    assert normalize_citation("Section 98 Employment Rights Act 1996",
                              CitationType.LEGISLATION) == "s 98 Employment Rights Act 1996"


def test_citation_as_dict_roundtrip():
    c = Citation(raw="[2021] UKSC 1", type=CitationType.NEUTRAL,
                 normalized="[2021] UKSC 1", start=0, end=13, jurisdiction_hint="UK")
    d = c.as_dict()
    assert d["resolved"] is False
    assert d["source_id"] is None
    assert d["type"] == "neutral_citation"


def test_spans_do_not_overlap():
    cits = extract_citations("s.98 Employment Rights Act 1996 [2021] UKSC 1")
    spans = sorted((c.start, c.end) for c in cits)
    for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
        assert e1 <= s2, "citation spans must not overlap"
