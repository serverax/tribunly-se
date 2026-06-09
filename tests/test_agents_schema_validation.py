"""
Schema-wall tests for the 4-agent architecture (Phase 1, AC-003/AC-004).

Proves: valid outputs pass; extra keys fail; invalid enums fail; missing
required fields fail; out-of-range / wrong-type scores fail; wrong date format
fails; and conversational / markdown-fenced JSON is rejected (never repaired).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.core.agentic.errors import AgentOutputError
from backend.core.agentic import schemas as S

# ── valid sample payloads ─────────────────────────────────────────────────────
VALID_AEE = {
    "timeline": [{
        "date": "2026-05-10", "date_status": "exact",
        "event_summary": "Employee dismissed", "evidence_type": "dismissal",
        "source_quote": "you are dismissed", "pii_scrubbed": True, "confidence": 0.9,
    }],
    "missing_critical_dates": False,
    "pii_redactions": [{"type": "employer", "replacement": "[EMPLOYER_NAME]"}],
    "requires_user_confirmation": True,
}

VALID_ART = {
    "claim_type": ["unfair_dismissal"], "viability_score_percentage": 70,
    "strength": "high", "statutory_citations_used": ["Employment Rights Act 1996 s.94"],
    "case_law_citations_used": [], "acas_citations_used": [], "key_weaknesses": ["short service"],
    "affirmation_risk_detected": False, "repudiatory_breach_detected": True,
    "causation_assessed": True, "limitation_status": "in_time",
    "recommended_next_step": "prepare_documents", "grounding_score": 0.8,
    "confidence_score": 0.7, "insufficient_grounding": False,
}

VALID_SEA = {
    "document_type": "schedule_of_loss", "markdown": "# Schedule of Loss\nNot legal advice.",
    "citations_used": ["Employment Rights Act 1996 s.123"], "boundary_notice_present": True,
    "generated_from_assessment_id": "assessment-1", "requires_guard_review": True,
}

VALID_GUARD = {
    "safety_check_passed": True, "failed_citations": [], "unsupported_legal_assertions": [],
    "reserved_activity_flags": [], "boundary_notice_present": True, "reason_for_failure": "",
}


def test_valid_outputs_pass():
    assert S.AEEOutput.model_validate(VALID_AEE)
    assert S.ARTOutput.model_validate(VALID_ART)
    assert S.SEAOutput.model_validate(VALID_SEA)
    assert S.CitationGuardOutput.model_validate(VALID_GUARD)


def test_extra_keys_fail():
    bad = {**VALID_ART, "secret_backdoor": True}
    with pytest.raises(ValidationError):
        S.ARTOutput.model_validate(bad)


def test_invalid_enum_fails():
    bad = {**VALID_ART, "strength": "guaranteed_win"}
    with pytest.raises(ValidationError):
        S.ARTOutput.model_validate(bad)
    bad2 = {**VALID_ART, "claim_type": ["definitely_winning"]}
    with pytest.raises(ValidationError):
        S.ARTOutput.model_validate(bad2)


def test_missing_required_field_fails():
    bad = {k: v for k, v in VALID_ART.items() if k != "viability_score_percentage"}
    with pytest.raises(ValidationError):
        S.ARTOutput.model_validate(bad)


def test_out_of_range_scores_fail():
    with pytest.raises(ValidationError):
        S.ARTOutput.model_validate({**VALID_ART, "viability_score_percentage": 150})
    with pytest.raises(ValidationError):
        S.ARTOutput.model_validate({**VALID_ART, "confidence_score": 1.5})


def test_wrong_score_type_fails():
    with pytest.raises(ValidationError):
        S.AEEOutput.model_validate({
            **VALID_AEE,
            "timeline": [{**VALID_AEE["timeline"][0], "confidence": "high"}],
        })


def test_wrong_date_format_fails():
    with pytest.raises(ValidationError):
        S.AEEOutput.model_validate({
            **VALID_AEE,
            "timeline": [{**VALID_AEE["timeline"][0], "date": "10/05/2026"}],
        })


def test_conversational_prefix_rejected():
    with pytest.raises(AgentOutputError):
        S.strict_json_parse_no_wrappers('Here is the JSON you asked for: {"a": 1}')


def test_markdown_fenced_json_rejected():
    with pytest.raises(AgentOutputError):
        S.strict_json_parse_no_wrappers("```json\n{\"a\": 1}\n```")


def test_non_object_json_rejected():
    with pytest.raises(AgentOutputError):
        S.strict_json_parse_no_wrappers("[1, 2, 3]")


def test_strict_parse_accepts_bare_object():
    assert S.strict_json_parse_no_wrappers('{"safety_check_passed": true}') == {"safety_check_passed": True}
