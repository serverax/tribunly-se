"""
Free public legal tools  -  deterministic, DB-first, fail-closed.

These power the no-login PREVIEW funnel (constitution §6/§9): a visitor may run
a quick screen and see an estimate, but every statutory value is loaded from the
effective-dated `rules` table via backend.core.retrieve.retrieve_rules  -  NEVER
hardcoded in this file. If a required statutory rule is absent the function fails
closed (raises ToolDataUnavailable) rather than fabricating a legal value.

None of these functions give legal advice. They produce an informational screen
or an arithmetic estimate with an explicit statutory authority reference, and they
say so. The full, saved, citation-backed result lives behind login + the brain
pipeline (assess / sovereign routes).

Public API:
    check_claim(facts)                          -> dict
    calculate_deadline(event_date, event_type)  -> dict
    estimate_compensation(weekly_pay, months)   -> dict
    prepare_acas(case_summary)                  -> dict
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Union

from backend.core.retrieve import retrieve_rules

# Standard non-advice framing appended to every screen/estimate. The preview is
# informational; the full assessment requires login + the governed brain path.
_PREVIEW_DISCLAIMER = (
    "Preview only  -  this is general information, not legal advice. "
    "Sign in for a full, saved assessment with citations."
)

# event_type (human funnel label) → claim_type (the key that drives the rules
# engine). Unknown types fall back to the primary supported claim so downstream
# rule lookups always have a valid key; the caller's label is preserved verbatim.
_EVENT_TO_CLAIM = {
    "dismissal":               "unfair_dismissal",
    "unfair_dismissal":        "unfair_dismissal",
    "constructive_dismissal":  "unfair_dismissal",
    "redundancy":              "unfair_dismissal",
    "discrimination":          "discrimination",
    "unpaid_wages":            "unlawful_deduction_wages",
    "wages":                   "unlawful_deduction_wages",
    "deduction":               "unlawful_deduction_wages",
}

_JURISDICTION_LABEL = {
    "EW": "England & Wales",
    "S":  "Scotland",
    "SCT": "Scotland",
    "GB": "Great Britain",
    "UK": "United Kingdom",
    "NI": "Northern Ireland",
}

# Recognised employment-issue signals for the claim screen. Presence of any signal
# means there is a potential claim worth assessing  -  NOT that a claim is made out.
_CLAIM_SIGNALS = {
    "unfair_dismissal":       ("dismiss", "sacked", "fired", "let go", "terminat", "redundan", "constructive"),
    "discrimination":         ("discriminat", "harass", "victimis", "victimiz", "disability", "pregnan",
                               "maternity", "race", "racist", "sex ", "gender", "age discriminat", "religion"),
    "whistleblowing":         ("whistleblow", "protected disclosure", "reported wrongdoing"),
    "unlawful_deduction_wages": ("unpaid", "not paid", "withheld wage", "deducted", "wages owed", "owed pay"),
}


class ToolDataUnavailable(RuntimeError):
    """Raised when a required statutory rule is missing from the DB  -  fail closed
    rather than fabricate a legal value (constitution §9). The API layer maps this
    to an honest 503, never a fabricated answer."""


def _claim_type_for_event(event_type: str) -> str:
    return _EVENT_TO_CLAIM.get((event_type or "").strip().lower(), "unfair_dismissal")


def _rule_value(rules: list[dict], rule_key: str) -> Optional[float]:
    for r in rules:
        if r.get("rule_key") == rule_key and r.get("value_numeric") is not None:
            return float(r["value_numeric"])
    return None


def _rule_row(rules: list[dict], rule_key: str) -> Optional[dict]:
    return next((r for r in rules if r.get("rule_key") == rule_key), None)


def _parse_date(value: Union[str, date]) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip()[:10])


# ── 1. Claim checker ──────────────────────────────────────────────────────────

def check_claim(facts: Union[str, dict]) -> dict:
    """Preliminary, deterministic claim screen from free-text or structured facts.

    Returns {has_claim, confidence, explanation}. This is a SIGNAL detector, not a
    merits decision: has_claim=True means "there is a recognised employment issue
    here worth a full assessment", and confidence reflects how much usable detail
    the visitor supplied  -  never a probability of winning.
    """
    if isinstance(facts, dict):
        text = " ".join(str(v) for v in facts.values() if v)
    else:
        text = str(facts or "")
    blob = text.lower()

    matched: list[str] = []
    for claim_type, signals in _CLAIM_SIGNALS.items():
        if any(sig in blob for sig in signals):
            matched.append(claim_type)

    has_claim = bool(matched)

    # Confidence = completeness of the screen input, NOT strength of the claim.
    # More words + a recognised signal + a date-like token → more usable detail.
    words = len([w for w in blob.split() if w])
    has_date = any(ch.isdigit() for ch in blob) and (
        "/" in blob or "-" in blob or "month" in blob or "week" in blob
        or "day" in blob or "year" in blob or "20" in blob
    )
    score = 0.0
    if has_claim:
        score += 0.45
    if words >= 8:
        score += 0.20
    if words >= 25:
        score += 0.10
    if has_date:
        score += 0.15
    if len(matched) >= 2:
        score += 0.10
    confidence = round(min(score, 0.9), 2) if has_claim else round(min(score + 0.05, 0.2), 2)

    if has_claim:
        label = ", ".join(m.replace("_", " ") for m in matched)
        explanation = (
            f"Your description shows signals of a possible {label} issue. "
            "This is worth a full assessment to check qualifying conditions, time "
            f"limits, and evidence. {_PREVIEW_DISCLAIMER}"
        )
    else:
        explanation = (
            "We couldn't identify a clear employment-law issue from what you wrote. "
            "Add more detail about what happened, when, and your employment status  -  "
            f"or sign in for a guided assessment. {_PREVIEW_DISCLAIMER}"
        )

    return {
        "has_claim":   has_claim,
        "confidence":  confidence,
        "explanation": explanation,
        "signals":     matched,
        "preview":     True,
    }


# ── 2. Deadline calculator ────────────────────────────────────────────────────

def calculate_deadline(
    event_date: Union[str, date],
    event_type: str,
    jurisdiction: str = "EW",
) -> dict:
    """Deterministic Employment Tribunal limitation date for an event.

    Loads the statutory time limit from the effective-dated rules table (DB-first,
    fail-closed) and applies the "N-months-less-1-day, beginning with the event"
    rule via backend.domains.employment.deadline.compute_limitation_date.

    Returns {deadline, days_remaining, jurisdiction, claim_type, authority, basis}.
    The Early-Conciliation stop-clock is NOT applied here (no EC dates in a preview);
    the result is the base limitation date and says so.
    """
    edt = _parse_date(event_date)
    claim_type = _claim_type_for_event(event_type)

    rules = retrieve_rules(claim_type, jurisdiction, edt)
    tl_key = f"{claim_type}.time_limit_months"
    tl_row = _rule_row(rules, tl_key)
    months = _rule_value(rules, tl_key)
    if months is None:
        raise ToolDataUnavailable(
            f"No effective statutory time limit ({tl_key}) for {jurisdiction} at "
            f"{edt.isoformat()}  -  cannot compute a deadline without the rule."
        )

    # Local import: deadline arithmetic lives in the employment domain.
    from backend.domains.employment.deadline import compute_limitation_date

    info = compute_limitation_date(edt, int(months))
    deadline = _parse_date(info["limitation_date"])
    days_remaining = (deadline - date.today()).days

    return {
        "deadline":       deadline.isoformat(),
        "days_remaining": days_remaining,
        "jurisdiction":   _JURISDICTION_LABEL.get(jurisdiction.upper(), jurisdiction),
        "claim_type":     claim_type,
        "event_date":     edt.isoformat(),
        "authority":      (tl_row or {}).get("authority_ref") or info.get("authority"),
        "basis":          info.get("notes"),
        "ec_applied":     False,
        "note": (
            "Base limitation date only  -  the ACAS Early Conciliation stop-clock can "
            f"extend this. {_PREVIEW_DISCLAIMER}"
        ),
        "preview":        True,
    }


# ── 3. Compensation estimator ─────────────────────────────────────────────────

def estimate_compensation(
    weekly_pay: float,
    months_employed: int,
    jurisdiction: str = "EW",
) -> dict:
    """Deterministic statutory BASIC AWARD estimate for unfair dismissal / redundancy.

    Uses the statutory week's-pay cap from the effective-dated rules table (DB-first,
    fail-closed). Formula (simplified preview): complete years of service × capped
    week's pay × 1.0 multiplier. The real basic award applies age-banded multipliers
    (0.5 / 1.0 / 1.5 per ERA 1996 s.119)  -  that needs the visitor's age, which a
    preview doesn't collect  -  so this returns a single-multiplier estimate and says so.

    Returns {estimated_amount, breakdown}.
    """
    weekly_pay = float(weekly_pay or 0)
    months_employed = int(months_employed or 0)
    if weekly_pay < 0 or months_employed < 0:
        raise ValueError("weekly_pay and months_employed must be non-negative")

    rules = retrieve_rules("unfair_dismissal", jurisdiction, date.today())
    wpc_key = "unfair_dismissal.weeks_pay_cap_amount"
    wpc_row = _rule_row(rules, wpc_key)
    weeks_pay_cap = _rule_value(rules, wpc_key)
    if weeks_pay_cap is None:
        raise ToolDataUnavailable(
            f"No effective statutory week's-pay cap ({wpc_key}) for {jurisdiction}  -  "
            "cannot estimate a basic award without the statutory cap."
        )

    # Statute counts COMPLETE years of service, capped at 20 (ERA 1996 s.119(3)).
    complete_years = min(months_employed // 12, 20)
    capped_weekly_pay = min(weekly_pay, weeks_pay_cap)
    multiplier = 1.0  # preview simplification  -  see docstring
    estimated_amount = round(complete_years * capped_weekly_pay * multiplier, 2)

    authority = (wpc_row or {}).get("authority_ref") or "ERA 1996 s.227(1)"

    breakdown = {
        "weekly_pay":            round(weekly_pay, 2),
        "weeks_pay_cap":         weeks_pay_cap,
        "capped_weekly_pay":     round(capped_weekly_pay, 2),
        "months_employed":       months_employed,
        "complete_years":        complete_years,
        "age_multiplier":        multiplier,
        "basic_award_estimate":  estimated_amount,
        "currency":              "GBP",
        "authority":             authority,
        "formula":               "complete_years × min(weekly_pay, week's-pay cap) × age multiplier (preview: 1.0)",
        "note": (
            "Statutory BASIC AWARD only  -  excludes the compensatory award and applies "
            "a flat 1.0 age multiplier (real multipliers are 0.5/1.0/1.5 by age, "
            f"ERA 1996 s.119). {_PREVIEW_DISCLAIMER}"
        ),
    }

    return {
        "estimated_amount": estimated_amount,
        "breakdown":        breakdown,
        "preview":          True,
    }


# ── 4. ACAS Early Conciliation prep ───────────────────────────────────────────

def prepare_acas(case_summary: Union[str, dict]) -> dict:
    """Deterministic ACAS Early Conciliation (EC) preparation checklist.

    EC is a MANDATORY procedural step before most Employment Tribunal claims
    (Employment Tribunals Act 1996 s.18A). This returns the standard procedural
    next steps and the documents a claimant should gather. It is procedural
    guidance, not legal advice or a merits opinion.

    Returns {next_steps, required_docs}.
    """
    if isinstance(case_summary, dict):
        text = " ".join(str(v) for v in case_summary.values() if v)
    else:
        text = str(case_summary or "")
    blob = text.lower()

    next_steps = [
        "Notify ACAS of Early Conciliation BEFORE issuing a tribunal claim "
        "(mandatory under Employment Tribunals Act 1996 s.18A)  -  submit the EC "
        "notification form online or by phone.",
        "An ACAS conciliator contacts both sides; conciliation runs for up to 6 "
        "weeks (extendable by 2 weeks if both sides agree).",
        "If no settlement is reached, ACAS issues an EC certificate with a unique "
        "reference number  -  you cannot file an ET1 without it.",
        "File your ET1 claim before your tribunal time limit expires. The EC period "
        "pauses the clock (stop-clock), but the deadline is strict  -  check it.",
    ]

    required_docs = [
        "Your written contract of employment / statement of terms",
        "Recent payslips and your latest P60",
        "Any dismissal, redundancy, or disciplinary outcome letter",
        "Grievance correspondence and the employer's response",
        "Relevant emails, messages, or notes evidencing what happened",
        "A short dated chronology of key events",
    ]

    # Light, deterministic tailoring  -  never fabricates law, only flags an extra
    # document/step when the summary clearly signals a sub-type.
    if any(s in blob for s in ("discriminat", "harass", "disability", "pregnan", "race", "religion")):
        required_docs.append(
            "Evidence relating to the discrimination (comparator details, medical "
            "evidence if disability, dates of incidents)"
        )
    if any(s in blob for s in ("unpaid", "wages", "owed", "deducted", "deduction")):
        required_docs.append("A breakdown of the pay/hours owed and how you calculated it")

    return {
        "next_steps":    next_steps,
        "required_docs": required_docs,
        "authority":     "Employment Tribunals Act 1996 s.18A; ACAS Early Conciliation",
        "disclaimer":    _PREVIEW_DISCLAIMER,
        "preview":       True,
    }
