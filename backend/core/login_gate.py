"""
Free-tool login gate  -  the login wall for the lawapp acquisition funnel.

PUBLIC (anonymous) capabilities  -  open to everyone:
    browse, teaser, preview.

GATED capabilities  -  require an authenticated user (login wall):
    full_result, upload_document, save_case, timeline, redaction, save_citations.

Anonymous visitors may start a free tool and answer the teaser questions. Those
answers are persisted as ENCRYPTED temporary state (Fernet, ENCRYPTION_KEY) under
a high-entropy *resume token*. Only the SHA-256 hash of that token is stored, so a
DB read alone cannot resume a session. After the visitor logs in, they present the
resume token; the saved answers are restored EXACTLY (no lost answers) and the row
is bound to their user id (a row already claimed by another user is rejected).

GUARDRAILS (constitution §6/§8/§19):
    * require_capability fails CLOSED (401) for anonymous callers on gated actions.
    * temporary state is never stored in plaintext (encryption fail-closed).
    * the raw resume token is never persisted or logged.
    * a claimed state cannot be stolen by a different user.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from typing import Optional

from fastapi import HTTPException

from backend.core import encryption
from ingestion.db import get_connection

logger = logging.getLogger(__name__)

# ── Capability registry ───────────────────────────────────────────────────────
# The brief's contract, encoded once. Routes/services consult this  -  they never
# hardcode their own allow/deny logic.

PUBLIC_CAPABILITIES: frozenset[str] = frozenset({
    "browse",   # land on a page, read static content
    "teaser",   # answer the teaser questions, see a preview
    "preview",  # see the redacted/partial preview of a tool's output
})

GATED_CAPABILITIES: frozenset[str] = frozenset({
    "full_result",     # generate the full governed assessment/result
    "upload_document", # upload evidence documents
    "save_case",       # persist a case
    "timeline",        # access the case timeline
    "redaction",       # use the redaction tool
    "save_citations",  # save/export citations
})


def is_gated(capability: str) -> bool:
    """True if `capability` requires login. Unknown capabilities are treated as
    GATED (fail closed)  -  a new capability is private until explicitly opened."""
    if capability in PUBLIC_CAPABILITIES:
        return False
    return True


def require_capability(user_id: Optional[str], capability: str) -> None:
    """Enforce the login wall.

    Returns None when access is allowed (public capability, or any capability for
    an authenticated user). Raises HTTPException(401) with a structured,
    machine-readable body when an anonymous caller hits a gated capability  -  the
    frontend keys off detail.login_required to show the login wall.
    """
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
                "Please sign in to continue. Your answers are saved  -  you'll pick "
                "up exactly where you left off."
            ),
        },
    )


# ── Resume token ──────────────────────────────────────────────────────────────

def generate_resume_token() -> str:
    """High-entropy, URL-safe opaque token (CSPRNG). Returned to the client once;
    only its hash is stored."""
    return secrets.token_urlsafe(48)


def hash_resume_token(raw_token: str) -> str:
    """SHA-256 hex digest  -  the at-rest representation of a resume token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# ── Encrypted temporary state ─────────────────────────────────────────────────

def _require_encryption() -> None:
    """Fail closed: temporary legal answers must never be stored in plaintext."""
    if not encryption.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Secure temporary storage is unavailable (ENCRYPTION_KEY not set).",
        )


def save_teaser_state(
    tool: str,
    answers: dict,
    *,
    resume_token: Optional[str] = None,
) -> str:
    """Persist (or update) the anonymous teaser answers, encrypted at rest.

    Returns the raw resume token (generate a fresh one if not resuming an existing
    session). The answers are Fernet-encrypted; plaintext is never written.
    """
    _require_encryption()
    if not isinstance(answers, dict):
        raise HTTPException(status_code=422, detail="answers must be an object.")

    token = resume_token or generate_resume_token()
    token_hash = hash_resume_token(token)
    ciphertext = encryption.encrypt_bytes(json.dumps(answers).encode("utf-8"))

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Upsert on the token hash: an autosave (same token) overwrites the
            # encrypted blob and refreshes updated_at, without touching the claim.
            cur.execute(
                """
                INSERT INTO teaser_sessions
                    (resume_token_hash, tool, state_encrypted, encryption_version)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (resume_token_hash) DO UPDATE
                   SET tool               = EXCLUDED.tool,
                       state_encrypted    = EXCLUDED.state_encrypted,
                       encryption_version = EXCLUDED.encryption_version,
                       updated_at         = now()
                """,
                (token_hash, tool, ciphertext, encryption.FERNET_V1),
            )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        logger.error("Teaser state save failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Could not save your answers.")
    finally:
        conn.close()
    return token


def _decrypt_answers(state_encrypted: bytes) -> dict:
    plaintext = encryption.decrypt_bytes(bytes(state_encrypted))
    return json.loads(plaintext.decode("utf-8"))


def load_teaser_state(resume_token: str) -> Optional[dict]:
    """Return the decrypted teaser state for a resume token, or None if unknown.

    Shape: {"tool", "answers", "claimed_by_user_id", "claimed_at"}.
    """
    if not resume_token:
        return None
    _require_encryption()
    token_hash = hash_resume_token(resume_token)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tool, state_encrypted, claimed_by_user_id, claimed_at
                  FROM teaser_sessions
                 WHERE resume_token_hash = %s
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
        "answers": _decrypt_answers(row[1]),
        "claimed_by_user_id": str(row[2]) if row[2] else None,
        "claimed_at": row[3].isoformat() if row[3] else None,
    }


def claim_teaser_state(resume_token: str, user_id: str) -> dict:
    """Bind a saved teaser session to `user_id` (resume-after-login) and return
    its decrypted answers EXACTLY as saved.

      * 404 if the token is unknown (or expired/swept).
      * 403 if the session was already claimed by a DIFFERENT user.
      * idempotent if re-claimed by the SAME user.

    GUARDRAIL: user ids are never logged.
    """
    if not user_id:
        # Defence in depth  -  routes already enforce auth, but never claim anon.
        raise HTTPException(status_code=401, detail="Authentication required to resume.")
    _require_encryption()
    token_hash = hash_resume_token(resume_token)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tool, state_encrypted, claimed_by_user_id
                  FROM teaser_sessions
                 WHERE resume_token_hash = %s
                 FOR UPDATE
                """,
                (token_hash,),
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="No saved session found for this link.")

            existing_owner = str(row[2]) if row[2] else None
            if existing_owner and existing_owner != str(user_id):
                # Already claimed by someone else  -  never hand over another user's
                # answers.
                logger.warning("Teaser claim rejected  -  already owned by another user.")
                raise HTTPException(
                    status_code=403,
                    detail="This saved session belongs to a different account.",
                )

            if existing_owner is None:
                # The claimer is an authenticated user; ensure their row exists
                # before the FK-backed claim (mirrors save_case / onboarding). In
                # production the row already exists; in mock-auth tests it may not.
                from backend.core.user_auth import ensure_user_exists
                ensure_user_exists(conn, str(user_id))
                cur.execute(
                    """
                    UPDATE teaser_sessions
                       SET claimed_by_user_id = %s::uuid,
                           claimed_at         = now(),
                           updated_at         = now()
                     WHERE resume_token_hash  = %s
                    """,
                    (str(user_id), token_hash),
                )
            answers = _decrypt_answers(row[1])
            tool = row[0]
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        logger.error("Teaser claim failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Could not resume your session.")
    finally:
        conn.close()

    return {"tool": tool, "answers": answers}
