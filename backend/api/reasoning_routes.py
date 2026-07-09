"""Path-Splitter HTTP routes (ADR: Deterministic vs Generative Routing).

  POST /reasoning/route   -> returns the lane decision (no work done).
  POST /reasoning/stream  -> FACTUAL: deterministic rules JSON (<400ms budget, no LLM).
                             REASONING: text/event-stream of model tokens (SSE).

Safety:
  - the FACTUAL lane never invokes the LLM (rules table only),
  - the REASONING lane de-identifies facts before the model sees them and is gated
    behind LOCAL_INFERENCE_ENABLED; the streamed text is an analysis PREVIEW  -  the
    authoritative, Critic-gated assessment remains the /assess pipeline.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from backend.domains.constants import DEFAULT_JURISDICTION
from backend.core.path_splitter import (
    FAST_DETERMINISTIC, route as split_route, sse_frames,
)

router = APIRouter(tags=["reasoning"])

_SYSTEM = (
    "You are a UK employment-law analysis engine. Use ONLY the provided context. "
    "If the answer is not in the provided context, say the law is unclear or no local "
    "precedent exists. Do not reference news, blogs, or internet opinion."
)


class ReasonRequest(BaseModel):
    query: str
    facts: Optional[dict] = None
    jurisdiction: str = DEFAULT_JURISDICTION


def _local_enabled() -> bool:
    if os.getenv("LOCAL_INFERENCE_ENABLED", "").lower() in ("1", "true", "yes"):
        return True
    try:
        from ingestion.config import settings
        return bool(getattr(settings, "local_inference_enabled", False))
    except Exception:
        return False


def _base_url() -> str:
    try:
        from ingestion.config import settings
        default = getattr(settings, "local_inference_url", "")
    except Exception:
        default = ""
    return os.getenv("OLLAMA_BASE_URL") or default or \
        "http://llm-inference-service.lawapp-ai.svc.cluster.local:11434"


@router.post("/reasoning/route")
def reasoning_route(req: ReasonRequest):
    d = split_route(req.query, req.facts)
    return {"intent": d.intent, "lane": d.lane, "reason": d.reason,
            "invokes_llm": d.invokes_llm}


def _serve_factual(req: ReasonRequest):
    """Deterministic fast path: rules-table lookup, no LLM, strict 400ms budget."""
    import concurrent.futures
    import time
    from datetime import date

    t0 = time.monotonic()

    def work():
        from backend.core.classify import classify
        from backend.core.retrieve import retrieve_rules
        c = classify(req.query, req.facts or {})
        claim = getattr(c, "matter_type", None) or "unfair_dismissal"
        rules = retrieve_rules(claim, req.jurisdiction, date.today())
        return claim, rules

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            claim, rules = ex.submit(work).result(timeout=0.4)  # strict <400ms
    except concurrent.futures.TimeoutError:
        return JSONResponse(status_code=200, content={
            "lane": FAST_DETERMINISTIC, "intent": "FACTUAL", "invokes_llm": False,
            "status": "deterministic_timeout_exceeded_400ms",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"deterministic lookup failed: {exc}")

    return {
        "lane": FAST_DETERMINISTIC, "intent": "FACTUAL", "invokes_llm": False,
        "claim_type": claim, "source": "rules_table",
        "rules": rules, "latency_ms": round((time.monotonic() - t0) * 1000, 1),
    }


@router.post("/reasoning/stream")
def reasoning_stream(req: ReasonRequest):
    decision = split_route(req.query, req.facts)
    if decision.lane == FAST_DETERMINISTIC:
        return _serve_factual(req)

    # REASONING lane  -  SSE stream of model tokens.
    if not _local_enabled():
        raise HTTPException(status_code=503,
                            detail="reasoning streaming disabled (LOCAL_INFERENCE_ENABLED is off)")
    # De-identify before anything reaches the model.
    try:
        from backend.core.deidentify import deidentify
        safe_facts, _ = deidentify(req.facts or {})
    except Exception:
        safe_facts = {}

    from backend.core.brain import execute_generative_lane
    from backend.core.models import LocalInferenceReasoningModel
    model = LocalInferenceReasoningModel(base_url=_base_url())
    user_content = f"Question: {req.query}\n\nDe-identified context: {safe_facts}"
    messages = [{"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_content}]
    # Institutionalised CitationGuard (LLM Fabric directive): the stream emits ONLY
    # governed output  -  accepted corpus-cited text, or the deterministic rules guide.
    # Raw, ungoverned model tokens never reach the client.
    governed = execute_generative_lane(req.query, messages=messages, model=model,
                                       jurisdiction=req.jurisdiction)
    if governed.get("status") == "accepted":
        payload = governed.get("text", "")
    else:
        payload = governed.get("message", "Deterministic guide (rules table).")
    return StreamingResponse(sse_frames(iter([payload])), media_type="text/event-stream")
