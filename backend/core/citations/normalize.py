"""Normalise a raw citation string to a canonical, comparable form.

Canonicalisation is purely textual and lossless of meaning  -  it standardises
spacing, court/series casing, and section prefixes so that two spellings of the
same authority compare equal in the linker. It NEVER changes which authority is
referred to (e.g. it will not "correct" s.98 to s.99).
"""
from __future__ import annotations

import re

from backend.core.citations.extract import CitationType

# Canonical court casing (input matched case-insensitively).
_COURT_CANON = {
    "uksc": "UKSC", "ukhl": "UKHL", "ukpc": "UKPC",
    "ewca": "EWCA", "ewca civ": "EWCA Civ", "ewca crim": "EWCA Crim",
    "ewhc": "EWHC", "ukeat": "UKEAT", "eat": "EAT", "ukeatpa": "UKEATPA",
    "ukut": "UKUT", "ukftt": "UKFTT",
    "csih": "CSIH", "csoh": "CSOH", "hcj": "HCJ",
    "nica": "NICA", "niqb": "NIQB", "nich": "NICh",
}
_SERIES_CANON = {
    "icr": "ICR", "irlr": "IRLR", "wlr": "WLR", "all er": "All ER",
    "qb": "QB", "ac": "AC", "ch": "Ch", "kb": "KB", "ecr": "ECR",
    "cmlr": "CMLR", "bclc": "BCLC", "fsr": "FSR", "rpc": "RPC", "ukclr": "UKCLR",
}
_KIND_CANON = {
    "s": "s", "section": "s", "reg": "reg", "regulation": "reg",
    "art": "art", "article": "art", "sch": "sch", "schedule": "sch",
    "para": "para", "paragraph": "para",
}


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def normalize_citation(raw: str, ctype: "CitationType | None" = None) -> str:
    """Return a canonical form of `raw`. If ctype is None, best-effort generic
    whitespace squash is returned."""
    s = _squash(raw)
    if ctype == CitationType.NEUTRAL:
        m = re.match(r"\[(\d{4})\]\s+(.+?)\s+(\d+)$", s)
        if m:
            year, court, num = m.group(1), m.group(2), m.group(3)
            court = _COURT_CANON.get(_squash(court).lower(), court.upper())
            return f"[{year}] {court} {num}"
    elif ctype == CitationType.LAW_REPORT:
        m = re.match(r"\[(\d{4})\]\s+(\d+\s+)?(.+?)\s+(\d+)$", s)
        if m:
            year, vol, series, page = m.group(1), m.group(2) or "", m.group(3), m.group(4)
            series = _SERIES_CANON.get(_squash(series).lower(), series.upper())
            vol = vol.strip()
            return f"[{year}] {vol + ' ' if vol else ''}{series} {page}"
    elif ctype == CitationType.LEGISLATION:
        m = re.match(
            r"(s|section|reg|regulation|art|article|sch|schedule|para|paragraph)\.?\s*"
            r"(\d+[A-Za-z]*)\s*(?:of\s+the\s+)?(.*)$",
            s, re.I,
        )
        if m:
            kind = _KIND_CANON.get(m.group(1).lower(), m.group(1).lower())
            num = m.group(2)
            act = _squash(m.group(3))
            return f"{kind} {num}{(' ' + act) if act else ''}"
    return s
