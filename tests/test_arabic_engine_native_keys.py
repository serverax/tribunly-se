"""Arabic engine native keys and formal tone."""

from __future__ import annotations

from backend.language_engine.ar import prompts
from backend.language_engine.ar.phrasing import render_ar
from backend.language_engine.shared.types import LanguageNeutralAssessment


def test_arabic_prompts_contain_native_unfair_dismissal_and_explanation_style():
    assert "الفصل" in prompts.UNFAIR_DISMISSAL_PROMPT
    assert "أسلوب الشرح" in prompts.EXPLANATION_STYLE
    assert "لا تضمن" in prompts.SYSTEM_PROMPT
    msgs = prompts.build_phrasing_messages({"claim_type": "unfair_dismissal", "status": "ok"})
    assert msgs[0]["role"] == "system"
    assert "الفصل" in msgs[0]["content"]


def test_arabic_render_uses_rtl_and_formatted_keys():
    neutral = LanguageNeutralAssessment(
        status="ok",
        claim_type="unfair_dismissal",
        jurisdiction="EW",
        strength="medium",
        reasoning_summary="English pipeline summary.",
        key_weaknesses=["short_service"],
        citations=[{"cite": "ERA 1996 s.111", "url": "https://example.test", "rule_key": "x"}],
    )
    rendered = render_ar(neutral)
    assert rendered.locale == "ar"
    assert rendered.dir == "rtl"
    assert rendered.headline
    assert not rendered.reasoning_summary.startswith("English pipeline")


def test_arabic_formatted_keys_via_router():
    from backend.language_engine.router import render_assessment

    out = render_assessment(
        {
            "status": "ok",
            "claim_type": "unfair_dismissal",
            "jurisdiction": "EW",
            "strength": "weak",
            "reasoning_summary": "Neutral",
            "citations": [{"cite": "ERA 1996", "url": "https://x", "rule_key": "k"}],
        },
        "ar",
    )
    formatted = out["rendered"]["formatted"]
    assert "المراجع" in formatted
    assert "تسمية_القوة" in formatted
