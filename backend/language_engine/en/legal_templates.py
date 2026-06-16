"""English native legal phrasing templates."""

from __future__ import annotations

DISCLAIMER = (
    "This is information and structured assessment only. LawApp is not a law firm "
    "and does not provide legal advice."
)

HEADLINE_OK = "Employment claim assessment"
HEADLINE_BLOCKED = "Assessment could not be completed"
HEADLINE_GROUNDING = "Insufficient verified sources"

WEAKNESS_TEMPLATES = {
    "missing_edt": "Effective date of termination is missing.",
    "short_service": "Service may be below the qualifying period.",
    "procedure_gap": "Employer procedure may not have been followed.",
    "evidence_thin": "Supporting evidence appears limited.",
    "deadline_risk": "Limitation deadline requires urgent attention.",
}

EMPLOYER_ARGUMENT_TEMPLATES = {
    "conduct": "Employer may rely on conduct and disciplinary process.",
    "capability": "Employer may argue capability concerns were documented.",
    "redundancy": "Employer may argue a genuine redundancy situation.",
    "some_other_substantial_reason": "Employer may cite another substantial reason.",
}
