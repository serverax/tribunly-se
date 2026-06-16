"""
Replaceable LLM provider plug for Workflow C (founder mandate: LEGAL DB FIRST,
RULES FIRST, CITATIONS FIRST, AI SECOND, FAIL-CLOSED ALWAYS).

The provider is NOT the brain. Workflow C retrieves local law + resolves
deterministic rules + de-identifies facts FIRST, then calls a provider only
through this interface, and the result must still pass the 4 AIA validators
(see ``backend/core/agentic/aia_validators.py``). Providers are swappable:
OpenRouter now, Gemini/local later, with no change to Workflow C logic.

No provider receives raw PII or raw uploaded documents  -  the OpenRouter path
routes through ``litellm_adapter`` whose de-identification chokepoint fails closed.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from backend.core.agentic.errors import AgentOutputError, PolicyViolation


class ProviderUnavailable(PolicyViolation):
    """Raised when the selected provider is not configured/enabled (fail closed)."""


class LLMProvider(ABC):
    name: str = "base"
    cloud: bool = False

    @abstractmethod
    def available(self) -> bool:
        """True only if this provider is configured and enabled."""

    @abstractmethod
    def complete_json(self, *, system_prompt: str, payload: dict,
                      trace_id: str, case_id: str) -> dict:
        """Return a strict JSON object (dict). Must raise on failure (fail closed)."""


class StubProvider(LLMProvider):
    """Deterministic, offline, fail-closed provider. Never invents legal content;
    signals insufficient grounding so the deterministic layer stays in control."""
    name = "stub"
    cloud = False

    def available(self) -> bool:
        return True

    def complete_json(self, *, system_prompt, payload, trace_id, case_id) -> dict:
        return {
            "insufficient_grounding": True,
            "reason": "stub_provider_no_reasoning",
            "note": "Local/stub provider: no external reasoning performed.",
        }


class OpenRouterProvider(LLMProvider):
    """OpenRouter via the single LiteLLM gateway. Enabled only when
    OPENROUTER_ENABLED=true AND a real key is present. The gateway de-identifies
    the payload and fails closed on residual PII before any network call."""
    name = "openrouter"
    cloud = True

    def available(self) -> bool:
        # LOCAL OLLAMA ONLY (hard mandate): OpenRouter is forbidden  -  never available.
        return False

    def complete_json(self, *, system_prompt, payload, trace_id, case_id) -> dict:
        from backend.core.inference_policy import ExternalLLMForbidden
        raise ExternalLLMForbidden(
            "OpenRouterProvider is forbidden  -  lawapp legal routes use local Ollama only."
        )
        if not self.available():                    # noqa: legacy path below unreachable
            raise ProviderUnavailable("OpenRouter is not enabled/configured")
        from backend.core.agentic.litellm_adapter import _pii_chokepoint
        from backend.core.agentic.schemas import strict_json_parse_no_wrappers
        model = os.environ.get("OPENROUTER_MODEL", "").strip()
        if not model:
            raise ProviderUnavailable("OPENROUTER_MODEL is not set")
        timeout = float(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "30") or "30")
        # PII chokepoint BEFORE any provider call (fails closed on residual PII).
        safe_payload = _pii_chokepoint(payload)
        try:
            import litellm
        except Exception as exc:
            raise ProviderUnavailable(f"litellm unavailable: {exc}") from exc
        try:
            import json
            raw = litellm.completion(
                model=f"openrouter/{model}",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(safe_payload, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
                temperature=float(os.environ.get("OPENROUTER_TEMPERATURE", "0") or "0"),
                max_tokens=int(os.environ.get("OPENROUTER_MAX_TOKENS", "1500") or "1500"),
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                api_base=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                timeout=timeout,
                metadata={"trace_id": trace_id, "case_id": case_id, "agent": "workflow_c"},
            )
            content = raw["choices"][0]["message"]["content"]
        except Exception as exc:
            raise AgentOutputError(f"provider call failed (fail closed): {exc}") from exc
        return strict_json_parse_no_wrappers(content)


class GeminiProvider(LLMProvider):
    """Placeholder for a future Gemini plug. Disabled until implemented."""
    name = "gemini"
    cloud = True

    def available(self) -> bool:
        return False

    def complete_json(self, *, system_prompt, payload, trace_id, case_id) -> dict:
        raise ProviderUnavailable("GeminiProvider not implemented yet")


class LocalLLMProvider(LLMProvider):
    """Placeholder for a future local (Ollama/vLLM/GPU) plug. Disabled until built."""
    name = "local"
    cloud = False

    def available(self) -> bool:
        return False

    def complete_json(self, *, system_prompt, payload, trace_id, case_id) -> dict:
        raise ProviderUnavailable("LocalLLMProvider not implemented yet")


_REGISTRY: dict[str, type[LLMProvider]] = {
    "stub": StubProvider,
    "openrouter": OpenRouterProvider,
    "gemini": GeminiProvider,
    "local": LocalLLMProvider,
}


def get_provider(name: str | None = None) -> LLMProvider:
    """Return the active provider. Defaults to OpenRouter when enabled+configured,
    otherwise the deterministic StubProvider (fail-closed, no crash)."""
    if name:
        cls = _REGISTRY.get(name)
        if cls is None:
            raise PolicyViolation(f"unknown provider {name!r}")
        return cls()
    openrouter = OpenRouterProvider()
    return openrouter if openrouter.available() else StubProvider()
