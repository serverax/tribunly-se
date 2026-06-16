"""
/api/free-tool/*  -  the free-tool login wall (acquisition funnel front door).

  POST /api/free-tool/teaser       PUBLIC   -  answer teaser questions, get a
                                             preview + a resume token. State is
                                             saved (encrypted) so nothing is lost.
  POST /api/free-tool/full-result  GATED    -  the full governed result. Anonymous
                                             callers get 401 {login_required}.
  POST /api/free-tool/resume       GATED    -  after login, claim the saved state
                                             and restore answers EXACTLY.

The gate logic lives in backend/core/login_gate.py (single source of truth). The
teaser preview and full result are REAL, grounded outputs (classify + rules
table)  -  no fabricated legal content, no fake success.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from backend.core import login_gate
from backend.core import otel as _otel
from backend.core.user_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/free-tool", tags=["free-tool"])


# ── request models ────────────────────────────────────────────────────────────

class TeaserRequest(BaseModel):
    tool: str = "employment_rights_check"
    answers: dict = {}
    resume_token: Optional[str] = None


class FullResultRequest(BaseModel):
    tool: str = "employment_rights_check"
    answers: dict = {}
    resume_token: Optional[str] = None
    jurisdiction: str = "EW"


class ResumeRequest(BaseModel):
    resume_token: str


# ── helpers ───────────────────────────────────────────────────────────────────

def _narrative(answers: dict) -> str:
    """Best-effort free-text query for the classifier, drawn from the teaser
    answers. Never raises."""
    for key in ("what_happened", "query", "narrative", "description"):
        val = answers.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return " ".join(str(v) for v in answers.values() if isinstance(v, str))


def _classify(answers: dict):
    from backend.core.classify import classify
    return classify(_narrative(answers), answers or {})


def _trace() -> Optional[str]:
    rid = _otel.get_request_id()
    return rid if rid and rid != "-" else None


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/teaser")
def teaser(request: Request, body: TeaserRequest) -> dict:
    """PUBLIC: classify the answers and return a PREVIEW only. Persist the answers
    (encrypted) under a resume token so the user can finish after logging in.

    The preview deliberately withholds the full governed result, the citations,
    documents, timeline, and redaction  -  those are gated."""
    c = _classify(body.answers)

    # Persist the teaser answers (encrypted). Re-uses the caller's resume_token on
    # autosave so repeated keystrokes update one row instead of spawning many.
    token = login_gate.save_teaser_state(
        body.tool, body.answers, resume_token=body.resume_token
    )

    preview = {
        "claim_type": c.matter_type,
        "in_scope": bool(c.in_scope),
        "headline": (
            "Based on what you've told us, this looks like a "
            f"{c.matter_type.replace('_', ' ')} matter."
            if c.in_scope else
            "We may not be able to help with this specific issue yet."
        ),
        # What the full (gated) result unlocks  -  a genuine value preview, not the
        # answer itself.
        "unlocks": [
            "Your full situation assessment with cited authorities",
            "Your exact tribunal deadline and urgency",
            "Your next-step options and document drafts",
        ],
    }

    return {
        "tool": body.tool,
        "login_required": True,
        "resume_token": token,
        "teaser": preview,
        "gated_capabilities": sorted(login_gate.GATED_CAPABILITIES),
        "trace_id": _trace(),
    }


@router.post("/full-result")
def full_result(
    request: Request,
    body: FullResultRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> dict:
    """GATED (full_result): the full grounded result. Anonymous → 401
    {login_required}. If a resume_token is supplied, the saved answers are used so
    nothing the user typed before logging in is lost."""
    user_id = get_current_user(x_user_id, authorization)
    login_gate.require_capability(user_id, "full_result")  # fails closed for anon

    # Restore saved answers across the login boundary (no lost answers). The
    # request body answers override/extend the saved set.
    answers = dict(body.answers or {})
    if body.resume_token:
        claimed = login_gate.claim_teaser_state(body.resume_token, str(user_id))
        merged = dict(claimed["answers"])
        merged.update(answers)
        answers = merged

    c = _classify(answers)
    result: dict = {
        "claim_type": c.matter_type,
        "in_scope": bool(c.in_scope),
        "jurisdiction": body.jurisdiction,
    }

    if not c.in_scope:
        result["status"] = "not_supported"
        result["message"] = "Out of scope for this system  -  no guess."
        result["citations"] = []
    else:
        from backend.core.retrieve import jurisdiction_supported, retrieve_rules
        if not jurisdiction_supported(body.jurisdiction):
            result["status"] = "not_supported"
            result["message"] = f"{body.jurisdiction} employment law is not verified  -  fail closed."
            result["citations"] = []
        else:
            rules = retrieve_rules(c.matter_type, body.jurisdiction, date.today())
            if not rules:
                result["status"] = "insufficient_grounding"
                result["citations"] = []
                result["reason"] = "required rule missing  -  fail closed"
            else:
                result["status"] = "ok"
                result["source"] = "rules_table"
                result["rules"] = rules
                result["citations"] = [
                    {
                        "cite": r.get("authority_ref") or r.get("rule_key"),
                        "rule_key": r.get("rule_key"),
                        "source": "rules_table",
                        "url": r.get("authority_url"),
                    }
                    for r in rules
                ]

    return {
        "tool": body.tool,
        "result": result,
        "answers_used": answers,
        "trace_id": _trace(),
    }


@router.post("/resume")
def resume(
    request: Request,
    body: ResumeRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> dict:
    """GATED: after login, claim the saved teaser state and restore the answers
    EXACTLY where the user stopped. Anonymous → 401 {login_required}; unknown
    token → 404; token owned by another user → 403."""
    user_id = get_current_user(x_user_id, authorization)
    login_gate.require_capability(user_id, "full_result")  # must be logged in

    claimed = login_gate.claim_teaser_state(body.resume_token, str(user_id))
    return {
        "resumed": True,
        "tool": claimed["tool"],
        "answers": claimed["answers"],
        "trace_id": _trace(),
    }
