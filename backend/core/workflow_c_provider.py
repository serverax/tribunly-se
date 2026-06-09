"""
Workflow C provider stage — wires the replaceable LLM provider plug into /assess.

Order of operations (founder mandate: DB FIRST, RULES FIRST, CITATIONS FIRST,
AI SECOND, FAIL-CLOSED ALWAYS):

  deterministic assessment already produced (RAG + rules)  ->  this stage:
    1. if RAG is weak/empty  -> DO NOT call the provider (skipped_weak_rag)
    2. de-identify a grounded bundle (no raw PII leaves the building)
    3. call the active provider (Stub by default; OpenRouter only if enabled+keyed)
    4. run all 4 AIA validators on the provider output
    5. accept only if every validator passes; otherwise reject / fail closed

This never replaces the deterministic result — it attaches a ``provider_stage``
block and only contributes if it passes every gate.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a restricted UK employment-law reasoning assistant. Use ONLY the "
    "provided grounded bundle (citations + rule values + de-identified facts). "
    "Do not invent citations, do not change deterministic values, do not use "
    "reserved/solicitor wording, include weaknesses. Return strict JSON only."
)


def _bundle_citations(assessment_result: dict) -> list[str]:
    out = []
    for c in (assessment_result.get("citations") or []):
        if isinstance(c, dict):
            out.append(c.get("cite") or c.get("citation") or "")
        elif isinstance(c, str):
            out.append(c)
    return [c for c in out if c]


def _rule_values(assessment_result: dict) -> dict:
    rv: dict = {}
    di = assessment_result.get("deadline_info") or {}
    for k in ("time_limit_months", "weeks_pay_cap_amount", "compensatory_cap_amount"):
        if di.get(k) is not None:
            rv[k] = di[k]
    return rv


def run_provider_stage(
    *,
    query: str,
    facts: dict,
    assessment_result: dict,
    trace_id: str = "",
    case_id: str = "",
    provider=None,
) -> dict:
    """Run the provider plug + 4 AIA validators after the deterministic assessment.
    Returns a structured ``provider_stage`` block. Never raises (fails closed)."""
    status = assessment_result.get("status")
    citations = _bundle_citations(assessment_result)
    rules_values = _rule_values(assessment_result)

    # (1) weak/empty RAG -> never call the provider
    weak = bool(assessment_result.get("insufficient_grounding")) or status in (
        "insufficient_grounding", "not_supported", "invalid_date", "model_not_configured",
    )
    if weak or not citations:
        return {"provider_used": False, "status": "skipped_weak_rag",
                "reason": "RAG/grounding insufficient; provider not called"}

    # (2) de-identify the grounded bundle
    from backend.core.agentic.pii import scrub_payload, residual_pii
    safe_bundle = scrub_payload({
        "query": query, "facts": facts or {},
        "citations": citations, "rule_values": rules_values,
    })
    leak = residual_pii(safe_bundle)
    if leak:
        return {"provider_used": False, "status": "fail_closed_pii",
                "reason": f"residual PII ({leak}); refusing to call provider"}

    # (3) call the active provider (Stub by default)
    if provider is None:
        from backend.core.llm_provider import get_provider
        provider = get_provider()
    try:
        raw = provider.complete_json(
            system_prompt=_SYSTEM, payload=safe_bundle, trace_id=trace_id, case_id=case_id)
    except Exception as exc:
        return {"provider_used": getattr(provider, "name", "?"),
                "status": "fail_closed", "reason": str(exc)[:160]}

    if not isinstance(raw, dict) or raw.get("insufficient_grounding"):
        return {"provider_used": provider.name, "status": "insufficient_grounding",
                "reason": "provider declined / no grounded reasoning"}

    # (4) run all 4 AIA validators on provider output
    from backend.core.agentic.aia_validators import run_all_validators
    passed, report = run_all_validators(
        cited=raw.get("statutory_citations_used") or raw.get("citations") or [],
        rag_bundle_citations=citations,
        claimed_rule_values=raw.get("rule_values") or {},
        rules_values=rules_values,
        outbound_payload=safe_bundle,
        answer_text=json.dumps(raw, ensure_ascii=False),
        non_trivial=True,
        has_weaknesses=bool(raw.get("key_weaknesses")),
    )
    if not passed:
        return {"provider_used": provider.name, "status": "rejected_by_aia",
                "failures": report}

    # (5) accepted
    return {"provider_used": provider.name, "status": "accepted",
            "assessment": raw, "validators": "passed"}
