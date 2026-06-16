"""Tests for language_engine router (neutral in, locale-native out)."""

from __future__ import annotations

from backend.language_engine.router import render_assessment, validate_locale_consistency
from backend.language_engine.shared.types import LanguageNeutralAssessment


NEUTRAL_PAYLOAD = {
    "status": "ok",
    "claim_type": "unfair_dismissal",
    "jurisdiction": "EW",
    "strength": "moderate",
    "reasoning_summary": "Employee may have a qualifying unfair dismissal claim based on cited rules.",
    "key_weaknesses": ["Procedure gaps need evidence."],
    "employer_arguments": ["Misconduct was serious."],
    "recommended_next_step": "File ACAS early conciliation before the deadline.",
    "citations": [
        {"rule_key": "unfair_dismissal_qualifying_period", "cite": "ERA 1996 s.108"},
        {"rule_key": "acas_ec_requirement", "cite": "ERA 1996 s.207A"},
    ],
    "trace_id": "test-trace-1",
}


def test_render_en_and_ar_share_rule_keys():
    en = render_assessment(NEUTRAL_PAYLOAD, "en")
    ar = render_assessment(NEUTRAL_PAYLOAD, "ar")

    assert en["locale"] == "en"
    assert ar["locale"] == "ar"
    assert en["dir"] == "ltr"
    assert ar["dir"] == "rtl"

    assert en["assessment_core"]["rule_keys"] == ar["assessment_core"]["rule_keys"]
    assert len(en["assessment_core"]["citations"]) == len(ar["assessment_core"]["citations"])

    en_keys = {c["rule_key"] for c in en["assessment_core"]["citations"]}
    ar_keys = {c["rule_key"] for c in ar["assessment_core"]["citations"]}
    assert en_keys == ar_keys


def test_rendered_text_differs_by_locale():
    en = render_assessment(NEUTRAL_PAYLOAD, "en")
    ar = render_assessment(NEUTRAL_PAYLOAD, "ar")

    assert en["headline"] != ar["headline"]
    assert en["strength_label"] != ar["strength_label"]
    # Arabic headline should contain Arabic script
    assert any("\u0600" <= ch <= "\u06FF" for ch in ar["headline"])


def test_assessment_core_is_language_neutral():
    rendered = render_assessment(NEUTRAL_PAYLOAD, "ar")
    core = rendered["assessment_core"]
    assert core["reasoning_summary"] == NEUTRAL_PAYLOAD["reasoning_summary"]
    assert core["claim_type"] == "unfair_dismissal"


def test_validate_locale_consistency_stub():
    en = render_assessment(NEUTRAL_PAYLOAD, "en")
    ar = render_assessment(NEUTRAL_PAYLOAD, "ar")
    report = validate_locale_consistency({"en": en, "ar": ar})
    assert report["consistent"] is True
    assert report["mismatches"] == []


def test_from_pipeline_dict_extracts_rule_keys():
    neutral = LanguageNeutralAssessment.from_pipeline_dict(NEUTRAL_PAYLOAD)
    assert "unfair_dismissal_qualifying_period" in neutral.rule_keys
    assert "acas_ec_requirement" in neutral.rule_keys
