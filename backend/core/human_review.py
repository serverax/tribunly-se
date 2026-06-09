"""
Human Review Queue — routes high-risk legal cases to human review.

Position in Brain: triggered after urgency/risk classification (step 6).
High-risk cases are queued; user receives a safe caveated response immediately.

Triggers:
- urgency=critical or expired
- claim_type=discrimination, whistleblowing, settlement_agreement
- missing_facts count >= 3
- evaluation_passed=False

Tables: human_review_queue
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_HIGH_RISK_CLAIM_TYPES = {"discrimination", "whistleblowing", "settlement_agreement"}
_HIGH_RISK_URGENCY = {"critical", "expired"}
_MISSING_FACTS_THRESHOLD = 3


def should_queue(
    claim_type: Optional[str],
    urgency: Optional[str],
    missing_facts: list,
    evaluation_passed: Optional[bool] = None,
) -> tuple[bool, str]:
    """Return (queue: bool, reason: str)."""
    if urgency in _HIGH_RISK_URGENCY:
        return True, f"urgency_{urgency}"
    if claim_type in _HIGH_RISK_CLAIM_TYPES:
        return True, f"claim_type_{claim_type}"
    if len(missing_facts) >= _MISSING_FACTS_THRESHOLD:
        return True, f"missing_facts_{len(missing_facts)}"
    if evaluation_passed is False:
        return True, "evaluation_failed"
    return False, "not_high_risk"


def queue_case(
    trace_id: str,
    user_id: Optional[str],
    case_id: Optional[str],
    claim_type: Optional[str],
    urgency: Optional[str],
    reason: str,
    missing_facts: list,
) -> Optional[str]:
    """
    Insert a human_review_queue record.
    Returns review row id on success, None on failure.
    Caller must still return a caveated response to the user.
    """
    try:
        import json
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO human_review_queue
                        (trace_id,user_id,case_id,claim_type,urgency,
                         trigger_reason,missing_facts_summary,status)
                    VALUES (%s,%s::uuid,%s::uuid,%s,%s,%s,%s,'pending')
                    ON CONFLICT (trace_id) DO NOTHING
                    RETURNING id
                    """,
                    (trace_id, user_id, case_id, claim_type, urgency,
                     reason, json.dumps(missing_facts[:10])),
                )
                row = cur.fetchone()
                review_id = str(row[0]) if row else None
            conn.commit()
            if review_id:
                logger.info("human_review queued review=%s trace=%s reason=%s",
                            review_id, trace_id, reason)
            return review_id
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("human_review queue write failed: %s", exc)
        return None


_CAVEATS: dict[str, str] = {
    "urgency_critical":
        "Your tribunal deadline is very close. This case has been flagged for priority review. "
        "Please contact ACAS immediately and seek qualified legal advice without delay.",
    "urgency_expired":
        "Your tribunal deadline may have passed. A qualified solicitor may advise on "
        "whether an extension is possible under exceptional circumstances.",
    "claim_type_discrimination":
        "Discrimination claims involve protected-characteristic law. "
        "This case has been flagged for specialist review. "
        "We recommend consulting a qualified employment solicitor.",
    "claim_type_whistleblowing":
        "Whistleblowing claims involve specific legal protections. "
        "This case has been flagged for specialist review.",
    "claim_type_settlement_agreement":
        "You must obtain independent legal advice from a qualified solicitor "
        "before signing any settlement agreement.",
    "evaluation_failed":
        "This assessment could not be completed to the required standard. "
        "Your case has been flagged for review. We recommend seeking qualified legal advice.",
}

_DEFAULT_CAVEAT = (
    "This case has been flagged for specialist human review. "
    "For urgent matters, please seek qualified legal advice immediately."
)


def get_safe_caveat(reason: str) -> str:
    return _CAVEATS.get(reason, _DEFAULT_CAVEAT)
