"""Ingestion Critic  -  Perpetual Law Brain structural/provenance gate.

Validates that a candidate document is a real, official legal instrument with
complete provenance BEFORE it is allowed to be graph-linked, chunked, or embedded.

IMPORTANT: this critic does NOT decide law and does NOT judge legal correctness.
It only validates STRUCTURE and PROVENANCE:
  - host is an official whitelisted legal source,
  - source_url / authority_ref / jurisdiction present (fail closed if missing),
  - the declared parser/format is a known official format (CLML / Akoma Ntoso /
    ACAS official),
  - the text carries a recognised legal citation pattern,
  - the text is NOT opinion/news/blog.

Reject => the document "does not exist" to the system (never ingested).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.core.ingestion.crawler import DOMAIN_WHITELIST, host_of

# Official source formats we accept.
ACCEPTED_PARSERS = {"clml", "akn", "akoma_ntoso", "legaldocml", "acas_official"}
ACCEPTED_SOURCE_TYPES = {"primary_legislation", "secondary_legislation",
                         "case_law", "official_guidance"}
SUPPORTED_JURISDICTIONS = {"EW", "S", "SC", "NI", "GB", "UK"}

# Recognised legal citation shapes (structure only  -  not a correctness judgement).
_CITATION_PATTERNS = [
    re.compile(r"\bs\.?\s?\d+[A-Z]?\b", re.I),                       # s.98 / section
    re.compile(r"\b[A-Z][A-Za-z ]+Act\s+\d{4}\b"),                  # ... Act 1996
    re.compile(r"\[\d{4}\]\s+[A-Z]+\s+\d+"),                        # [2017] UKSC 32
    re.compile(r"\bSI\s+\d{4}/\d+\b"),                              # SI 2014/3199
    re.compile(r"\bCode of Practice\b", re.I),                      # ACAS code
]

# Markers that indicate opinion/news/blog  -  rejected outright.
_NEWS_MARKERS = [
    "comment is free", "opinion", "editorial", "sponsored", "advertisement",
    "blog post", "share this article", "subscribe", "breaking news",
    "our reporter", "click here", "read more stories",
]


@dataclass
class IngestionDoc:
    source_url: str
    source_type: str
    parser_type: str
    jurisdiction_code: str
    authority_ref: str
    content: str
    title: str = ""


@dataclass
class CriticVerdict:
    passed: bool
    reason: str
    checks: dict = field(default_factory=dict)


def _has_citation(text: str) -> bool:
    return any(p.search(text or "") for p in _CITATION_PATTERNS)


def _looks_like_news(text: str) -> bool:
    low = (text or "").lower()
    return any(m in low for m in _NEWS_MARKERS)


class IngestionCritic:
    """Structural/provenance validator. Fail-closed on any missing guarantee."""

    def validate(self, doc: IngestionDoc) -> CriticVerdict:
        checks: dict = {}

        # 1) Provenance: source_url present and on the official whitelist.
        checks["has_source_url"] = bool(doc.source_url)
        on_whitelist = host_of(doc.source_url) in DOMAIN_WHITELIST
        checks["whitelisted_source"] = on_whitelist
        if not doc.source_url:
            return CriticVerdict(False, "missing source_url", checks)
        if not on_whitelist:
            return CriticVerdict(False, f"source not on whitelist: {host_of(doc.source_url)}", checks)

        # 2) Jurisdiction present and supported. A blank/unsupported jurisdiction
        #    must never silently ingest.
        juris_ok = (doc.jurisdiction_code or "").upper() in SUPPORTED_JURISDICTIONS
        checks["jurisdiction_supported"] = juris_ok
        if not juris_ok:
            return CriticVerdict(False, f"unsupported/missing jurisdiction: {doc.jurisdiction_code!r}", checks)

        # 3) Authority reference present (no rule/chunk without authority).
        checks["has_authority_ref"] = bool(doc.authority_ref)
        if not doc.authority_ref:
            return CriticVerdict(False, "missing authority_ref", checks)

        # 4) Declared format must be a known official parser/source type.
        fmt_ok = (doc.parser_type or "").lower() in ACCEPTED_PARSERS
        type_ok = (doc.source_type or "").lower() in ACCEPTED_SOURCE_TYPES
        checks["accepted_parser"] = fmt_ok
        checks["accepted_source_type"] = type_ok
        if not (fmt_ok and type_ok):
            return CriticVerdict(False, f"unsupported format/source_type: {doc.parser_type!r}/{doc.source_type!r}", checks)

        # 5) Opinion/news/blog text is discarded.
        if _looks_like_news(doc.content):
            checks["news_marker"] = True
            return CriticVerdict(False, "content looks like opinion/news/blog", checks)
        checks["news_marker"] = False

        # 6) Must carry a recognised legal citation pattern (structure only).
        cite_ok = _has_citation(doc.content) or _has_citation(doc.authority_ref)
        checks["has_citation_pattern"] = cite_ok
        if not cite_ok:
            return CriticVerdict(False, "no recognised legal citation pattern", checks)

        return CriticVerdict(True, "accepted: official source, complete provenance, legal format", checks)

    def verify(self, doc: IngestionDoc) -> bool:
        """Convenience boolean form."""
        return self.validate(doc).passed
