"""Arabic formatter: formal native legal phrasing with Arabic keys in output."""

from __future__ import annotations

from typing import Any

from backend.language_engine.ar import legal_templates as tpl
from backend.language_engine.shared import rule_mapper


def _headline(status: str, insufficient: bool) -> str:
    if insufficient:
        return tpl.HEADLINE_GROUNDING
    if status not in ("ok", "fallback"):
        return tpl.HEADLINE_BLOCKED
    return tpl.HEADLINE_OK


def _native_summary(core: dict[str, Any], claim: str, viability: str | None, strength: str) -> str:
    base = core.get("reasoning_summary") or core.get("message")
    if base and _looks_arabic(str(base)):
        return str(base)

    claim_ar = rule_mapper.claim_label(claim, "ar")
    viab_ar = rule_mapper.viability_label(viability, "ar")
    strength_ar = rule_mapper.strength_label(strength, "ar")

    if core.get("status") not in ("ok", "fallback"):
        return str(core.get("message") or "يرجى إكمال الوقائع للحصول على تقييم مؤسس على مصادر موثقة.")

    return (
        f"بناءً على الوقائع المقدمة، يتعلق التقييم بـ{claim_ar}. "
        f"{viab_ar}. قوة المطالبة المبدئية: {strength_ar}. "
        "هذا تقييم معلوماتي فقط وليس مشورة قانونية."
    )


def _looks_arabic(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06FF" for ch in text)


def _native_weaknesses(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items or []:
        if isinstance(item, str):
            if _looks_arabic(item):
                out.append(item)
                continue
            key = item.strip().lower().replace(" ", "_")
            out.append(tpl.WEAKNESS_TEMPLATES.get(key, f"يرجى مراجعة: {item}"))
        else:
            out.append(str(item))
    return out or ["راجع وقائعك مع المستندات الداعمة."]


def _native_employer_args(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items or []:
        if isinstance(item, str):
            if _looks_arabic(item):
                out.append(item)
                continue
            key = item.strip().lower().replace(" ", "_")
            out.append(tpl.EMPLOYER_ARGUMENT_TEMPLATES.get(key, f"قد يثير صاحب العمل: {item}"))
        else:
            out.append(str(item))
    return out


def format_assessment(core: dict[str, Any]) -> dict[str, Any]:
    status = str(core.get("status") or "unknown")
    claim = str(core.get("claim_type") or "unfair_dismissal")
    strength = str(core.get("strength") or "uncertain")
    viability = core.get("has_viable_claim")
    next_step = str(core.get("recommended_next_step") or "free_diagnosis_only")

    summary = _native_summary(core, claim, viability, strength)

    return {
        "headline": _headline(status, bool(core.get("insufficient_grounding"))),
        "reasoning_summary": summary,
        "key_weaknesses": _native_weaknesses(core.get("key_weaknesses") or []),
        "employer_arguments": _native_employer_args(core.get("employer_arguments") or []),
        "recommended_next_step": next_step,
        "recommended_next_step_label": rule_mapper.next_step_label(next_step, "ar"),
        "strength_label": rule_mapper.strength_label(strength, "ar"),
        "viability_label": rule_mapper.viability_label(viability, "ar"),
        "claim_label": rule_mapper.claim_label(claim, "ar"),
        "disclaimer": tpl.DISCLAIMER,
        "formatted": {
            "نوع_المطالبة": claim,
            "تسمية_المطالبة": rule_mapper.claim_label(claim, "ar"),
            "القوة": strength,
            "تسمية_القوة": rule_mapper.strength_label(strength, "ar"),
            "الجدوى": viability,
            "المراجع": rule_mapper.format_citations(core.get("citations") or [], "ar"),
            "الموعد_النهائي": core.get("deadline") or core.get("deadline_info"),
            "الملخص": summary,
            "نقاط_الضعف": _native_weaknesses(core.get("key_weaknesses") or []),
            "حجج_صاحب_العمل": _native_employer_args(core.get("employer_arguments") or []),
        },
    }
