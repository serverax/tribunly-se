"""
Append-only audit trail for the lawapp auth stack (auth_events table).

Every auth action records an event. Audit writes use their OWN autocommit
connection so the record is durable even when the surrounding request transaction
rolls back (e.g. a failed login), and a DB hiccup in audit never breaks the auth
request itself (best-effort, logged on failure).

GUARDRAILS:
  * Raw IP addresses are NEVER stored  -  only a salted SHA-256 (ip_hash).
  * Tokens / passwords / secrets are NEVER placed in the detail payload.
  * email_attempted is lower()'d; used only for failed/unknown-user correlation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _ip_salt() -> str:
    # A dedicated salt is preferred; fall back to the signing secret so hashes are
    # never computed under an empty salt.
    return os.getenv("AUTH_IP_HASH_SALT") or os.getenv("JWT_SECRET") or "lawapp-ip-salt"


def hash_ip(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    return hashlib.sha256((_ip_salt() + ":" + ip).encode("utf-8")).hexdigest()


def record_event(
    *,
    event_type: str,
    success: bool,
    user_id: Optional[str] = None,
    email_attempted: Optional[str] = None,
    provider: Optional[str] = None,
    trace_id: Optional[str] = None,
    ip_hash: Optional[str] = None,
    user_agent: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    """Insert one auth_events row. Best-effort: never raises into the caller."""
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auth_events
                        (user_id, email_attempted, event_type, provider, success,
                         trace_id, ip_hash, user_agent, detail)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        user_id,
                        (email_attempted.lower() if email_attempted else None),
                        event_type,
                        provider,
                        success,
                        trace_id,
                        ip_hash,
                        (user_agent or "")[:512] or None,
                        json.dumps(detail or {}),
                    ),
                )
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001  -  audit must never break the request
        logger.warning("auth audit write failed for event=%s (%s)", event_type, type(exc).__name__)
