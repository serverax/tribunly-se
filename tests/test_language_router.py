"""Language router unit tests."""

from __future__ import annotations

from backend.language_engine.router import render_assessment
from backend.language_engine.shared.detector import detect_arabic_script, resolve_locale


def test_detect_arabic_script_in_query():
    assert detect_arabic_script("هل لدي مطالبة؟") is True
    assert detect_arabic_script("Do I have a claim?") is False


def test_resolve_locale_body_language_ar():
    loc = resolve_locale(None, body_language="ar")
    assert loc == "ar"


def test_resolve_locale_arabic_script_fallback():
    loc = resolve_locale(None, sample_text="ما هو موعد التقادم؟")
    assert loc == "ar"


def test_render_assessment_en_has_assessment_core_and_rendered():
    payload = {
        "status": "ok",
        "claim_type": "unfair_dismissal",
        "jurisdiction": "EW",
        "strength": "medium",
        "reasoning_summary": "Based on cited rules, a preliminary view is provided.",
        "key_weaknesses": ["procedure_gap"],
        "citations": [{"cite": "ERA 1996 s.111", "url": "https://example.test", "rule_key": "unfair_dismissal.time_limit_months"}],
    }
    out = render_assessment(payload, "en")
    assert out["locale"] == "en"
    assert out["dir"] == "ltr"
    assert "assessment_core" in out
    assert out["assessment_core"]["claim_type"] == "unfair_dismissal"
    assert "rendered" in out
    assert out["rendered"]["headline"]


def test_render_assessment_ar_rtl_and_native_summary():
    payload = {
        "status": "ok",
        "claim_type": "unfair_dismissal",
        "jurisdiction": "EW",
        "strength": "medium",
        "reasoning_summary": "English neutral summary from pipeline.",
        "key_weaknesses": ["evidence_thin"],
        "citations": [{"cite": "ERA 1996 s.111", "url": "https://example.test", "rule_key": "unfair_dismissal.time_limit_months"}],
    }
    out = render_assessment(payload, "ar")
    assert out["locale"] == "ar"
    assert out["dir"] == "rtl"
    assert out["rendered"]["formatted"]["الملخص"]
    assert "نقاط_الضعف" in out["rendered"]["formatted"]
