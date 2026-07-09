"""
Legal Semantic Cache.

Caches only safe, generic legal explanations.

ALLOWED to cache:
  - "What is unfair dismissal?"
  - "What is ACAS early conciliation?"
  - Public legal glossary entries

NOT ALLOWED to cache:
  - Personal case advice (has user_id or case_id in query)
  - Uploaded document answers
  - Sensitive user facts
  - Settlement strategy
  - Discrimination facts
  - Any query with safe_to_cache=False

GUARDRAIL: Cache is jurisdiction + source_version aware.
           Cache is invalidated when legal sources are updated.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from backend.domains.constants import DEFAULT_JURISDICTION

logger = logging.getLogger(__name__)

# ── Safety classification ─────────────────────────────────────────────────────

_UNSAFE_SIGNALS = [
    "my case", "my employer", "i was dismissed", "i was sacked", "my claim",
    "my situation", "what should i", "am i entitled", "will i win",
    "my dismissal", "my salary", "my contract", "my appeal", "case_id",
    "settlement", "discrimination", "pregnancy", "disability", "whistleblow",
    "grievance", "i have been", "we were", "our company",
]


def _is_safe_to_cache(query: str, facts: Optional[dict] = None) -> bool:
    """True only if the query is generic and contains no personal context."""
    lowered = query.lower()
    if facts and any(facts.get(k) for k in ("edt", "service_start_date", "wages_due_date",
                                             "user_id", "case_id")):
        return False
    for signal in _UNSAFE_SIGNALS:
        if signal in lowered:
            return False
    return True


def _cache_key(query: str, jurisdiction: str, source_version: str) -> str:
    """Deterministic cache key from query + jurisdiction + source version."""
    normalised = " ".join(query.lower().split())
    raw = f"{normalised}|{jurisdiction}|{source_version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ── Source version ────────────────────────────────────────────────────────────

def _get_current_source_version(jurisdiction: str) -> str:
    """Get current source version from DB to ensure cache is not stale."""
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT MAX(last_verified_at) FROM legislation WHERE jurisdiction = %s",
                    (jurisdiction,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    return row[0].strftime("%Y-%m-%d")
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("Source version check failed: %s", exc)
    return "unknown"


# ── Cache operations ──────────────────────────────────────────────────────────

def cache_lookup(
    query: str,
    jurisdiction: str = DEFAULT_JURISDICTION,
    facts: Optional[dict] = None,
) -> dict:
    """
    Look up a query in the semantic cache.

    Returns:
      {"cache_hit": bool, "safe_to_cache": bool, "answer": any | None, "cache_key": str}
    """
    safe = _is_safe_to_cache(query, facts)
    if not safe:
        return {
            "cache_hit": False,
            "safe_to_cache": False,
            "answer": None,
            "cache_key": None,
            "reason": "personal_or_sensitive_query",
        }

    source_version = _get_current_source_version(jurisdiction)
    key = _cache_key(query, jurisdiction, source_version)

    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT answer FROM semantic_cache "
                    "WHERE cache_key = %s AND jurisdiction = %s AND source_version = %s",
                    (key, jurisdiction, source_version),
                )
                row = cur.fetchone()
                if row:
                    answer = row[0]
                    try:
                        answer = json.loads(answer)
                    except (json.JSONDecodeError, TypeError):
                        pass
                    return {
                        "cache_hit": True,
                        "safe_to_cache": True,
                        "answer": answer,
                        "cache_key": key,
                    }
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("Cache lookup failed: %s", exc)

    return {
        "cache_hit": False,
        "safe_to_cache": True,
        "answer": None,
        "cache_key": key,
    }


def cache_store(
    query: str,
    answer: Any,
    jurisdiction: str = DEFAULT_JURISDICTION,
    facts: Optional[dict] = None,
) -> dict:
    """
    Store a query+answer in the semantic cache.

    GUARDRAIL: Only stores if safe_to_cache=True.
    """
    safe = _is_safe_to_cache(query, facts)
    if not safe:
        return {"stored": False, "reason": "personal_or_sensitive_query"}

    source_version = _get_current_source_version(jurisdiction)
    key = _cache_key(query, jurisdiction, source_version)

    serialised = json.dumps(answer) if not isinstance(answer, str) else answer

    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO semantic_cache (cache_key, query_text, answer, jurisdiction, source_version)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE
                      SET answer = EXCLUDED.answer,
                          source_version = EXCLUDED.source_version,
                          updated_at = now()
                    """,
                    (key, query[:500], serialised, jurisdiction, source_version),
                )
                conn.commit()
                return {"stored": True, "cache_key": key, "source_version": source_version}
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("Cache store failed: %s", exc)
        return {"stored": False, "reason": str(exc)}
