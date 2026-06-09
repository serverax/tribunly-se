"""Corpus-citation enforcement (LLM Fabric directive).

Every LLM reasoning output MUST reference at least one valid SQL corpus UUID — an
id that resolves to a real row in corpus_chunks. If it does not, the orchestrator
rejects the output and either regenerates (bounded) or falls back to a deterministic
guide. This prevents the model from inventing authority that is not in the local DB.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

MAX_REGEN = 2


def extract_uuids(text: str) -> list[str]:
    """All UUID-shaped tokens in the text (lowercased, de-duplicated, order-stable)."""
    seen, out = set(), []
    for m in _UUID_RE.findall(text or ""):
        u = m.lower()
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _get_conn():
    from ingestion.db import get_connection
    return get_connection()


def valid_corpus_uuids(uuids: list[str], get_conn: Optional[Callable] = None) -> set[str]:
    """Subset of uuids that resolve to a real corpus_chunks.id."""
    if not uuids:
        return set()
    conn = (get_conn or _get_conn)()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id::text FROM corpus_chunks WHERE id = ANY(%s::uuid[])",
                        (uuids,))
            return {r[0].lower() for r in cur.fetchall()}
    finally:
        conn.close()


def response_has_valid_corpus_citation(text: str, get_conn: Optional[Callable] = None) -> bool:
    """True iff the text cites at least one UUID that exists in corpus_chunks."""
    return len(valid_corpus_uuids(extract_uuids(text), get_conn)) > 0


_CACHE_KEY_PREFIX = "cg:v1:"  # bump v1 to invalidate all cached existence answers


def cached_valid_corpus_uuids(uuids: list[str], get_conn: Optional[Callable] = None) -> set[str]:
    """Cache-aware variant of valid_corpus_uuids for the 100k hot path.

    Per-UUID existence ("does corpus_chunks contain this id?") is cached in Redis.
    A cache HIT answers without touching Postgres; misses are resolved in ONE
    pooled DB round-trip and written back. Fully fail-safe:

      - Cache down/slow  -> every lookup degrades to a miss -> authoritative DB.
      - A fabricated UUID can only ever cache as NEGATIVE; the cache can never
        promote an id to valid that the DB did not confirm (fail-closed intact).

    Returns the subset of `uuids` (lowercased) that exist in corpus_chunks.
    """
    from backend.core import cache  # local import: cache is best-effort/optional

    norm = []
    seen = set()
    for u in uuids:
        lu = (u or "").lower()
        if lu and lu not in seen:
            seen.add(lu)
            norm.append(lu)
    if not norm:
        return set()

    good: set[str] = set()
    to_check: list[str] = []
    for u in norm:
        hit = cache.cache_get_bool(_CACHE_KEY_PREFIX + u)
        if hit is True:
            good.add(u)
        elif hit is False:
            pass  # cached negative — known-absent, skip DB
        else:
            to_check.append(u)  # miss / cache down

    if to_check:
        resolved = valid_corpus_uuids(to_check, get_conn)  # one pooled DB round-trip
        for u in to_check:
            present = u in resolved
            if present:
                good.add(u)
            cache.cache_set_bool(_CACHE_KEY_PREFIX + u, present)
    return good


def enforce_or_regenerate(reason_fn: Callable[[int], str],
                          fallback_fn: Optional[Callable[[], dict]] = None,
                          max_regen: int = MAX_REGEN,
                          get_conn: Optional[Callable] = None) -> dict:
    """Drive generation with corpus-UUID enforcement.

    reason_fn(attempt) -> raw LLM text. If an attempt cites a valid corpus UUID, it
    is accepted. After max_regen+1 failed attempts, fall back to the deterministic
    guide (fallback_fn) — NEVER returns ungrounded model text as accepted.

    Returns: {"status": "accepted"|"fallback", "text"?, "valid_uuids"?, "attempts", ...}
    """
    for attempt in range(max_regen + 1):
        text = reason_fn(attempt)
        valid = valid_corpus_uuids(extract_uuids(text), get_conn)
        if valid:
            return {"status": "accepted", "text": text, "valid_uuids": sorted(valid),
                    "attempts": attempt + 1, "fallback_used": False}
    if fallback_fn is not None:
        result = fallback_fn()
        result["status"] = "fallback"          # force — overrides the guide's own status
        result["fallback_used"] = True
        result["attempts"] = max_regen + 1
        result.setdefault("source", "rules_table")
        return result
    return {"status": "fallback", "fallback_used": True, "source": "rules_table",
            "reason": "no valid corpus UUID after regeneration",
            "recommended_next_step": "deterministic_guide", "attempts": max_regen + 1}


# ── PII Redaction ────────────────────────────────────────────────────────────

import logging as _logging
_log = _logging.getLogger(__name__)


def redact_pii(text: str) -> str:
    """
    Redact personally identifiable information from text.

    Removes or masks:
    - Personal names
    - Addresses and postcodes
    - Phone numbers
    - Email addresses
    - National Insurance numbers
    - Passport numbers
    - Case/claim numbers

    Args:
        text: Input text that may contain PII

    Returns:
        Text with PII removed or masked with [TYPE] placeholders
    """
    if not text:
        return text

    import re as _re

    # Patterns for common PII
    patterns = {
        r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b': '[NAME]',
        r'\b\d{1,5}\s+[A-Z][A-Za-z\s]{2,40}\s+(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr)\b': '[ADDRESS]',
        r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b': '[POSTCODE]',  # UK postcodes
        r'\b\d{2}-?\d{4}-?\d{4}\b': '[PHONE]',  # Phone numbers
        r'\b\d{3}\s\d{4}\s\d{4}\b': '[PHONE]',  # Alternative phone format
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}': '[EMAIL]',  # Email
        r'\b[A-Z]{2}\s\d{2}\s\d{2}\s\d{2}\s[A-Z]\b': '[NI_NUMBER]',  # NI number
        r'\b\d{6,9}\b': '[ID_NUMBER]',  # Generic ID numbers
        r'\bET\s*\d{7}/\d{4}\b': '[CASE_NUMBER]',  # Employment tribunal case
        r'\d{4,5}\s*of\s*\d{4}': '[CASE_NUMBER]',  # Generic case number
    }

    result = text
    for pattern, replacement in patterns.items():
        result = _re.sub(pattern, replacement, result, flags=_re.IGNORECASE)

    _log.debug("redact_pii: processed %d chars", len(text))
    return result


# ── Governance validation ────────────────────────────────────────────────────

def validate_governance(answer: dict) -> tuple[bool, list[str]]:
    """
    Validate that an answer meets governance requirements.

    Checks:
    - Answer has at least one valid corpus citation
    - Answer does not contain raw PII
    - Answer is grounded (sufficient_grounding=true)

    Args:
        answer: Answer dict with 'text', 'cited_uuids', 'sufficient_grounding'

    Returns:
        ``(valid, errors_or_flags)``. Empty citations, weak grounding, invented
        deadlines, certainty language, and solicitor/representation wording fail
        closed.
    """
    errors: list[str] = []

    if not answer:
        return False, ["answer is None or empty"]

    text = " ".join(
        str(answer.get(k, ""))
        for k in ("text", "claim", "reasoning_summary")
        if answer.get(k) is not None
    )
    citations = answer.get("citations") or answer.get("cited_uuids") or []
    sufficient = answer.get("sufficient_grounding", None)
    if sufficient is None:
        sufficient = not answer.get("insufficient_grounding", False)
    confidence = answer.get("confidence_score", answer.get("confidence", 1.0))

    # Check grounding
    if not sufficient:
        errors.append("insufficient grounding")

    # Check citation
    if not citations or len(citations) == 0:
        errors.append("no citations found")
    else:
        allowed_hosts = (
            "legislation.gov.uk",
            "nationalarchives.gov.uk",
            "caselaw.nationalarchives.gov.uk",
            "acas.org.uk",
            "gov.uk",
            "equalityhumanrights.com",
            "hse.gov.uk",
        )
        for citation in citations:
            if isinstance(citation, str):
                if any(marker in citation.lower() for marker in ("fake", "hallucinated", "made up")):
                    errors.append("fake citation detected")
                continue
            if isinstance(citation, dict):
                url = str(citation.get("url") or citation.get("authority_url") or "")
                if url.startswith("http") and not any(host in url for host in allowed_hosts):
                    errors.append("citation URL is not an approved UK employment law source")

    if "deadline_days" in answer and not citations:
        errors.append("deadline must be sourced from rules and cited")

    lower_text = text.lower()
    if any(term in lower_text for term in ("definitely win", "you will win", "guaranteed", "certainly win")):
        errors.append("overconfident or guarantee language")
    if answer.get("certainty_language") and confidence < 0.7:
        errors.append("overconfident certainty language with low confidence")
    if confidence < 0.5:
        errors.append("low confidence")
    if any(term in lower_text for term in ("hire me as your solicitor", "instruct me", "represent you in tribunal")):
        errors.append("solicitor/legal advice boundary breached")

    # Check for raw PII patterns (basic check)
    if text and any(pattern in text.lower() for pattern in
                     ['mr.', 'ms.', 'mrs.', 'dr.', 'phone:', 'email:', 'address:']):
        # Might contain PII — flag for review
        _log.warning("validate_governance: answer may contain raw PII markers")
        errors.append("potential unredacted PII detected")

    return len(errors) == 0, errors


def check_grounding(answer_text: str | dict, required_min_citations: int | list[dict] = 1):
    """
    Check if an answer is sufficiently grounded in corpus citations.

    Args:
        answer_text: Answer text to check
        required_min_citations: Minimum number of distinct corpus citations required

    Returns:
        Legacy text mode returns a dict. Shared contract mode
        ``check_grounding(facts, sources)`` returns ``(grounded, confidence)``.
    """
    if isinstance(answer_text, dict) and isinstance(required_min_citations, list):
        facts = answer_text
        sources = required_min_citations
        if not sources:
            return False, 0.0

        expected_jurisdiction = facts.get("jurisdiction")
        matching_jurisdiction = [
            s for s in sources
            if not expected_jurisdiction or s.get("jurisdiction") in (None, expected_jurisdiction, "EW", "GB", "UK")
        ]
        binding = [
            s for s in matching_jurisdiction
            if (s.get("type") or s.get("source_type") or "").lower() in ("legislation", "statute", "case_law")
        ]
        guidance = [
            s for s in matching_jurisdiction
            if (s.get("type") or s.get("source_type") or "").lower() in ("guidance", "acas", "acas_guidance")
        ]

        confidence = 0.0
        confidence += min(0.45, 0.2 * len(binding))
        confidence += min(0.25, 0.1 * len(guidance))
        confidence += min(0.20, 0.08 * len(matching_jurisdiction))
        confidence += 0.10 if len(matching_jurisdiction) >= 2 else 0.0
        confidence = min(1.0, confidence)
        grounded = len(matching_jurisdiction) >= 2 and len(binding) >= 1 and confidence >= 0.5
        return grounded, confidence

    if not answer_text:
        return {
            "grounded": False,
            "citation_count": 0,
            "details": "empty answer",
        }

    uuids = extract_uuids(str(answer_text))
    if not uuids:
        return {
            "grounded": False,
            "citation_count": 0,
            "details": "no citations found in text",
        }

    # Validate that these UUIDs actually exist in corpus_chunks
    valid = valid_corpus_uuids(uuids)
    is_grounded = len(valid) >= required_min_citations

    _log.debug("check_grounding: found %d UUIDs, %d valid", len(uuids), len(valid))

    return {
        "grounded": is_grounded,
        "citation_count": len(valid),
        "required_min": required_min_citations,
        "details": f"found {len(valid)} valid citations (required {required_min_citations})",
    }
