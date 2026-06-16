"""UK-aware legal citation extraction, normalisation, and linking.

This package extracts legal citations from free text (user messages, uploaded
briefs, case-law chunks), normalises them to a canonical form, and links them
to stored source records  -  WITHOUT ever fabricating a citation or a source id.

Design boundary (constitution §9):
  - Unknown / unmatched citation => marked unresolved. NEVER invented.
  - eyecite (if installed) is used for US-style reporter citations, but UK
    neutral citations, law reports (ICR/IRLR/WLR), and statute-section
    references are handled by first-class UK regexes here so a US-biased
    extractor can never overwrite or mis-normalise a UK authority.
"""
from backend.core.citations.extract import (
    Citation,
    CitationType,
    extract_citations,
)
from backend.core.citations.normalize import normalize_citation
from backend.core.citations.linker import link_citations

__all__ = [
    "Citation",
    "CitationType",
    "extract_citations",
    "normalize_citation",
    "link_citations",
]
