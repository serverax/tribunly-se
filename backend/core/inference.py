"""Inference module  -  LLM reasoning with governance gates.

Stub implementation for testability. Provides:
- Local Ollama LLM routing (no external provider calls)
- Citation guard enforcement
- Fail-closed behavior on model unavailability
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def prepare_model_request(facts: dict, context: str = "assessment") -> dict:
    """Prepare a redacted, minimal model payload. Never includes raw PII."""
    from backend.core.agentic.corpus_citation_guard import redact_pii

    safe_facts: dict = {}
    sensitive_keys = {
        "claimant_name", "claimant_email", "claimant_phone", "claimant_address",
        "employer_name", "employee_name", "ssn", "national_insurance",
    }
    for key, value in (facts or {}).items():
        if key in sensitive_keys:
            safe_facts[key] = "[REDACTED]"
        elif isinstance(value, str):
            safe_facts[key] = redact_pii(value)
        else:
            safe_facts[key] = value
    return {
        "context": context,
        "payload": safe_facts,
        "pii_redacted": True,
    }


def get_inference_mode() -> str:
    """Return the inference mode: 'ollama' (recommended) or 'disabled'."""
    mode = os.getenv("INFERENCE_MODE", "disabled").lower()
    return mode if mode in ("ollama", "disabled") else "disabled"


def is_ollama_available() -> bool:
    """Check if local Ollama service is available and healthy."""
    mode = get_inference_mode()
    if mode != "ollama":
        logger.debug("is_ollama_available: mode=%s (not ollama)", mode)
        return False

    try:
        import httpx
        ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        resp = httpx.get(f"{ollama_url}/api/tags", timeout=2.0)
        available = resp.status_code == 200
        logger.debug("is_ollama_available: %s", available)
        return available
    except Exception as exc:
        logger.debug("is_ollama_available: check failed: %s", exc)
        return False


def call_ollama_reasoning(
    prompt: str,
    context: str = "",
    model: str = "llama2",
    temperature: float = 0.7,
) -> str:
    """
    Call local Ollama for legal reasoning.

    Args:
        prompt: Main reasoning prompt
        context: Background context (rules, authorities, etc.)
        model: Ollama model name (default: llama2)
        temperature: Sampling temperature (0.0-1.0)

    Returns:
        Model response text (empty string if model unavailable)

    GUARDRAIL: Returns empty string if Ollama is down  -  fails closed, never
               returns fabricated text.
    """
    if not is_ollama_available():
        logger.warning("call_ollama_reasoning: Ollama unavailable  -  returning empty (fail-closed)")
        return ""

    try:
        import httpx
        ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        full_prompt = context + "\n\n" + prompt if context else prompt

        resp = httpx.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": full_prompt,
                "temperature": temperature,
                "stream": False,
            },
            timeout=60.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("response", "")
            logger.debug("call_ollama_reasoning: received %d chars", len(result))
            return result
        else:
            logger.warning("call_ollama_reasoning: Ollama returned %d", resp.status_code)
            return ""

    except Exception as exc:
        logger.warning("call_ollama_reasoning failed: %s (fail-closed)", exc)
        return ""


def call_inference_with_citation_guard(
    prompt: str,
    context: str = "",
    required_corpus_uuids: list[str] | None = None,
) -> dict:
    """
    Call inference with citation guard enforcement.

    If result does not cite required corpus UUIDs, regenerates up to
    max_attempts times, then returns fallback (grounded answer from rules engine).

    Args:
        prompt: Reasoning prompt
        context: Background context
        required_corpus_uuids: UUIDs that must be cited in response

    Returns:
        {
            "status": "accepted" | "fallback",
            "text": response text,
            "cited_uuids": [list of corpus UUIDs cited],
            "attempts": number of attempts,
            "fallback_used": bool,
        }
    """
    logger.debug("call_inference_with_citation_guard: prompt=%d chars", len(prompt or ""))

    max_attempts = 2

    for attempt in range(max_attempts):
        text = call_ollama_reasoning(prompt, context)
        if not text:
            logger.debug("call_inference_with_citation_guard: attempt %d returned empty", attempt + 1)
            continue

        # Extract UUIDs from response
        from backend.core.agentic.corpus_citation_guard import extract_uuids, valid_corpus_uuids
        uuids_in_text = extract_uuids(text)
        valid = valid_corpus_uuids(uuids_in_text)

        if required_corpus_uuids:
            has_required = any(u in valid for u in required_corpus_uuids)
        else:
            has_required = len(valid) > 0

        if has_required:
            logger.debug("call_inference_with_citation_guard: citation guard passed")
            return {
                "status": "accepted",
                "text": text,
                "cited_uuids": sorted(valid),
                "attempts": attempt + 1,
                "fallback_used": False,
            }

        logger.debug("call_inference_with_citation_guard: attempt %d failed citation guard", attempt + 1)

    # All attempts failed citation guard
    logger.warning("call_inference_with_citation_guard: all %d attempts failed citation guard", max_attempts)
    return {
        "status": "fallback",
        "text": "",
        "cited_uuids": [],
        "attempts": max_attempts,
        "fallback_used": True,
        "reason": "inference did not cite required corpus authorities",
    }


def reasoning_disabled_response() -> dict:
    """Return a fail-closed response when inference is disabled."""
    return {
        "status": "fallback",
        "text": "",
        "cited_uuids": [],
        "attempts": 0,
        "fallback_used": True,
        "reason": "inference mode is disabled",
    }
