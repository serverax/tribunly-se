"""Language module router: neutral assessment -> native presentation."""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.language_engine.ar.phrasing import render_ar
from backend.language_engine.en.phrasing import render_en
from backend.language_engine.shared.types import (
    LanguageNeutralAssessment,
    RenderContext,
    RenderedAssessment,
    SUPPORTED_LOCALES,
)

logger = logging.getLogger(__name__)

_RENDERERS = {
    "en": render_en,
    "ar": render_ar,
}


def render_assessment(
    payload: dict[str, Any],
    locale: str = "en",
    *,
    use_llm_phrasing: bool = False,
    model=None,
) -> dict[str, Any]:
    """
    Attach assessment_core (neutral) and locale-rendered fields to API payload.
    Does not alter citations, rule_keys, or RAG retrieval.
    """
    loc = locale if locale in SUPPORTED_LOCALES else "en"
    neutral = LanguageNeutralAssessment.from_pipeline_dict(payload)
    ctx = RenderContext.for_locale(loc)
    rendered = _render_native(neutral, loc)

    if use_llm_phrasing and model is not None and hasattr(model, "stream_chat"):
        rendered = _maybe_llm_phrase(neutral, rendered, loc, model)

    out = dict(payload)
    out["locale"] = loc
    out["dir"] = ctx.dir
    out["direction"] = ctx.dir
    out["font_stack"] = ctx.font_stack
    out["assessment_core"] = neutral.to_dict()
    rendered_dict = rendered.to_dict()
    if loc == "ar":
        rendered_dict["formatted"] = _arabic_formatted(neutral, rendered)
    else:
        rendered_dict["formatted"] = _english_formatted(neutral, rendered)
    out["rendered"] = rendered_dict
    out.update(rendered_dict)
    # Preserve canonical neutral fields for clients that read legacy keys
    out["reasoning_summary"] = rendered.reasoning_summary
    out["key_weaknesses"] = rendered.key_weaknesses
    out["employer_arguments"] = rendered.employer_arguments
    out["recommended_next_step"] = rendered.recommended_next_step
    return out


def _english_formatted(neutral: LanguageNeutralAssessment, rendered: RenderedAssessment) -> dict[str, Any]:
    return {
        "claim_type": neutral.claim_type,
        "headline": rendered.headline,
        "strength_label": rendered.strength_label,
        "citations": neutral.citations,
        "deadline": neutral.deadline,
    }


def _arabic_formatted(neutral: LanguageNeutralAssessment, rendered: RenderedAssessment) -> dict[str, Any]:
    return {
        "نوع_المطالبة": neutral.claim_type,
        "العنوان": rendered.headline,
        "تسمية_القوة": rendered.strength_label,
        "الملخص": rendered.reasoning_summary,
        "نقاط_الضعف": rendered.key_weaknesses,
        "حجج_صاحب_العمل": rendered.employer_arguments,
        "الخطوة_التالية": rendered.recommended_next_step,
        "المراجع": [
            {"المرجع": c.get("cite"), "الرابط": c.get("url")}
            for c in (neutral.citations or [])
            if isinstance(c, dict)
        ],
        "الموعد_النهائي": neutral.deadline,
    }


def _render_native(neutral: LanguageNeutralAssessment, locale: str) -> RenderedAssessment:
    fn = _RENDERERS.get(locale, render_en)
    return fn(neutral)


def _maybe_llm_phrase(
    neutral: LanguageNeutralAssessment,
    template: RenderedAssessment,
    locale: str,
    model,
) -> RenderedAssessment:
    try:
        if locale == "ar":
            from backend.language_engine.ar.prompts import build_phrasing_messages
        else:
            from backend.language_engine.en.prompts import build_phrasing_messages

        messages = build_phrasing_messages(neutral.to_dict())
        text = "".join(model.stream_chat(messages)).strip()
        if not text or len(text) < 40:
            return template
        return RenderedAssessment(
            locale=template.locale,
            dir=template.dir,
            reasoning_summary=text,
            key_weaknesses=template.key_weaknesses,
            employer_arguments=template.employer_arguments,
            recommended_next_step=template.recommended_next_step,
            strength_label=template.strength_label,
            headline=template.headline,
        )
    except Exception as exc:
        logger.debug("LLM phrasing skipped: %s", exc)
        return template


def validate_locale_consistency(
    payloads: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Stub v1: ensure rule_keys and citation rule_keys match across locales.
    """
    if not payloads:
        return {"consistent": True, "detail": "no payloads"}

    base_locale = next(iter(payloads))
    base = payloads[base_locale].get("assessment_core") or payloads[base_locale]
    base_keys = set(base.get("rule_keys") or [])
    base_cites = {c.get("rule_key") for c in (base.get("citations") or []) if c.get("rule_key")}

    mismatches: list[str] = []
    for loc, body in payloads.items():
        core = body.get("assessment_core") or body
        keys = set(core.get("rule_keys") or [])
        cites = {c.get("rule_key") for c in (core.get("citations") or []) if c.get("rule_key")}
        if keys != base_keys:
            mismatches.append(f"rule_keys:{loc}")
        if cites != base_cites:
            mismatches.append(f"citations:{loc}")

    return {
        "consistent": len(mismatches) == 0,
        "base_locale": base_locale,
        "checked_locales": list(payloads.keys()),
        "mismatches": mismatches,
    }
