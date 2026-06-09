"""
Cost Governor — controls per-user and per-feature AI spend.

Position in Brain: called before the AI Router / LLM call (step 14).
Over-quota requests are downgraded or blocked.

Tables: cost_governor_log
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_DAILY_LIMIT = int(os.getenv("COST_GOVERNOR_DAILY_TOKENS", "50000"))
_REQUEST_LIMIT = int(os.getenv("COST_GOVERNOR_REQUEST_TOKENS", "8000"))

_ROUTE_ESTIMATES: dict[str, int] = {
    "full_legal_pipeline":                     4000,
    "full_legal_pipeline_plus_human_review":   5000,
    "rag_plus_rules":                          1000,
    "rules_engine_only":                       200,
    "lite_llm_plus_glossary":                  500,
}


@dataclass
class CostDecision:
    allowed: bool
    route_override: Optional[str]
    estimated_tokens: int
    reason: str
    daily_used: int
    daily_limit: int

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "route_override": self.route_override,
            "estimated_tokens": self.estimated_tokens,
            "reason": self.reason,
            "daily_used": self.daily_used,
            "daily_limit": self.daily_limit,
        }


def check(user_id: Optional[str], route: str, trace_id: Optional[str] = None) -> CostDecision:
    """
    Evaluate whether the requested route is within the user's daily budget.
    Called by Brain before generate_draft step.
    """
    estimated = _ROUTE_ESTIMATES.get(route, 3000)
    daily_used = _get_daily_usage(user_id)

    if daily_used + estimated > _DAILY_LIMIT:
        decision = CostDecision(False, None, estimated, "daily_quota_exceeded", daily_used, _DAILY_LIMIT)
    elif estimated > _REQUEST_LIMIT:
        downgrade = "rag_plus_rules"
        decision = CostDecision(True, downgrade, _ROUTE_ESTIMATES.get(downgrade, 1000),
                                "request_downgraded", daily_used, _DAILY_LIMIT)
    else:
        decision = CostDecision(True, None, estimated, "within_budget", daily_used, _DAILY_LIMIT)

    _write_log(user_id, route, estimated, decision, trace_id)
    if not decision.allowed:
        logger.warning("cost_governor blocked user=%s route=%s used=%d", user_id, route, daily_used)
    elif decision.route_override:
        logger.info("cost_governor downgraded user=%s %s→%s", user_id, route, decision.route_override)
    return decision


def record_usage(user_id: Optional[str], tokens_used: int, trace_id: Optional[str] = None) -> None:
    """Record actual tokens after provider call."""
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE cost_governor_log SET actual_tokens=%s WHERE trace_id=%s",
                    (tokens_used, trace_id),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("cost_governor record_usage skipped: %s", exc)


def _get_daily_usage(user_id: Optional[str]) -> int:
    if not user_id:
        return 0
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(SUM(estimated_tokens),0) FROM cost_governor_log "
                    "WHERE user_id=%s::uuid AND created_at>=CURRENT_DATE",
                    (user_id,),
                )
                row = cur.fetchone()
                return int(row[0]) if row else 0
        finally:
            conn.close()
    except Exception:
        return 0


def _write_log(user_id, route, estimated_tokens, decision: CostDecision, trace_id) -> None:
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cost_governor_log
                        (trace_id,user_id,route,estimated_tokens,daily_used,
                         daily_limit,allowed,route_override,reason)
                    VALUES (%s,%s::uuid,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (trace_id, user_id, route, estimated_tokens,
                     decision.daily_used, decision.daily_limit,
                     decision.allowed, decision.route_override, decision.reason),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("cost_governor_log write skipped: %s", exc)
