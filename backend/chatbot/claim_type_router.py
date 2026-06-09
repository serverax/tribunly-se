from __future__ import annotations


def route_claim_type(message: str) -> str | None:
    text = message.lower()
    if any(term in text for term in ("resigned", "forced me out", "pressure to resign")):
        return "constructive_dismissal"
    if any(term in text for term in ("not paid", "wages", "salary missing", "deduction")):
        return "unlawful_deduction_wages"
    if "holiday" in text and "pay" in text:
        return "holiday_pay"
    if any(term in text for term in ("pregnant", "maternity")):
        return "pregnancy_maternity"
    if any(term in text for term in ("disabled", "adjustment", "reasonable adjustment")):
        return "reasonable_adjustments"
    if any(term in text for term in ("race", "religion", "age", "sex", "gender", "discrimination", "harassment")):
        return "direct_discrimination"
    if "whistleblow" in text:
        return "whistleblowing"
    if "redundan" in text:
        return "redundancy"
    if "tupe" in text or "transfer" in text:
        return "tupe_transfer"
    if any(term in text for term in ("hours", "break", "working time")):
        return "working_time"
    if "union" in text:
        return "trade_union_rights"
    if "health and safety" in text or "safety complaint" in text:
        return "health_safety_detriment"
    if any(term in text for term in ("notice", "wrongful")):
        return "wrongful_dismissal"
    if any(term in text for term in ("dismissed", "sacked", "fired", "terminated")):
        return "unfair_dismissal"
    return None
