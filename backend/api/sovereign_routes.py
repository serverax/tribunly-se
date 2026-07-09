"""Sovereign pipeline HTTP routes (Test Cases A/B/C).

  POST /api/v1/lawapp/ingest  -> reverse data flow: narrative -> employment vars
                                 -> user_legal_profiles. 202 Accepted. (Test A)
  POST /api/v1/lawapp/query   -> DB-first SSE: thinking-states + citation-guarded
                                 answer; fail-closed (ESCALATED) on invalid
                                 citation. (Test B / Test C)
"""
from __future__ import annotations

import uuid as _uuid
from typing import Optional

from backend.domains.constants import DEFAULT_JURISDICTION
from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

router = APIRouter(tags=["sovereign"])


class IngestRequest(BaseModel):
    raw_text: str
    user_id: Optional[str] = None
    jurisdiction: str = DEFAULT_JURISDICTION


class QueryRequest(BaseModel):
    raw_text: str
    jurisdiction: str = DEFAULT_JURISDICTION


def _trace_id() -> str:
    return str(_uuid.uuid4())


@router.post("/api/v1/lawapp/ingest")
def ingest(req: IngestRequest):
    """Reverse data flow  -  deterministic extraction written to user_legal_profiles."""
    from backend.core.sovereign.extract import extract_employment_vars, write_user_profile
    trace = _trace_id()
    user_id = req.user_id or str(_uuid.uuid4())
    variables = extract_employment_vars(req.raw_text)
    write_user_profile(user_id, variables, req.jurisdiction)
    return JSONResponse(
        status_code=202,
        content={"trace_id": trace, "user_id": user_id, "pipeline_stage": "EXTRACTING",
                 "extracted": variables},
        headers={"X-Trace-ID": trace},
    )


@router.post("/api/v1/lawapp/query")
def query(req: QueryRequest):
    """DB-first hybrid retrieval, streamed with thinking-states and a hard
    citation-validation circuit breaker (fail-closed)."""
    from backend.core.sovereign.answer import (
        build_answer, passes_wasm_guard, retrieve_cited_chunks,
    )
    trace = _trace_id()

    def _stream():
        yield "data: STAGE:CLASSIFYING_INTENT\n\n"
        yield "data: STAGE:HYBRID_DB_RETRIEVAL\n\n"
        chunks = retrieve_cited_chunks(req.raw_text, req.jurisdiction)
        yield "data: STAGE:LOCAL_INFERENCE_GENERATION\n\n"
        answer, _cited = build_answer(req.raw_text, chunks)
        yield "data: STAGE:WASM_GUARD_VALIDATION\n\n"
        if passes_wasm_guard(answer):
            for line in answer.split("\n"):
                yield f"data: {line}\n\n"
            yield "data: STAGE:COMPLETED\n\n"
        else:
            # Fail-closed: the unverified legal answer is WITHHELD, not streamed.
            yield "data: STAGE:ESCALATED\n\n"
            yield "data: [BLOCKED] Response failed citation validation and was withheld.\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers={"X-Trace-ID": trace})
