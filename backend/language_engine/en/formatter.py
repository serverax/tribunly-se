"""English formatter: native phrasing from neutral assessment core."""

from __future__ import annotations

from typing import Any

from backend.language_engine.en import legal_templates as tpl
from backend.language_engine.shared import rule_mapper


def _headline(status: str, insufficient: bool) -> str:
    if insufficient:
        return tpl.HEADLINE_GROUNDING
    if status not in ("ok", "fallback"):
        return tpl.HEADLINE_BLOCKED
    return tpl.HEADLINE_OK


def _native_weaknesses(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items or []:
        if isinstance(item, str):
            key = item.strip().lower().replace(" ", "_")
            out.append(tpl.WEAKNESS_TEMPLATES.get(key, item))
        else:
            out.append(str(item))
    return out or ["Review your fact pattern with supporting documents."]


def _native_employer_args(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items or []:
        if isinstance(item, str):
            key = item.strip().lower().replace(" ", "_")
            out.append(tpl.EMPLOYER_ARGUMENT_TEMPLATES.get(key, item))
        else:
            out.append(str(item))
    return out


def format_assessment(core: dict[str, Any]) -> dict[str, Any]:
    status = str(core.get("status") or "unknown")
    claim = str(core.get("claim_type") or "unfair_dismissal")
    strength = str(core.get("strength") or "uncertain")
    viability = core.get("has_viable_claim")
    next_step = str(core.get("recommended_next_step") or "free_diagnosis_only")
    summary = str(
        core.get("reasoning_summary")
        or core.get("message")
        or "Complete the fact pattern for a grounded assessment."
    )

    return {
        "headline": _headline(status, bool(core.get("insufficient_grounding"))),
        "reasoning_summary": summary,
        "key_weaknesses": _native_weaknesses(core.get("key_weaknesses") or []),
        "employer_arguments": _native_employer_args(core.get("employer_arguments") or []),
        "recommended_next_step": next_step,
        "recommended_next_step_label": rule_mapper.next_step_label(next_step, "en"),
        "strength_label": rule_mapper.strength_label(strength, "en"),
        "viability_label": rule_mapper.viability_label(viability, "en"),
        "claim_label": rule_mapper.claim_label(claim, "en"),
        "disclaimer": tpl.DISCLAIMER,
        "formatted": {
            "claim_type": claim,
            "claim_label": rule_mapper.claim_label(claim, "en"),
            "strength": strength,
            "strength_label": rule_mapper.strength_label(strength, "en"),
            "viability": viability,
            "citations": rule_mapper.format_citations(core.get("citations") or [], "en"),
            "deadline": core.get("deadline") or core.get("deadline_info"),
        },
    }
