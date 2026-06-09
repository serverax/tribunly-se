"""Extract legal citations from free text — UK-first, US via optional eyecite.

Returns a list of `Citation` objects. Each carries its raw span, a coarse type,
a normalised form, and `resolved=False` until the linker matches it to a stored
source. Nothing here invents a citation: a token that does not match a known
UK pattern (and is not recognised by eyecite, if installed) is simply not
returned, or returned as type=UNKNOWN — never coerced into a fake authority.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CitationType(str, Enum):
    NEUTRAL = "neutral_citation"          # [2021] UKSC 1
    LAW_REPORT = "law_report"             # [2019] ICR 1063
    LEGISLATION = "legislation_section"   # section 98 Employment Rights Act 1996
    EU = "eu_citation"                    # Case C-184/89; [2000] ECR I-1
    US = "us_citation"                    # via eyecite, if present
    UNKNOWN = "unknown"


@dataclass
class Citation:
    raw: str
    type: CitationType
    normalized: str
    start: int
    end: int
    jurisdiction_hint: Optional[str] = None  # "UK"|"EU"|"US"|None
    resolved: bool = False
    source_id: Optional[str] = None          # set ONLY by the linker on a real match
    source_type: Optional[str] = None        # legislation|case_law|acas
    source_url: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "raw": self.raw,
            "type": self.type.value,
            "normalized": self.normalized,
            "start": self.start,
            "end": self.end,
            "jurisdiction_hint": self.jurisdiction_hint,
            "resolved": self.resolved,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_url": self.source_url,
        }


# ── UK neutral citations ─────────────────────────────────────────────────────
# [YYYY] COURT NUMBER, optional division suffix e.g. EWCA Civ, EWHC (Admin).
_UK_COURTS = (
    r"UKSC|UKHL|UKPC|"
    r"EWCA(?:\s+(?:Civ|Crim))?|EWHC(?:\s+\([A-Za-z]+\))?|"
    r"UKEAT|EAT|UKEATPA|UKUT(?:\s+\([A-Za-z]+\))?|UKFTT|"
    r"CSIH|CSOH|HCJ|"            # Scotland
    r"NICA|NIQB|NICh"           # Northern Ireland
)
_NEUTRAL_RE = re.compile(
    r"\[(?P<year>\d{4})\]\s+(?P<court>" + _UK_COURTS + r")\s+(?P<num>\d+)",
    re.I,
)

# ── UK law reports ───────────────────────────────────────────────────────────
# [YYYY] (vol?) SERIES page  e.g. [2019] ICR 1063, [2011] 1 WLR 1, [2004] IRLR 358
_REPORT_SERIES = r"ICR|IRLR|WLR|All\s*ER|QB|AC|Ch|KB|ECR|CMLR|BCLC|FSR|RPC|UKCLR"
_LAW_REPORT_RE = re.compile(
    r"\[(?P<year>\d{4})\]\s+(?P<vol>\d+\s+)?(?P<series>" + _REPORT_SERIES + r")\s+(?P<page>\d+)",
    re.I,
)

# ── UK legislation section references ────────────────────────────────────────
# "section 98 Employment Rights Act 1996", "s.98 ERA 1996", "reg 13 WTR 1998",
# and common Act abbreviations.
_ACT_ABBR = r"ERA|EqA|TULR(?:C)?A|TUPE|WTR|NMWA|PIDA|TICER|ETA|ERelA"
_LEGISLATION_RE = re.compile(
    r"\b(?P<kind>s|section|reg|regulation|art|article|sch|schedule|para|paragraph)\.?\s*"
    r"(?P<num>\d+[A-Z]*)\s*"
    r"(?:(?:of\s+the\s+)?(?P<act>(?:[A-Z][A-Za-z'&]+\s+){1,6}Act\s+\d{4})"
    r"|(?P<abbr>(?:" + _ACT_ABBR + r")\s*\d{4}))",
    re.I,
)

# ── EU citations ─────────────────────────────────────────────────────────────
_EU_CASE_RE = re.compile(r"\bCase\s+[CT]-\d+/\d{2,4}\b", re.I)
_EU_ECR_RE = re.compile(r"\[(?P<year>\d{4})\]\s+ECR\s+I?-?\d+", re.I)


def _add(out: list[Citation], spans: list[tuple[int, int]], cit: Citation) -> bool:
    """Append cit unless its span overlaps an already-claimed span. Returns added?"""
    for s, e in spans:
        if cit.start < e and s < cit.end:
            return False
    out.append(cit)
    spans.append((cit.start, cit.end))
    return True


def extract_citations(text: str, *, use_eyecite: bool = True) -> list[Citation]:
    """Extract citations from `text`. UK patterns take priority and claim their
    spans first; eyecite (if installed and use_eyecite) fills remaining US-style
    reporter citations only. Order of returned list is by position in text.
    """
    from backend.core.citations.normalize import normalize_citation

    if not text:
        return []

    found: list[Citation] = []
    claimed: list[tuple[int, int]] = []

    # 1. UK neutral citations (highest priority — unambiguous court refs)
    for m in _NEUTRAL_RE.finditer(text):
        raw = m.group(0)
        _add(found, claimed, Citation(
            raw=raw, type=CitationType.NEUTRAL,
            normalized=normalize_citation(raw, CitationType.NEUTRAL),
            start=m.start(), end=m.end(), jurisdiction_hint="UK",
        ))

    # 2. UK law reports
    for m in _LAW_REPORT_RE.finditer(text):
        raw = m.group(0)
        _add(found, claimed, Citation(
            raw=raw, type=CitationType.LAW_REPORT,
            normalized=normalize_citation(raw, CitationType.LAW_REPORT),
            start=m.start(), end=m.end(), jurisdiction_hint="UK",
        ))

    # 3. UK legislation sections
    for m in _LEGISLATION_RE.finditer(text):
        raw = m.group(0)
        _add(found, claimed, Citation(
            raw=raw, type=CitationType.LEGISLATION,
            normalized=normalize_citation(raw, CitationType.LEGISLATION),
            start=m.start(), end=m.end(), jurisdiction_hint="UK",
        ))

    # 4. EU citations
    for rex in (_EU_CASE_RE, _EU_ECR_RE):
        for m in rex.finditer(text):
            raw = m.group(0)
            _add(found, claimed, Citation(
                raw=raw, type=CitationType.EU,
                normalized=normalize_citation(raw, CitationType.EU),
                start=m.start(), end=m.end(), jurisdiction_hint="EU",
            ))

    # 5. eyecite for any remaining US-style reporter citations (optional dep).
    #    Failure to import or run eyecite must NEVER break extraction — UK results
    #    are already captured above. We only ADD non-overlapping US citations.
    if use_eyecite:
        for cit in _extract_us_via_eyecite(text):
            _add(found, claimed, cit)

    found.sort(key=lambda c: c.start)
    return found


def _extract_us_via_eyecite(text: str) -> list[Citation]:
    """Best-effort US citation extraction via eyecite. Returns [] if eyecite is
    not installed or errors — fail closed, never raise into the caller."""
    try:
        from eyecite import get_citations  # type: ignore
    except Exception:
        return []
    try:
        out: list[Citation] = []
        for c in get_citations(text):
            try:
                start, end = c.span()
            except Exception:
                start, end = 0, 0
            raw = getattr(c, "matched_text", lambda: "")() or str(c)
            out.append(Citation(
                raw=raw, type=CitationType.US, normalized=raw.strip(),
                start=start, end=end, jurisdiction_hint="US",
            ))
        return out
    except Exception:
        return []


def eyecite_available() -> bool:
    """True if the optional eyecite dependency can be imported."""
    try:
        import eyecite  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False
