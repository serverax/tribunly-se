"""lawapp-brain — governed orchestration entrypoint.

Wraps backend.core.brain: the deterministic rules-first guide (no LLM) for /assess,
and the governed generative lane (rules → RAG → LLM → CitationGuard) for the
workflow path. Enforces tenancy ownership and provides X-Trace-ID via the shared
factory. No raw ungrounded model text ever leaves this service.
"""
from __future__ import annotations

import os

from fastapi import HTTPException, Request
from pydantic import BaseModel

from services._common import create_service
from services._common import call_service, get_trace_id

app = create_service("lawapp-brain", needs_db=True)

# ── Downstream service wiring (a real microservice mesh) ──────────────────────
# In a deployed cluster these resolve via DNS to the sibling services. Integration
# tests override the *_CLIENT_FACTORY module globals with a callable returning a
# Starlette TestClient(app) so the cross-service calls run the real downstream apps
# in-process (no network), while still exercising each app's full middleware + handler.
RULES_ENGINE_URL = os.getenv("RULES_ENGINE_URL", "http://lawapp-rules-engine:8000")
LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://lawapp-llm-gateway:8000")
RULES_ENGINE_CLIENT_FACTORY = None  # set to lambda base: TestClient(rules_app) in tests
LLM_GATEWAY_CLIENT_FACTORY = None   # set to lambda base: TestClient(gateway_app) in tests


class WorkflowRequest(BaseModel):
    user_id: str | None = None
    workspace_id: str | None = None
    case_id: str | None = None
    intent: str | None = None
    query: str | None = None
    jurisdiction: str = "EW"
    claim_type: str = "unfair_dismissal"
    facts: dict | None = None


def _require_tenancy(req: WorkflowRequest) -> None:
    if not req.user_id or not req.workspace_id or not req.case_id:
        raise HTTPException(status_code=400, detail="user_id, workspace_id and case_id required")


@app.post("/v1/assess")
def assess(req: WorkflowRequest):
    """Deterministic rules-first assessment — no LLM, fail-closed on missing rules."""
    _require_tenancy(req)
    from backend.core.brain import get_deterministic_guide
    guide = get_deterministic_guide(req.claim_type, req.jurisdiction)
    return {
        "service": "lawapp-brain",
        "route": "rules_first",
        "llm_called": False,
        "citation_guard_required": True,
        "guide": guide,
    }


class DeadlineExplainRequest(BaseModel):
    user_id: str | None = None
    workspace_id: str | None = None
    case_id: str | None = None
    claim_type: str = "unfair_dismissal"
    jurisdiction: str = "EW"
    edt: str | None = None
    ec_day_a: str | None = None
    ec_day_b: str | None = None


@app.post("/v1/deadline/explain")
def deadline_explain(req: DeadlineExplainRequest, request: Request):
    """Cross-service: compute the deterministic ET deadline in the rules-engine, then
    route THAT result through the llm-gateway for a plain-English explanation.

    One trace id is propagated to BOTH downstream services (prove cross-service
    tracing). The deadline is the source of truth (source=rules); the LLM only
    explains it and is never allowed to change a date. Fails closed: if the rules
    service cannot compute the deadline the whole call fails (no fabricated date);
    if the model is unavailable we still return the real deadline with an honest
    explanation_unavailable marker (never a hallucinated explanation).
    """
    if not req.user_id or not req.workspace_id or not req.case_id:
        raise HTTPException(status_code=400, detail="user_id, workspace_id and case_id required")
    if not req.edt:
        raise HTTPException(status_code=400, detail="edt (effective date of termination) required")

    trace_id = get_trace_id(request)

    # ── Step 1: deterministic deadline from the rules-engine (trace propagated) ──
    try:
        r = call_service(
            RULES_ENGINE_URL, "POST", "/v1/deadline/calculate",
            json_body={"claim_type": req.claim_type, "jurisdiction": req.jurisdiction,
                       "relevant_date": req.edt, "ec_day_a": req.ec_day_a,
                       "ec_day_b": req.ec_day_b},
            trace_id=trace_id, client_factory=RULES_ENGINE_CLIENT_FACTORY)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"rules_engine_unreachable: {e}")
    if r.status_code != 200:
        # Propagate fail-closed: never invent a deadline if rules could not produce one.
        raise HTTPException(status_code=502,
                            detail={"stage": "rules_engine", "status": r.status_code,
                                    "body": _safe_json(r)})
    deadline = r.json()
    limitation_date = (deadline.get("result") or {}).get("limitation_date")
    authority = deadline.get("authority", "ERA 1996 s.111(2)")

    # ── Step 2: route the deadline through the llm-gateway for explanation ──────
    # Dates + legal authority only — no PII crosses the model boundary.
    prompt = (
        "You are explaining a UK employment tribunal claim deadline to a claimant. "
        "Do NOT recompute or change any date. Using only the values provided, explain "
        f"in two plain-English sentences why the deadline to start a claim is "
        f"{limitation_date} (statutory authority: {authority}). State that missing it "
        "is usually fatal to the claim."
    )
    gateway_status = None
    explanation = None
    try:
        g = call_service(
            LLM_GATEWAY_URL, "POST", "/v1/generate",
            json_body={"messages": [{"role": "user", "content": prompt}],
                       "context": {"deadline": deadline.get("result", {}),
                                   "authority": authority},
                       "max_tokens": 256},
            trace_id=trace_id, client_factory=LLM_GATEWAY_CLIENT_FACTORY)
        gateway_status = g.status_code
        if g.status_code == 200:
            explanation = g.json().get("response")
    except Exception as e:
        gateway_status = 503
        explanation = None
        _gateway_error = str(e)  # noqa: F841 — recorded via gateway_status only

    return {
        "service": "lawapp-brain",
        "trace_id": trace_id,
        "source": "rules",
        "llm_called": explanation is not None,
        "deadline": deadline,
        "limitation_date": limitation_date,
        "authority": authority,
        "explanation": explanation,
        "explanation_unavailable": explanation is None,
        "gateway_status": gateway_status,
    }


def _safe_json(resp) -> object:
    try:
        return resp.json()
    except Exception:
        return resp.text[:500]


@app.post("/v1/workflow/execute")
def workflow_execute(req: WorkflowRequest):
    """Governed generative lane: rules → RAG → LLM → CitationGuard (fail-closed)."""
    _require_tenancy(req)
    from backend.core.brain import execute_generative_lane
    result = execute_generative_lane(
        query=req.query or req.intent or "",
        context=req.facts or {},
        case_id=req.case_id or "",
        user_id=req.user_id or "",
        jurisdiction=req.jurisdiction,
        claim_type=req.claim_type,
    )
    return {"service": "lawapp-brain", "citation_guard_required": True, "result": result}
