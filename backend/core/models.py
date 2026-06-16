"""
Reasoning model interface and stub.

GUARDRAIL (model selection): the workhorse model has NOT been chosen yet  - 
that is a deliberate bake-off decision (01_BUILD_PLAN.md §0). Do not default
to any specific model here. The interface is defined so the rest of the pipeline
can be built and tested without a live model call.

StubReasoningModel: returns a valid, honest assessment that exercises the full
pipeline (including governance gate) without any model call. Used for unit tests
and pipeline wiring verification. It returns insufficient_grounding=True because
it has no real reasoning to offer  -  this is the correct and honest result.

ClaudeReasoningModel: wired but requires explicit model_id at construction.
Will not instantiate without it. Implement once the bake-off is complete.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from shared.schemas import (
    Citation, Deadline, RetrievalBundle, StructuredAssessment, ValueRange,
)

logger = logging.getLogger(__name__)


class ReasoningModel(ABC):
    """Interface all reasoning models must implement."""

    @abstractmethod
    def reason(
        self,
        safe_facts: dict,           # de-identified facts (PII already stripped)
        bundle: RetrievalBundle,
        deadline_info: dict,        # pre-computed from rules  -  model must not alter
        boundary_log: dict,         # de-identification audit record
    ) -> StructuredAssessment:
        """
        Apply retrieved law to user facts and produce a structured assessment.

        GUARDRAIL: safe_facts must have been through deidentify() before this
        call. The caller is responsible. boundary_log proves it happened.
        The deadline values in deadline_info come from the rules table and are
        injected into the assessment  -  the model explains them, never re-derives.
        """
        ...

    @abstractmethod
    def get_boundary_payload(self) -> Optional[dict]:
        """
        Return the last payload sent to any external API (for compliance proof).
        Returns None if no external call was made (e.g. stub).
        """
        ...


class StubReasoningModel(ReasoningModel):
    """
    Pipeline-test stub. No model call. Returns honest insufficient_grounding.

    Use this to:
    - Test the full pipeline chain end-to-end without model costs.
    - Verify that the governance gate correctly handles insufficient_grounding.
    - Confirm the de-identification boundary is enforced before this is called.

    Returns insufficient_grounding=True because it has no actual reasoning.
    The governance gate will route this to seek_solicitor  -  correct behaviour.
    """

    def reason(
        self,
        safe_facts: dict,
        bundle: RetrievalBundle,
        deadline_info: dict,
        boundary_log: dict,
    ) -> StructuredAssessment:
        logger.info("StubReasoningModel.reason called  -  no external API call made")

        # Derive deadline from the pre-computed deadline_info (never from model)
        deadline = Deadline(
            limitation_date=date.fromisoformat(deadline_info["limitation_date"])
            if deadline_info.get("limitation_date") else None,
            source="rules",
            authority=deadline_info.get("authority", "ERA 1996 s.111(2)"),
        )

        # Extract cap from rules bundle if available
        cap_rule = next(
            (r for r in bundle.exact_rules
             if r["rule_key"] == "unfair_dismissal.compensatory_cap_amount"),
            None,
        )
        value_range = ValueRange(
            low=0,
            high=float(cap_rule["value_numeric"]) if cap_rule and cap_rule.get("value_numeric") else 0,
            currency="GBP",
            basis="from rules  -  model reasoning not yet configured",
        )

        return StructuredAssessment(
            claim_type="unfair_dismissal",
            jurisdiction=safe_facts.get("jurisdiction", "EW"),
            has_viable_claim="uncertain",
            strength="uncertain",
            reasoning_summary=(
                "Stub model  -  reasoning engine not yet configured. "
                "Rules data retrieved successfully. Cite your legal adviser."
            ),
            value_range=value_range,
            key_weaknesses=["Reasoning model not yet configured  -  assessment is incomplete."],
            deadline=deadline,
            recommended_next_step="seek_solicitor",
            citations=[],
            grounding_score=0.0,
            confidence_score=0.0,
            insufficient_grounding=True,
        )

    def get_boundary_payload(self) -> Optional[dict]:
        return None  # No external call made by stub


class ClaudeReasoningModel(ReasoningModel):
    """
    Real reasoning implementation using the Anthropic API.

    REQUIRES: explicit model_id  -  do not hardcode a default.
    Model selection is a deliberate bake-off decision (Phase 2, post-embeddings).
    Construct only after the workhorse model has been chosen and tested.

    De-identification: the caller MUST pass safe_facts (PII stripped) and the
    boundary_log proving deidentify() was called. This class asserts it.
    """

    def __init__(self, model_id: str, api_key: str) -> None:
        # LOCAL OLLAMA ONLY (hard mandate): the Anthropic/Claude cloud provider is
        # forbidden for lawapp legal routes. This class is retained for type/imports
        # but fails closed on construction so it can never serve a legal request.
        from backend.core.inference_policy import ExternalLLMForbidden
        raise ExternalLLMForbidden(
            "ClaudeReasoningModel (Anthropic cloud) is forbidden  -  lawapp uses the "
            "internal Ollama backend only."
        )

    _SYSTEM_PROMPT = """You are a legal assessment engine for UK unfair dismissal claims.
You receive ONLY retrieved legal authority and de-identified user facts.
You must produce a structured JSON assessment matching the exact schema provided.
You must not generate, recall, or re-derive any deadline, cap, or threshold  - 
these are provided in deadline_info and rules and must be used verbatim.
You must cite every legal claim to a specific retrieved authority.
When a LEGAL RELATIONSHIP MAP is provided, prioritise its nodes and relationships
(statute -> test -> limitation -> remedy) over isolated vector-search snippets: it
encodes the verified structure of the law, not just lexical similarity.
If the retrieved bundle is insufficient to support a claim, set insufficient_grounding=true.
Never fabricate authority. Never overstate strength. Surface weaknesses honestly."""

    def _build_prompt(
        self, safe_facts: dict, bundle: RetrievalBundle, deadline_info: dict
    ) -> str:
        relationship_map = safe_facts.get("_legal_relationship_map", "")
        relationship_block = (
            f"\nLEGAL RELATIONSHIP MAP (verified graph  -  PRIORITISE over isolated "
            f"snippets below):\n{relationship_map}\n" if relationship_map else ""
        )
        return f"""Assess the following unfair dismissal matter.
{relationship_block}
RETRIEVED RULES (use verbatim  -  do not alter these values):
{json.dumps(bundle.exact_rules, indent=2, default=str)}

RETRIEVED AUTHORITIES:
{json.dumps(bundle.authorities, indent=2)}

DEADLINE (pre-computed from rules  -  use verbatim, source must remain "rules"):
{json.dumps(deadline_info, indent=2, default=str)}

DE-IDENTIFIED FACTS:
{json.dumps(safe_facts, indent=2, default=str)}

Produce a structured assessment as JSON matching this schema exactly:
{{
  "claim_type": "unfair_dismissal",
  "jurisdiction": "EW",
  "has_viable_claim": "yes|no|uncertain",
  "strength": "low|medium|high|uncertain",
  "reasoning_summary": "<= 150 words plain English, no jargon>",
  "value_range": {{"low": 0, "high": 0, "currency": "GBP", "basis": "..."}},
  "key_weaknesses": ["..."],
  "deadline": {{"limitation_date": "YYYY-MM-DD", "source": "rules", "authority": "..."}},
  "recommended_next_step": "free_diagnosis_only|prepare_documents|seek_solicitor",
  "citations": [{{"cite": "...", "url": "..."}}],
  "grounding_score": 0.0,
  "confidence_score": 0.0,
  "insufficient_grounding": false
}}

Return ONLY the JSON object. No prose before or after."""

    def reason(
        self,
        safe_facts: dict,
        bundle: RetrievalBundle,
        deadline_info: dict,
        boundary_log: dict,
    ) -> StructuredAssessment:
        import anthropic

        # Assert de-identification happened
        if not boundary_log:
            raise RuntimeError(
                "boundary_log is empty  -  deidentify() must be called before reason(). "
                "Raw personal facts must never reach this method."
            )

        prompt = self._build_prompt(safe_facts, bundle, deadline_info)
        self._last_payload = {
            "model": self._model_id,
            "system": self._SYSTEM_PROMPT,
            "user_prompt_length": len(prompt),
            "safe_facts_keys": list(safe_facts.keys()),
            "boundary_log": boundary_log,
            # NOT logging prompt text to avoid any edge-case PII in the log itself
        }

        client = anthropic.Anthropic(api_key=self._api_key)
        response = client.messages.create(
            model=self._model_id,
            max_tokens=2048,
            system=self._SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        # Sanitisation interceptor (fail-closed): strip code fences, extract the
        # outermost JSON object, and never let raw prose crash json.loads with a 500.
        try:
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            _a, _b = raw.find("{"), raw.rfind("}")
            if _a != -1 and _b > _a:
                raw = raw[_a:_b + 1]
            data = json.loads(raw)
        except Exception as exc:
            logger.warning("Claude output not valid JSON  -  failing closed: %s", exc)
            return StructuredAssessment(
                claim_type="unfair_dismissal",
                jurisdiction=safe_facts.get("jurisdiction", "EW"),
                has_viable_claim="uncertain", strength="uncertain",
                reasoning_summary="Model output could not be safely parsed  -  insufficient grounding.",
                value_range=ValueRange(low=0, high=0, currency="GBP", basis="unparseable model output"),
                key_weaknesses=["Model output unparseable (failed closed). Seek legal advice."],
                deadline=Deadline(limitation_date=None, source="rules", authority="ERA 1996 s.111(2)"),
                recommended_next_step="seek_solicitor", citations=[],
                grounding_score=0.0, confidence_score=0.0, insufficient_grounding=True,
            )

        # Enforce deadline.source = "rules"  -  governance gate also checks this,
        # but we fix it here defensively so the model cannot override it.
        if "deadline" in data:
            data["deadline"]["source"] = "rules"

        return StructuredAssessment(**data)

    def get_boundary_payload(self) -> Optional[dict]:
        return self._last_payload


class OpenRouterReasoningModel(ReasoningModel):
    """
    Optional reasoning provider via OpenRouter (openai-compatible API).

    DISABLED BY DEFAULT (OPENROUTER_ENABLED=false in config).
    Must be explicitly enabled. De-identification MUST run before every call.
    Governance MUST run after every response.

    OpenRouter receives ONLY:
      - de-identified safe_facts (no PII)
      - retrieved authority bundle (rules + BM25)
      - structured task instruction + required JSON schema

    It returns a structured assessment DRAFT. The governance gate validates it
    before any output reaches the user.

    Timeout: if OpenRouter is unavailable, returns insufficient_grounding with
    flag MODEL_UNAVAILABLE  -  never crashes the engine.
    """

    BASE_URL = "https://openrouter.ai/api/v1"
    TIMEOUT_SECONDS = 30

    def __init__(self, model_id: str, api_key: str) -> None:
        # LOCAL OLLAMA ONLY (hard mandate): OpenRouter is a hosted gateway and is
        # forbidden for lawapp legal routes. Retained for imports; fails closed.
        from backend.core.inference_policy import ExternalLLMForbidden
        raise ExternalLLMForbidden(
            "OpenRouterReasoningModel (hosted gateway) is forbidden  -  lawapp uses the "
            "internal Ollama backend only."
        )

    _SYSTEM = (
        "You are a structured legal assessment engine for UK unfair dismissal claims. "
        "You receive ONLY de-identified facts and retrieved legal authority. "
        "You return ONLY the structured JSON assessment. "
        "You must cite every legal claim to a retrieved source. "
        "If grounding is insufficient, set insufficient_grounding=true. "
        "Never fabricate authority. Never guarantee outcomes. Surface weaknesses honestly."
    )

    def reason(
        self,
        safe_facts: dict,
        bundle,
        deadline_info: dict,
        boundary_log: dict,
    ) -> "StructuredAssessment":
        import httpx

        if not boundary_log:
            raise RuntimeError(
                "boundary_log is empty  -  deidentify() must be called before "
                "OpenRouterReasoningModel.reason(). Raw personal facts must never reach this method."
            )

        prompt = (
            f"Assess the following unfair dismissal matter.\n\n"
            f"RETRIEVED RULES (verbatim  -  do not alter):\n{json.dumps(bundle.exact_rules, indent=2, default=str)}\n\n"
            f"RETRIEVED AUTHORITIES:\n{json.dumps(bundle.authorities, indent=2)}\n\n"
            f"DEADLINE (pre-computed from rules  -  source must remain 'rules'):\n"
            f"{json.dumps(deadline_info, indent=2, default=str)}\n\n"
            f"DE-IDENTIFIED FACTS:\n{json.dumps(safe_facts, indent=2, default=str)}\n\n"
            "Return ONLY valid JSON matching the structured assessment schema. No prose."
        )

        self._last_payload = {
            "model":            self._model_id,
            "provider":         "openrouter",
            "safe_facts_keys":  list(safe_facts.keys()),
            "boundary_log":     boundary_log,
            "prompt_length":    len(prompt),
        }

        try:
            resp = httpx.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "https://github.com/serverax/lawapp",
                    "X-Title":       "lawapp-uk-employment",
                },
                json={
                    "model": self._model_id,
                    "messages": [
                        {"role": "system", "content": self._SYSTEM},
                        {"role": "user",   "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens":  2048,
                },
                timeout=self.TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("OpenRouter unavailable: %s  -  returning MODEL_UNAVAILABLE", exc)
            return StructuredAssessment(
                claim_type="unfair_dismissal",
                jurisdiction=safe_facts.get("jurisdiction", "EW"),
                has_viable_claim="uncertain",
                strength="uncertain",
                reasoning_summary="Model unavailable  -  insufficient grounding.",
                value_range=ValueRange(low=0, high=0, currency="GBP", basis="model unavailable"),
                key_weaknesses=["Model unavailable (MODEL_UNAVAILABLE). Seek legal advice."],
                deadline=Deadline(
                    limitation_date=None,
                    source="rules",
                    authority="ERA 1996 s.111(2)",
                ),
                recommended_next_step="seek_solicitor",
                citations=[],
                grounding_score=0.0,
                confidence_score=0.0,
                insufficient_grounding=True,
            )

        raw = resp.json()["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        data = json.loads(raw)
        if "deadline" in data:
            data["deadline"]["source"] = "rules"  # defensive enforcement

        return StructuredAssessment(**data)

    def get_boundary_payload(self) -> Optional[dict]:
        return self._last_payload


class LocalInferenceReasoningModel(ReasoningModel):
    """
    Local Inference Fabric provider  -  reasons against the in-cluster llama.cpp
    DaemonSet (Qwen2.5-3B-Instruct, GGUF Q6_K) via its OpenAI-compatible API.

    No cloud APIs, no per-token cost: the model runs on lawapp's own metal. The
    backend reaches the inference instance on its OWN node (the Service uses
    internalTrafficPolicy: Local), so there are no cross-node hops.

    Guardrails identical to every other provider:
      - de-identification MUST have run (boundary_log asserted),
      - deadlines/caps come from the rules table, never the model
        (deadline.source is force-set to "rules"),
      - the Critic Agent verifies citations against the local DB afterwards.

    FAIL-SOFT: if the node-local inference pod is unreachable (e.g. not yet Ready),
    this returns a MODEL_UNAVAILABLE / insufficient_grounding assessment rather
    than crashing the Mother Algorithm. The governance gate handles it safely.
    """

    TIMEOUT_SECONDS = 60  # CPU inference on a 3B model is slower than a GPU/cloud call

    _SYSTEM = (
        "You are a structured legal assessment engine for UK unfair dismissal claims. "
        "You receive ONLY de-identified facts and retrieved legal authority. "
        "When a LEGAL RELATIONSHIP MAP is provided, prioritise its nodes and "
        "relationships over isolated snippets. "
        "You return ONLY the structured JSON assessment  -  no prose. "
        "You must cite every legal claim to a retrieved source. "
        "You must NOT invent, recall, or alter any deadline, cap, or threshold; use "
        "the provided rules verbatim. If grounding is insufficient, set "
        "insufficient_grounding=true. Never fabricate authority."
    )

    def __init__(self, base_url: str, model_id: str = "qwen2.5-3b-instruct") -> None:
        if not base_url:
            raise ValueError("LocalInferenceReasoningModel requires a base_url")
        self._base_url = base_url.rstrip("/")
        self._model_id = model_id
        self._last_payload: Optional[dict] = None

    def reason(
        self,
        safe_facts: dict,
        bundle,
        deadline_info: dict,
        boundary_log: dict,
    ) -> "StructuredAssessment":
        import httpx

        if not boundary_log:
            raise RuntimeError(
                "boundary_log is empty  -  deidentify() must be called before "
                "LocalInferenceReasoningModel.reason(). Raw personal facts must "
                "never reach this method."
            )

        relationship_map = safe_facts.get("_legal_relationship_map", "")
        relationship_block = (
            f"LEGAL RELATIONSHIP MAP (verified graph  -  PRIORITISE over isolated "
            f"snippets):\n{relationship_map}\n\n" if relationship_map else ""
        )
        prompt = (
            f"Assess the following unfair dismissal matter.\n\n"
            f"{relationship_block}"
            f"RETRIEVED RULES (verbatim  -  do not alter):\n"
            f"{json.dumps(bundle.exact_rules, indent=2, default=str)}\n\n"
            f"RETRIEVED AUTHORITIES:\n{json.dumps(bundle.authorities, indent=2)}\n\n"
            f"DEADLINE (pre-computed from rules  -  source must remain 'rules'):\n"
            f"{json.dumps(deadline_info, indent=2, default=str)}\n\n"
            f"DE-IDENTIFIED FACTS:\n{json.dumps(safe_facts, indent=2, default=str)}\n\n"
            "Return ONLY valid JSON matching the structured assessment schema. No prose."
        )

        self._last_payload = {
            "model":           self._model_id,
            "provider":        "local_inference",
            "base_url":        self._base_url,
            "safe_facts_keys": list(safe_facts.keys()),
            "boundary_log":    boundary_log,
            "prompt_length":   len(prompt),
        }

        try:
            resp = httpx.post(
                f"{self._base_url}/v1/chat/completions",
                json={
                    "model": self._model_id,
                    "messages": [
                        {"role": "system", "content": self._SYSTEM},
                        {"role": "user",   "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens":  2048,
                },
                timeout=self.TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(
                "Local inference unavailable (%s)  -  returning MODEL_UNAVAILABLE", exc
            )
            return StructuredAssessment(
                claim_type="unfair_dismissal",
                jurisdiction=safe_facts.get("jurisdiction", "EW"),
                has_viable_claim="uncertain",
                strength="uncertain",
                reasoning_summary="Local inference unavailable  -  insufficient grounding.",
                value_range=ValueRange(low=0, high=0, currency="GBP", basis="model unavailable"),
                key_weaknesses=["Local inference node unavailable (MODEL_UNAVAILABLE). Seek legal advice."],
                deadline=Deadline(limitation_date=None, source="rules",
                                  authority="ERA 1996 s.111(2)"),
                recommended_next_step="seek_solicitor",
                citations=[],
                grounding_score=0.0,
                confidence_score=0.0,
                insufficient_grounding=True,
            )

        raw = resp.json()["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        data = json.loads(raw)
        if "deadline" in data:
            data["deadline"]["source"] = "rules"  # defensive enforcement
        return StructuredAssessment(**data)

    def get_boundary_payload(self) -> Optional[dict]:
        return self._last_payload

    def stream_chat(self, messages: list, max_tokens: int = 512):
        """Yield content deltas from Ollama (stream=true) for the SSE reasoning lane.
        Fail-soft: yields a single '[MODEL_UNAVAILABLE]' marker if unreachable, so the
        client stream never hangs. The authoritative structured assessment + Critic
        gate still run on the full output before any advice is finalised."""
        import json as _json
        import httpx
        try:
            with httpx.stream(
                "POST", f"{self._base_url}/v1/chat/completions",
                json={"model": self._model_id, "messages": messages,
                      "temperature": 0.1, "max_tokens": max_tokens, "stream": True},
                timeout=self.TIMEOUT_SECONDS,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[len("data:"):].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        delta = _json.loads(payload)["choices"][0]["delta"].get("content")
                    except Exception:
                        delta = None
                    if delta:
                        yield delta
        except Exception as exc:
            logger.warning("stream_chat unavailable: %s", exc)
            yield "[MODEL_UNAVAILABLE]"


def get_ai_provider_status() -> dict:
    """
    Return the current AI provider configuration status.
    Used by /health endpoint to report provider mode transparently.
    """
    from backend.core.inference_policy import (
        get_allowed_inference_backend, get_ollama_base_url, get_ollama_model)
    # LOCAL OLLAMA ONLY  -  status reports the internal Ollama backend. External
    # providers are forbidden and are never "active" for legal inference.
    return {
        "provider": get_allowed_inference_backend(),   # "ollama"
        "active": True,
        "backend": "ollama_local",
        "base_url": get_ollama_base_url(),
        "model": get_ollama_model(),
        "note": "Local Ollama only  -  no external LLM. Last resort after RULES + GRAPHRAG.",
    }
    return {"provider": "stub", "active": False,       # noqa: unreachable legacy
            "note": "No AI key configured  -  StubReasoningModel active"}


def select_model(settings) -> "ReasoningModel":
    """
    Select the reasoning model provider based on AI_PROVIDER env var and available keys.

    AI_PROVIDER=disabled → always returns StubReasoningModel with clear log
    AI_PROVIDER=anthropic (or key set) → attempts Anthropic/Claude
    Fallback → StubReasoningModel (safe: governance gate handles insufficient_grounding)

    Never fails  -  always returns a usable model.
    The pipeline continues; governance gate handles insufficient_grounding.
    """
    import os
    from backend.core.inference_policy import assert_no_external_llm_enabled
    # Hard mandate: lawapp legal routes are LOCAL OLLAMA ONLY. Refuse to serve if an
    # external/cloud provider mode is configured (fail closed, never silently).
    assert_no_external_llm_enabled()
    ai_provider = os.getenv("AI_PROVIDER", "").lower()

    if ai_provider == "disabled":
        logger.info("Model provider: DISABLED (AI_PROVIDER=disabled)")
        return StubReasoningModel()

    # Local Inference Fabric (Ollama)  -  PRIMARY provider when enabled. No cloud
    # APIs: reasons on lawapp's own metal. Unreachable => fail soft to stub.
    #
    # The canonical env contract is owned by inference_policy (LAWAPP_LLM_PROVIDER /
    # LAWAPP_OLLAMA_BASE_URL / LAWAPP_OLLAMA_MODEL  -  the names the deployment sets).
    # Earlier this block read AI_PROVIDER/OLLAMA_BASE_URL/settings only, so the
    # deployed LAWAPP_* wiring was ignored and /assess silently fell to the Stub
    # (insufficient_grounding). Resolve provider/URL/model through the policy
    # helpers so deployment and code agree on ONE contract.
    lawapp_provider = (os.getenv("LAWAPP_LLM_PROVIDER") or "").strip().lower()
    local_enabled = (
        ai_provider == "local"
        or lawapp_provider == "ollama_local"
        or getattr(settings, "local_inference_enabled", False)
    )
    if local_enabled:
        from backend.core.inference_policy import (
            get_ollama_base_url, get_ollama_model)
        # LAWAPP_OLLAMA_BASE_URL / OLLAMA_BASE_URL env win (override/tests); else the
        # Settings default (the lawapp-ai Ollama Service DNS). Never a node IP.
        base_url = get_ollama_base_url()
        mid = get_ollama_model()
        logger.info("Model provider: Local Inference Fabric (%s @ %s)", mid, base_url)
        try:
            return LocalInferenceReasoningModel(base_url=base_url, model_id=mid)
        except Exception as exc:
            logger.warning("Local inference init failed: %s  -  falling back", exc)

    # LOCAL OLLAMA ONLY (hard mandate). NO OpenRouter, NO Anthropic, NO cloud
    # fallback. External provider classes (OpenRouterReasoningModel /
    # ClaudeReasoningModel) are intentionally NEVER constructed for legal routes.
    # If local inference is unreachable we do NOT call a cloud model: we return the
    # deterministic Stub, whose insufficient_grounding the governance gate routes to
    # honest uncertainty/human-help (fail closed).
    logger.info(
        "Model provider: local-only. Ollama not enabled/unreachable -> "
        "StubReasoningModel (insufficient_grounding); NO external/cloud fallback."
    )
    return StubReasoningModel()


# ── OAuth / JWT Token Models ─────────────────────────────────────────────────

from pydantic import BaseModel


def encrypt_value(value: str | None) -> str | None:
    if value is None:
        return None
    return "[ENCRYPTED]"


class OAuthToken(BaseModel):
    """OAuth2 access token response."""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    scope: Optional[str] = None

    def model_dump(self, *args, **kwargs):
        data = super().model_dump(*args, **kwargs)
        if data.get("access_token"):
            data["access_token"] = encrypt_value(data["access_token"])
        if data.get("refresh_token"):
            data["refresh_token"] = encrypt_value(data["refresh_token"])
        return data

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
                "scope": "read write",
            }
        }
