"""Central inference policy  -  LOCAL OLLAMA ONLY for lawapp legal routes.

Hard mandate: the only permitted inference backend is the internal Kubernetes
Ollama DaemonSet (CPU). No OpenAI / Anthropic / Gemini / Mistral / Cohere /
Together / Groq / Azure OpenAI / OpenRouter / any hosted inference. No silent
cloud fallback. If Ollama is unavailable, callers must fail closed with
INFERENCE_UNAVAILABLE  -  never a cloud model, never a fabricated answer.

Routing contract (enforced by the brain/orchestrator, grounded here):
    RULES FIRST -> GRAPHRAG SECOND -> LOCAL_OLLAMA LAST RESORT -> CITATION_GUARD
Deterministic legal facts (deadlines, caps, qualifying periods, statutory
thresholds) MUST come from the rules table and MUST NOT call Ollama.
"""
from __future__ import annotations

import os

ALLOWED_BACKEND = "ollama"

# Provider mode strings that select an EXTERNAL/cloud model. If AI_PROVIDER is set
# to any of these, legal routes must refuse to start / refuse to serve.
_EXTERNAL_PROVIDER_MODES = frozenset({
    "openai", "anthropic", "claude", "gemini", "google", "mistral", "cohere",
    "together", "groq", "azure_openai", "azure", "openrouter", "cloud",
    "external", "litellm",
})

# Modes that are local/deterministic and therefore allowed.
_ALLOWED_PROVIDER_MODES = frozenset({"", "local", "ollama", "disabled"})

_DEFAULT_OLLAMA_URL = "http://ollama-inference.lawapp-ai.svc.cluster.local:11434"
_DEFAULT_OLLAMA_MODEL = "qwen2.5:3b-instruct-q6_K"


class ExternalLLMForbidden(RuntimeError):
    """Raised when an external/cloud LLM provider is configured for a legal route."""


class InferenceUnavailable(RuntimeError):
    """Raised when the local Ollama backend cannot be reached. Fail closed  - 
    the system must surface INFERENCE_UNAVAILABLE, never a cloud fallback."""
    code = "INFERENCE_UNAVAILABLE"


def get_allowed_inference_backend() -> str:
    """The only permitted inference backend for legal routes."""
    return ALLOWED_BACKEND


def assert_no_external_llm_enabled() -> None:
    """Fail closed if an external/cloud LLM provider mode is selected.

    Note: the mere PRESENCE of OPENAI_API_KEY / ANTHROPIC_API_KEY does NOT enable
    those providers  -  only an explicit AI_PROVIDER (or LLM_PROVIDER) mode does.
    This function forbids that explicit selection so a stray cloud key can never
    route legal traffic off-box.
    """
    for var in ("AI_PROVIDER", "LLM_PROVIDER", "LAWAPP_LLM_PROVIDER", "EXTERNAL_LLM", "CLOUD_LLM"):
        mode = (os.getenv(var) or "").strip().lower()
        if mode in _EXTERNAL_PROVIDER_MODES:
            raise ExternalLLMForbidden(
                f"External LLM provider '{mode}' (via {var}) is forbidden for lawapp "
                f"legal routes. Only the internal Ollama backend is permitted."
            )
    # OpenRouter is a hosted gateway  -  forbid even if only the legacy flag is on.
    try:
        from ingestion.config import settings
        if bool(getattr(settings, "openrouter_enabled", False)):
            raise ExternalLLMForbidden(
                "openrouter_enabled=true is forbidden: OpenRouter is a hosted "
                "inference gateway. Disable it; use the internal Ollama backend."
            )
    except ImportError:
        pass


def get_ollama_base_url() -> str:
    """Resolve the internal Ollama Service URL (cluster DNS). Never a node IP or
    localhost in production; OLLAMA_BASE_URL env wins for overrides/tests."""
    try:
        from ingestion.config import settings
        cfg = getattr(settings, "local_inference_url", "") or ""
    except ImportError:
        cfg = ""
    return (os.getenv("LAWAPP_OLLAMA_BASE_URL") or os.getenv("OLLAMA_BASE_URL")
            or cfg or _DEFAULT_OLLAMA_URL)


def get_ollama_model() -> str:
    env = os.getenv("LAWAPP_OLLAMA_MODEL") or os.getenv("OLLAMA_MODEL")
    if env:
        return env
    try:
        from ingestion.config import settings
        return getattr(settings, "local_inference_model", "") or _DEFAULT_OLLAMA_MODEL
    except ImportError:
        return _DEFAULT_OLLAMA_MODEL


def require_ollama_local_provider() -> None:
    """Production-startup guard: the legal inference provider MUST be the internal
    Ollama backend. Fails closed unless LAWAPP_LLM_PROVIDER == 'ollama_local'
    (empty is treated as the default local backend; any other value is rejected)."""
    assert_no_external_llm_enabled()
    mode = (os.getenv("LAWAPP_LLM_PROVIDER") or "").strip().lower()
    # Strict: the legal LLM route requires an explicit local provider. Missing or
    # any other value fails closed (no implicit cloud, no implicit anything).
    if mode != "ollama_local":
        raise ExternalLLMForbidden(
            f"LAWAPP_LLM_PROVIDER='{mode or '<unset>'}' is not permitted for the legal "
            f"LLM route. Set LAWAPP_LLM_PROVIDER=ollama_local (internal Ollama only)."
        )


def external_llm_keys_present_redacted() -> dict:
    """Report WHICH external provider keys are present in the environment, REDACTED
    (booleans only  -  never values). Presence is allowed on dev machines but must
    NOT activate any legal route; this exists for transparency/audit only."""
    keys = (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
        "GEMINI_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY", "COHERE_API_KEY",
        "TOGETHER_API_KEY", "GROQ_API_KEY", "AZURE_OPENAI_API_KEY",
    )
    def _present(v: str | None) -> bool:
        return bool(v) and v.strip().lower() not in ("", "placeholder", "changeme", "dummy")
    return {k: _present(os.getenv(k)) for k in keys}


def build_legal_inference_model():
    """Build the ONLY permitted legal reasoning model (local Ollama).

    Enforces no-external first, then constructs LocalInferenceReasoningModel.
    Raises InferenceUnavailable if it cannot be constructed  -  NO cloud fallback.
    Raises ExternalLLMForbidden unless LAWAPP_LLM_PROVIDER=ollama_local.
    """
    require_ollama_local_provider()
    from backend.core.models import LocalInferenceReasoningModel
    try:
        return LocalInferenceReasoningModel(
            base_url=get_ollama_base_url(), model_id=get_ollama_model())
    except Exception as exc:  # construction failure => fail closed
        raise InferenceUnavailable(f"Local Ollama backend unavailable: {exc}") from exc
