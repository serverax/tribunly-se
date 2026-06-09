"""Link extracted citations to stored source records — never fabricates.

For each `Citation`, attempt to resolve it to a real row in the local corpus:
  - LEGISLATION  -> legislation (match section number + Act title)
  - NEUTRAL      -> case_law_documents.neutral_citation
  - LAW_REPORT   -> case_law_documents.neutral_citation (best-effort)

On a match, the citation is annotated with the real row id, source_type, and
source_url, and resolved=True. On NO match the citation is left unresolved
(resolved=False, source_id=None). A citation is NEVER assigned a manufactured
id — an unresolved legal reference must surface as unresolved so the caller can
decline to rely on it (constitution §9: unknown citation = unresolved).
"""
from __future__ import annotations

import logging
import re
from typing import Sequence

import psycopg2.extras

from backend.core.citations.extract import Citation, CitationType

logger = logging.getLogger(__name__)


def _resolve_legislation(cur, cit: Citation) -> bool:
    """Match 's 98 Employment Rights Act 1996' to a legislation row."""
    m = re.match(r"(?:s|reg|art|sch|para)\s+(\d+[A-Za-z]*)\s+(.*)$", cit.normalized, re.I)
    if not m:
        return False
    section_num, act = m.group(1), m.group(2).strip()
    if not act:
        return False
    cur.execute(
        """
        SELECT id, source_url
        FROM legislation
        WHERE act_title ILIKE %s
          AND (section_ref = %s OR section_ref ILIKE %s OR section_ref ILIKE %s)
        LIMIT 1
        """,
        (f"%{act}%", section_num, f"%{section_num}%", f"s%{section_num}%"),
    )
    row = cur.fetchone()
    if not row:
        return False
    cit.resolved = True
    cit.source_id = str(row["id"])
    cit.source_type = "legislation"
    cit.source_url = row["source_url"]
    return True


def _resolve_case_law(cur, cit: Citation) -> bool:
    """Match a neutral citation (or law-report) to a case_law_documents row."""
    norm = re.sub(r"\s+", " ", cit.normalized).strip()
    cur.execute(
        """
        SELECT id, fetch_url, neutral_citation
        FROM case_law_documents
        WHERE regexp_replace(lower(neutral_citation), '\\s+', ' ', 'g') = lower(%s)
        LIMIT 1
        """,
        (norm,),
    )
    row = cur.fetchone()
    if not row:
        return False
    cit.resolved = True
    cit.source_id = str(row["id"])
    cit.source_type = "case_law"
    cit.source_url = row["fetch_url"]
    return True


def link_citations(citations: Sequence[Citation], conn=None) -> list[Citation]:
    """Resolve each citation against the corpus. Mutates and returns the list.

    Opens its own DB connection if `conn` is None. A DB error leaves all
    citations unresolved (fail closed) rather than raising — the caller still
    receives the extracted-but-unresolved citations and can act accordingly.
    """
    cits = list(citations)
    if not cits:
        return cits

    own_conn = conn is None
    try:
        if own_conn:
            from ingestion.db import get_connection
            conn = get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for cit in cits:
                try:
                    if cit.type == CitationType.LEGISLATION:
                        _resolve_legislation(cur, cit)
                    elif cit.type in (CitationType.NEUTRAL, CitationType.LAW_REPORT):
                        _resolve_case_law(cur, cit)
                    # EU / US / UNKNOWN: no UK corpus match path -> stay unresolved.
                except Exception as exc:  # noqa: BLE001 - one bad row never fabricates
                    logger.debug("citation link skipped (%s): %s", cit.raw, exc)
    except Exception as exc:  # noqa: BLE001 - DB down -> all unresolved, fail closed
        logger.warning("citation linking unavailable (%s) — all unresolved", exc)
    finally:
        if own_conn and conn is not None:
            conn.close()
    return cits
