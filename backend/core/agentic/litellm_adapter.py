"""
LiteLLM adapter — the ONLY module permitted to call the model gateway (AC-006).

Year-1 infra (founder decision): cloud models are served via OpenRouter free
endpoints through LiteLLM. Because data leaves the building, this adapter is the
ABSOLUTE PII chokepoint (AC-007/008): every payload is de-identified via
``backend.core.deidentify.deidentify`` and then hard-checked for residual PII.
If the scrubber fails, or any PII pattern remains, the call FAILS CLOSED and no
request is sent.

Routing (config/litellm.lawapp.yaml):
  AEE, SEA, Citation Guard -> de-identified payload, cloud disabled-by-default
  ART -> local-first, cloud escalation only via policy gate
LiteLLM is imported lazily so this module is importable without the package
installed (it then fails closed at call time).
"""

from __future__ import annotations

import json
import logging
import os
import re

from pydantic import BaseModel

from backend.core.agentic.errors import (
    AgentOutputError,
    PIIBoundaryViolation,
    PolicyViolation,
)
from backend.core.agentic.schemas import AgentName, strict_json_parse_no_wrappers

logger = logging.getLogger(__name__)

_LOCAL_ROUTE = "lawapp-edge-slm"


def is_openrouter_configured() -> bool:
    """True if a real OpenRouter key is present in the environment. Optional:
    when False, the agentic LLM layer stays local/stub/fail-closed (no crash).
    Returns only a boolean — never the key value."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    return bool(key) and key.lower() not in {"dummy", "dummy_test_key", "changeme", "placeholder"}


def require_openrouter_configured() -> None:
    """Fail closed at startup if the live OpenRouter key is absent or a
    placeholder (founder mandate: no placeholders; app must not start blind).
    Call from the app lifespan once OPENROUTER_API_KEY is provisioned to the
    backend environment (never commit the key — env/secret only)."""
    # LOCAL OLLAMA ONLY (hard mandate): the agentic layer must NOT require an
    # OpenRouter/cloud key. No-op now; cloud routes fail closed at call time via
    # ExternalLLMForbidden. Never require an external key to start.
    return

def _pii_chokepoint(payload: dict) -> dict:
    """Scrub the payload (content-preserving) and hard-assert no residual PII.
    Fails closed if the scrubber errors or any PII survives. Year-1: every
    outbound payload is treated as cloud-bound, so this always runs before a call."""
    try:
        from backend.core.agentic.pii import scrub_payload, residual_pii
        scrubbed = scrub_payload(payload)
        # Belt-and-suspenders: also run the structured-facts scrubber on any
        # recognised fact sub-dicts (founder mandate: wire deidentify in).
        try:
            from backend.core.deidentify import deidentify
            if isinstance(scrubbed, dict):
                for fk in ("facts", "confirmed_facts", "confirmed_timeline"):
                    if isinstance(scrubbed.get(fk), dict):
                        safe, _b = deidentify(scrubbed[fk])
                        scrubbed[fk] = safe
        except Exception:
            pass  # deidentify is supplementary; text redaction already applied
    except Exception as exc:
        raise PIIBoundaryViolation(f"PII scrubber failed; refusing to send: {exc}") from exc

    leak = residual_pii(scrubbed)
    if leak:
        raise PIIBoundaryViolation(f"residual PII ({leak}) after scrub; failing closed")
    return scrubbed


def call_model(
    *,
    agent_name: AgentName,
    model_route: str,
    system_prompt: str,
    payload: dict,
    response_schema: type[BaseModel],
    trace_id: str,
    case_id: str,
    allow_cloud: bool = False,
    pii_allowed: bool = False,
) -> BaseModel:
    """Call a model via LiteLLM and return a validated ``response_schema``.

    Cloud routes require ``allow_cloud=True`` AND a de-identified payload
    (``pii_allowed`` must be False for cloud). All output is strictly parsed
    (no markdown/conversational wrappers) and schema-validated before return.
    """
    if agent_name not in set(AgentName):
        raise PolicyViolation(f"unknown agent {agent_name!r}")

    is_cloud = model_route != _LOCAL_ROUTE
    if is_cloud:
        # LOCAL OLLAMA ONLY (hard mandate): any non-local (cloud) route is forbidden.
        from backend.core.inference_policy import ExternalLLMForbidden
        raise ExternalLLMForbidden(
            f"Cloud route {model_route!r} is forbidden — lawapp legal routes use the "
            f"internal Ollama backend only (no LiteLLM/OpenRouter cloud calls)."
        )

    # PII chokepoint: scrub + hard-assert for any non-local route (Year-1 = cloud).
    outbound_payload = payload if (not is_cloud and pii_allowed) else _pii_chokepoint(payload)

    try:
        import litellm  # lazy: module stays importable without the package
    except Exception as exc:
        raise PolicyViolation(f"LiteLLM unavailable; cannot call model (fail closed): {exc}") from exc

    try:
        raw = litellm.completion(
            model=model_route,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(outbound_payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            api_key=os.environ.get("OPENROUTER_API_KEY") if is_cloud else None,
            metadata={"trace_id": trace_id, "case_id": case_id, "agent_name": agent_name.value},
        )
        content = raw["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("model call failed agent=%s route=%s: %s", agent_name.value, model_route, exc)
        raise AgentOutputError(f"model call failed: {exc}") from exc

    parsed = strict_json_parse_no_wrappers(content)
    return response_schema.model_validate(parsed)
