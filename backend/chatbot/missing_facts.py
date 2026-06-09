from __future__ import annotations


def missing_facts_for(claim_type: str | None, facts: dict) -> list[str]:
    if not claim_type:
        return ["what happened", "what outcome you want"]
    if claim_type in {"unfair_dismissal", "wrongful_dismissal", "constructive_dismissal"}:
        required = ["dismissal_date", "years_service"]
        return [field for field in required if field not in facts]
    if claim_type in {"unlawful_deduction_wages", "holiday_pay", "national_minimum_wage"}:
        required = ["amount_owed", "last_payment_date"]
        return [field for field in required if field not in facts]
    if "discrimination" in claim_type or claim_type in {"reasonable_adjustments", "pregnancy_maternity"}:
        required = ["protected_characteristic", "incident_date", "treatment"]
        return [field for field in required if field not in facts]
    return []
