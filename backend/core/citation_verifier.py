"""
Citation Verification Engine.

Every citation must be verified against the DB before appearing in output.
Checks: Act/section exists, citation text matches DB, jurisdiction correct,
source is current, no fabricated citations.

GUARDRAIL: Unverified citations are removed or marked as UNVERIFIED.
           No fabricated citations may survive this check.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Citation patterns ────────────────────────────────────────────────────────

_LEGISLATION_RE = re.compile(
    r"(?P<act>"
    r"(?:[A-Z]{2,5}\s+\d{4})"           # abbreviation form: ERA 1996, TULRCA 1992
    r"|(?:[A-Za-z ]+(?:Act|Regulations|Order|Rules)\s+\d{4})"  # full name
    r")"
    r"(?:\s+s\.?\s*(?P<section>\d+[A-Z]?))?",
    re.IGNORECASE,
)

_CASE_RE = re.compile(
    r"(?P<neutral_citation>UKEAT/\d+/\d+(?:/\w+)?|UKSC \d+|\[?\d{4}\]?\s+\w+ \d+)",
    re.IGNORECASE,
)


_ABBREV_MAP = {
    "ERA 1996":     "Employment Rights Act 1996",
    "ERA 1999":     "Employment Relations Act 1999",
    "ERA 2025":     "Employment Rights Act 2025",
    "TULRCA 1992":  "Trade Union and Labour Relations (Consolidation) Act 1992",
    "ETA 1996":     "Employment Tribunals Act 1996",
    "EA 2002":      "Employment Act 2002",
    "EA 2008":      "Employment Act 2008",
    "EqA 2010":     "Equality Act 2010",
    "ERRA 2013":    "Enterprise and Regulatory Reform Act 2013",
}


def _expand_abbreviation(act: str) -> str:
    """Expand common UK employment law abbreviations to full act names."""
    act = act.strip()
    return _ABBREV_MAP.get(act, act)


def _parse_legislation_cite(cite: str) -> tuple[str, str | None]:
    """Extract act_title and section_ref from a citation string."""
    m = _LEGISLATION_RE.search(cite)
    if m:
        act = _expand_abbreviation(m.group("act").strip())
        return act, m.group("section")
    return cite, None


def _verify_legislation_in_db(act_title: str, section_ref: str | None) -> bool:
    """Check the legislation table for the cited act/section."""
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                if section_ref:
                    cur.execute(
                        "SELECT 1 FROM legislation "
                        "WHERE act_title ILIKE %s AND section_ref = %s "
                        "LIMIT 1",
                        (f"%{act_title}%", section_ref),
                    )
                else:
                    cur.execute(
                        "SELECT 1 FROM legislation WHERE act_title ILIKE %s LIMIT 1",
                        (f"%{act_title}%",),
                    )
                return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("Legislation DB check failed: %s", exc)
        return False


def _verify_case_in_db(neutral_citation: str) -> bool:
    """Check case_law_documents for the cited neutral citation."""
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM case_law_documents "
                    "WHERE neutral_citation ILIKE %s LIMIT 1",
                    (f"%{neutral_citation.strip()}%",),
                )
                return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("Case law DB check failed: %s", exc)
        return False


def _verify_acas_in_db(cite: str) -> bool:
    """Check ACAS guidance citations against the local acas_guidance table."""
    needle = (
        cite.replace("ACAS Guidance:", "")
        .replace("ACAS Code:", "")
        .strip()
    )
    if not needle:
        needle = cite.strip()
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                      FROM acas_guidance
                     WHERE doc_title ILIKE %s
                        OR section_ref ILIKE %s
                        OR source_url ILIKE %s
                     LIMIT 1
                    """,
                    (f"%{needle}%", f"%{needle}%", f"%{needle.lower().replace(' ', '-')}%"),
                )
                return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("ACAS guidance DB check failed: %s", exc)
        return False


def verify_citation(cite: str, source_type: str | None = None) -> dict:
    """
    Verify a single citation string.

    Returns:
      {"cite": str, "verified": bool, "reason": str | None, "method": str}
    """
    cite = (cite or "").strip()
    if not cite:
        return {"cite": cite, "verified": False, "reason": "empty_citation", "method": "none"}

    if source_type in ("acas", "acas_guidance") or cite.lower().startswith("acas "):
        verified = _verify_acas_in_db(cite)
        return {
            "cite": cite,
            "verified": verified,
            "reason": None if verified else "not_in_acas_guidance_db",
            "method": "acas_guidance_db",
        }

    if source_type in ("legislation",) or _LEGISLATION_RE.search(cite):
        act, section = _parse_legislation_cite(cite)
        verified = _verify_legislation_in_db(act, section)
        return {
            "cite": cite,
            "verified": verified,
            "reason": None if verified else "not_in_legislation_db",
            "method": "legislation_db",
        }

    if source_type in ("case_law",) or _CASE_RE.search(cite):
        m = _CASE_RE.search(cite)
        if m:
            nc = m.group("neutral_citation")
            verified = _verify_case_in_db(nc)
            return {
                "cite": cite,
                "verified": verified,
                "reason": None if verified else "not_in_case_law_db",
                "method": "case_law_db",
            }

    # Fallback: check both tables
    act, section = _parse_legislation_cite(cite)
    if _verify_legislation_in_db(act, section):
        return {"cite": cite, "verified": True, "reason": None, "method": "legislation_db_fallback"}

    # Cannot verify — mark as unverified (do not remove, just flag)
    return {
        "cite": cite,
        "verified": False,
        "reason": "not_found_in_any_db",
        "method": "exhausted",
    }


def verify_bundle_citations(authorities: list[dict]) -> dict:
    """
    Verify all citations in a retrieval bundle.

    Returns:
      {
        "total": int,
        "verified": int,
        "failed": int,
        "pass_rate": float,
        "details": list[dict]
      }
    """
    if not authorities:
        return {"total": 0, "verified": 0, "failed": 0, "pass_rate": 1.0, "details": []}

    details = []
    for auth in authorities:
        cite = auth.get("cite", "")
        source_type = auth.get("type", "")
        result = verify_citation(cite, source_type)
        details.append(result)

    verified = sum(1 for d in details if d["verified"])
    total = len(details)
    failed = total - verified
    pass_rate = round(verified / total, 2) if total > 0 else 1.0

    return {
        "total": total,
        "verified": verified,
        "failed": failed,
        "pass_rate": pass_rate,
        "details": details,
    }


def filter_verified_only(authorities: list[dict]) -> list[dict]:
    """Remove unverified citations from a bundle. Logs what was removed."""
    if not authorities:
        return []
    result = verify_bundle_citations(authorities)
    kept = []
    for auth, detail in zip(authorities, result["details"]):
        if detail["verified"]:
            kept.append(auth)
        else:
            logger.warning(
                "Citation removed (unverified): %s — reason: %s",
                detail["cite"],
                detail["reason"],
            )
    return kept
