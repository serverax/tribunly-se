"""
Evidence Gap Detector.

Before giving a conclusion, identify missing facts.
If key facts are missing, the Brain must say "insufficient facts"
and ask for the exact missing data.

GUARDRAIL: No legal conclusion may be drawn with missing essential facts.
"""

from __future__ import annotations

from typing import Optional

# ── Required facts per claim type ────────────────────────────────────────────

_REQUIRED_UD = {
    "edt": "effective_date_of_termination",
    "service_start_date": "employment_start_date",
}

_STRONGLY_RECOMMENDED_UD = {
    "reason_for_dismissal": "reason_for_dismissal",
    "weekly_pay": "weekly_pay_for_compensation_estimate",
}

_REQUIRED_UPW = {
    "wages_due_date": "date_wages_were_due",
    "unpaid_amount": "amount_unpaid_or_deducted",
}

_REQUIRED_COMMON = {
    "jurisdiction": "jurisdiction",
}

# ── Gap detection ─────────────────────────────────────────────────────────────

def detect_gaps(claim_type: str, facts: dict) -> list[str]:
    """
    Return a list of missing required field names for the given claim type.

    Each returned item is the field name that is missing.
    An empty list means no required gaps.
    """
    gaps = []

    # Common required fields
    for field in _REQUIRED_COMMON:
        if not facts.get(field):
            gaps.append(field)

    if claim_type == "unfair_dismissal":
        for field, label in _REQUIRED_UD.items():
            if not facts.get(field):
                gaps.append(field)
        # Strongly recommended (not blocking but flagged)
        for field in _STRONGLY_RECOMMENDED_UD:
            if not facts.get(field):
                gaps.append(f"recommended:{field}")

    elif claim_type == "unpaid_wages":
        for field in _REQUIRED_UPW:
            if not facts.get(field):
                gaps.append(field)

    return gaps


def describe_gaps(gaps: list[str]) -> list[dict]:
    """
    Convert raw gap field names into user-readable descriptions.
    """
    _DESCRIPTIONS = {
        "edt": "Date your employment ended (effective date of termination)",
        "service_start_date": "Date you started working for this employer",
        "wages_due_date": "Date wages were due (when you should have been paid)",
        "unpaid_amount": "Amount unpaid or wrongly deducted (£ gross)",
        "jurisdiction": "Jurisdiction (England and Wales, Scotland, or Northern Ireland)",
        "reason_for_dismissal": "Reason given by employer for dismissal",
        "weekly_pay": "Your gross weekly pay (for compensation estimate)",
        "employer_name": "Employer's full legal name",
        "acas_ec_number": "ACAS Early Conciliation certificate number (if applicable)",
        "ec_day_a": "Date you first contacted ACAS (EC Day A)",
        "ec_day_b": "Date EC certificate was issued (EC Day B)",
        "appeal_status": "Whether you appealed the dismissal",
        "grievance_status": "Whether you raised a grievance",
        "protected_characteristic": "Any protected characteristic relevant to the claim",
        "documents_available": "Documents available (dismissal letter, contract, payslips, emails)",
    }
    result = []
    for gap in gaps:
        required = not gap.startswith("recommended:")
        clean = gap.replace("recommended:", "")
        result.append({
            "field": clean,
            "required": required,
            "description": _DESCRIPTIONS.get(clean, f"Missing: {clean}"),
        })
    return result


def has_minimum_facts(claim_type: str, facts: dict) -> bool:
    """True if the minimum required facts for a viable assessment are present."""
    gaps = detect_gaps(claim_type, facts)
    required_gaps = [g for g in gaps if not g.startswith("recommended:")]
    return len(required_gaps) == 0
