"""
Free-tool login gate  -  the login wall for the lawapp acquisition funnel.

PUBLIC (anonymous) capabilities  -  open to everyone:
    browse, teaser, preview.

GATED capabilities  -  require an authenticated user (login wall):
    full_result, upload_document, save_case, timeline, redaction, save_citations.

Owner decision 2026-06-16 (Feature §5 #8): anonymous flows do NOT persist
special-category case facts. Only non-sensitive funnel signals are recorded
(tool, coarse outcome, timestamp) under legitimate interest.

After login, users re-enter gated tools; anonymous teaser answers are not restored.

GUARDRAILS (constitution §6/§8/§19):
    * require_capability fails CLOSED (401) for anonymous callers on gated actions.
    * no plaintext or encrypted storage of anonymous special-category answers.
    * agent registry and gated tools carry auth and audit.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Optional

from fastapi import HTTPException

from ingestion.db import get_connection

logger = logging.getLogger(__name__)

PUBLIC_CAPABILITIES: frozenset[str] = frozenset({
    "browse",
    "teaser",
    "preview",
})

GATED_CAPABILITIES: frozenset[str] = frozenset({
    "full_result",
    "upload_document",
    "save_case",
    "timeline",
    "redaction",
    "save_citations",
})


def is_gated(capability: str) -> bool:
    if capability in PUBLIC_CAPABILITIES:
        return False
    return True


def require_capability(user_id: Optional[str], capability: str) -> None:
    if not is_gated(capability):
        return None
    if user_id:
        return None
    raise HTTPException(
        status_code=401,
        detail={
            "login_required": True,
            "capability": capability,
            "message": (
                "Please sign in to continue. For your privacy we do not store "
                "anonymous case details; sign in to save your matter securely."
            ),
        },
    )


def generate_resume_token() -> str:
    return secrets.token_urlsafe(48)


def hash_resume_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _coarse_outcome(answers: dict) -> str:
    if not isinstance(answers, dict):
        return "unknown"
    for key in ("coarse_outcome", "outcome", "step"):
        val = answers.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:64]
    if answers:
        return "in_progress"
    return "started"


def save_teaser_state(
    tool: str,
    answers: dict,
    *,
    resume_token: Optional[str] = None,
) -> str:
    """Record a non-sensitive funnel signal only. Does NOT persist case facts."""
    if not isinstance(answers, dict):
        raise HTTPException(status_code=422, detail="answers must be an object.")

    token = resume_token or generate_resume_token()
    coarse = _coarse_outcome(answers)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO funnel_signals (tool, coarse_outcome, session_id)
                VALUES (%s, %s, %s)
                """,
                (tool, coarse, hash_resume_token(token)),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("Funnel signal save failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Could not record funnel signal.")
    finally:
        conn.close()
    return token


def load_teaser_state(resume_token: str) -> Optional[dict]:
    """Anonymous case answers are not persisted. Returns tool metadata only."""
    if not resume_token:
        return None
    token_hash = hash_resume_token(resume_token)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tool, coarse_outcome, created_at
                  FROM funnel_signals
                 WHERE session_id = %s
                 ORDER BY created_at DESC
                 LIMIT 1
                """,
                (token_hash,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return {
        "tool": row[0],
        "answers": {},
        "coarse_outcome": row[1],
        "claimed_by_user_id": None,
        "claimed_at": None,
        "answers_not_stored": True,
    }


def claim_teaser_state(resume_token: str, user_id: str) -> dict:
    """Bind funnel session to user without restoring anonymous special-category data."""
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required to resume.")
    loaded = load_teaser_state(resume_token)
    if loaded is None:
        raise HTTPException(status_code=404, detail="No saved session found for this link.")
    return {"tool": loaded["tool"], "answers": {}, "answers_not_stored": True}
