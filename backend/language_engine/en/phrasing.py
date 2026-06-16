"""English legal tone templates (native EN, not translated from Arabic)."""

from __future__ import annotations

from backend.language_engine.shared.types import LanguageNeutralAssessment, RenderedAssessment

_STRENGTH_LABELS = {
    "strong": "Strong case indicators",
    "moderate": "Moderate case strength",
    "weak": "Weak case indicators",
    "uncertain": "Strength uncertain",
}

_CLAIM_HEADLINES = {
    "unfair_dismissal": "Unfair dismissal assessment",
    "constructive_dismissal": "Constructive dismissal assessment",
    "discrimination": "Discrimination assessment",
    "unpaid_wages": "Unpaid wages assessment",
    "whistleblowing": "Whistleblowing assessment",
    "redundancy": "Redundancy assessment",
}


def render_en(assessment: LanguageNeutralAssessment) -> RenderedAssessment:
    strength = assessment.strength or "uncertain"
    summary = assessment.reasoning_summary
    if not summary and assessment.status == "ok":
        summary = (
            f"Based on the rules database and retrieved authorities, "
            f"your {assessment.claim_type.replace('_', ' ')} matter in "
            f"{assessment.jurisdiction} has been evaluated."
        )
    elif not summary:
        summary = "Further facts are needed before a grounded assessment can be provided."

    weaknesses = list(assessment.key_weaknesses)
    if not weaknesses and assessment.status != "ok":
        weaknesses = ["Insufficient grounded evidence for a confident conclusion."]

    employer_args = list(assessment.employer_arguments)
    next_step = assessment.recommended_next_step or (
        "Review the cited sources and confirm key dates before lodging a tribunal claim."
    )

    headline = _CLAIM_HEADLINES.get(
        assessment.claim_type,
        f"{assessment.claim_type.replace('_', ' ').title()} assessment",
    )

    return RenderedAssessment(
        locale="en",
        dir="ltr",
        reasoning_summary=summary,
        key_weaknesses=weaknesses,
        employer_arguments=employer_args,
        recommended_next_step=next_step,
        strength_label=_STRENGTH_LABELS.get(strength, _STRENGTH_LABELS["uncertain"]),
        headline=headline,
    )
