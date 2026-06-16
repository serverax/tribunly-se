"""lawapp-llm-gateway  -  the ONLY service permitted to call Ollama.

Wraps backend.core.models.LocalInferenceReasoningModel. Rejects raw PII before
inference (detail.error = "pii_rejected") and fails closed (503) when the model is
unavailable  -  never a fallback hallucination. Uses the shared factory for the
mandatory X-Trace-ID middleware + /health + /ready.
"""
from __future__ import annotations

import os
import re

from fastapi import HTTPException
from pydantic import BaseModel

from services._common import create_service
from backend.core.circuit_breaker import CircuitBreaker

app = create_service("lawapp-llm-gateway", needs_db=False)

# Process-local breaker around the external Ollama dependency. After
# LLM_BREAKER_FAIL_MAX consecutive failures it OPENS and requests fail fast for
# LLM_BREAKER_RESET_S, then a single HALF_OPEN trial probes recovery.
_LLM_BREAKER = CircuitBreaker(
    "ollama",
    fail_max=int(os.getenv("LLM_BREAKER_FAIL_MAX", "5")),
    reset_timeout_s=float(os.getenv("LLM_BREAKER_RESET_S", "15")),
)

_PII_FIELD_KEYS = {
    "name", "full_name", "first_name", "last_name", "email", "phone", "mobile",
    "address", "postcode", "ni_number", "national_insurance", "employer_name",
    "dob", "date_of_birth",
}
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\b(?:\+?44|0)\d{9,10}\b")
_NINO = re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]\b", re.I)


class GenerateRequest(BaseModel):
    messages: list
    context: dict | None = None
    max_tokens: int = 512


def _pii_violations(req: GenerateRequest) -> list[str]:
    out = []
    for k in (req.context or {}):
        if k.lower() in _PII_FIELD_KEYS:
            out.append(f"context.{k}")
    blob = " ".join(str(m.get("content", "")) for m in (req.messages or []) if isinstance(m, dict))
    if _EMAIL.search(blob): out.append("email_in_message")
    if _PHONE.search(blob): out.append("phone_in_message")
    if _NINO.search(blob): out.append("ni_number_in_message")
    return out


@app.post("/v1/generate")
def generate(req: GenerateRequest):
    leaked = _pii_violations(req)
    if leaked:
        raise HTTPException(status_code=422, detail={"error": "pii_rejected", "fields": leaked})

    from backend.core.models import LocalInferenceReasoningModel
    from backend.core.circuit_breaker import CircuitOpenError
    from ingestion.config import settings
    base = os.getenv("OLLAMA_BASE_URL") or getattr(settings, "local_inference_url", "")
    model = LocalInferenceReasoningModel(
        base_url=base, model_id=getattr(settings, "local_inference_model", "qwen2.5:3b-instruct-q6_K"))

    def _invoke() -> str:
        out = "".join(model.stream_chat(req.messages, max_tokens=req.max_tokens))
        # Treat an unavailable model as a breaker FAILURE so repeated outages trip
        # the circuit and later calls fail fast instead of stacking up slow waits.
        if not out or out.strip() == "[MODEL_UNAVAILABLE]":
            raise RuntimeError("model_unavailable")
        return out

    try:
        text = _LLM_BREAKER.call(_invoke)
    except CircuitOpenError:
        # External dependency known-bad: fail fast, no piled-up slow calls.
        raise HTTPException(status_code=503, detail="llm_circuit_open_fail_fast")
    except Exception:
        raise HTTPException(status_code=503, detail="llm_unavailable_fail_closed")
    return {"response": text}
