"""Production-scoped employment assessment dispatcher.

This module is intentionally small. LawApp's real legal scope comes from the
domain registry, DB-backed rules, and retrieved authorities. It must not contain
or expose aspirational employment-law modules that are not DB-proven.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta

from backend.domains.employment.modules import production_module_keys


ASSESSMENT_HANDLERS = {
    "unfair_dismissal": "assess_unfair_dismissal",
    "unpaid_wages": "assess_unpaid_wages",
    "wrongful_dismissal": "assess_wrongful_dismissal",
    "redundancy": "assess_redundancy",
    "working_time": "assess_working_time",
    "holiday_pay": "assess_holiday_pay",
    "flexible_working": "assess_flexible_working",
    "employment_contracts": "assess_employment_contracts",
    "fixed_term_workers": "assess_fixed_term_workers",
    "part_time_workers": "assess_part_time_workers",
    "agency_workers": "assess_agency_workers",
}
assert sorted(ASSESSMENT_HANDLERS) == sorted(production_module_keys())


def _missing_rules(claim_type: str, keys: list[str]) -> dict[str, Any]:
    return {
        "viable_claim": None,
        "claim_type": claim_type,
        "reason": "Required rules missing from DB-backed authority bundle",
        "missing_rules": keys,
        "confidence": 0.0,
        "confidence_score": 0.0,
        "grounding_score": 0.0,
        "insufficient_grounding": True,
        "citations": [],
    }


def _require_rules(claim_type: str, rules: dict[str, Any], keys: tuple[str, ...]) -> dict[str, float] | dict[str, Any]:
    missing = [key for key in keys if rules.get(key) is None]
    if missing:
        return _missing_rules(claim_type, missing)
    return {key: float(rules[key]) for key in keys}


def _require_present_rules(claim_type: str, rules: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    missing = [key for key in keys if rules.get(key) is None]
    if missing:
        return _missing_rules(claim_type, missing)
    return {key: rules[key] for key in keys}


def _years_service(facts: dict[str, Any], end_date: datetime) -> float:
    if facts.get("years_service") is not None:
        return max(0.0, float(facts["years_service"]))
    start_value = facts.get("employment_start_date") or facts.get("service_start_date")
    if not start_value:
        raise ValueError("years_service or employment_start_date required")
    start_date = datetime.fromisoformat(str(start_value))
    return max(0.0, (end_date.date() - start_date.date()).days / 365.2425)


def _citation(cite: str, url: str) -> dict[str, str]:
    return {"cite": cite, "url": url}


def assess_case(claim_type: str, facts: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    if facts is None or not isinstance(facts, dict):
        return {"viable_claim": None, "claim_type": claim_type, "error": "facts must be a non-empty dictionary"}
    if not facts:
        return {"viable_claim": None, "claim_type": claim_type, "error": "facts cannot be empty"}

    handler_name = ASSESSMENT_HANDLERS.get(claim_type)
    if not handler_name:
        return {
            "viable_claim": None,
            "claim_type": claim_type,
            "error": f"Claim type '{claim_type}' not supported yet",
            "supported_types": production_module_keys(),
        }

    return globals()[handler_name](facts, rules)


def assess_unfair_dismissal(facts: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    required = _require_rules(
        "unfair_dismissal",
        rules,
        (
            "qualifying_period_months",
            "time_limit_months",
            "weeks_pay_cap_amount",
            "basic_award_min",
            "compensatory_cap_amount",
        ),
    )
    if "missing_rules" in required:
        return required

    try:
        edt = datetime.fromisoformat(str(facts.get("dismissal_date", "")))
        start_value = facts.get("employment_start_date") or facts.get("service_start_date")
        if facts.get("years_service") is not None:
            years_service = float(facts["years_service"])
        elif start_value:
            start_date = datetime.fromisoformat(str(start_value))
            years_service = max(0.0, (edt.date() - start_date.date()).days / 365.2425)
        else:
            raise ValueError("years_service or employment_start_date required")
        gross_weekly = float(facts.get("gross_weekly_pay", 0))
        age = int(facts.get("age", 0))
    except (TypeError, ValueError) as exc:
        return {
            "viable_claim": False,
            "claim_type": "unfair_dismissal",
            "reason": f"Invalid facts: {exc}",
            "confidence": 0.0,
            "confidence_score": 0.0,
            "grounding_score": 0.0,
            "insufficient_grounding": True,
            "citations": [],
        }

    qualifying_years = required["qualifying_period_months"] / 12
    deadline = (
        edt
        + relativedelta(months=int(required["time_limit_months"]))
        - timedelta(days=1)
    ).date().isoformat()
    deadline_info = {"limitation_date": deadline, "source": "rules", "authority": "ERA 1996 s.111(2)"}

    if years_service < qualifying_years:
        return {
            "viable_claim": False,
            "claim_type": "unfair_dismissal",
            "reason": f"Does not meet qualifying period ({qualifying_years:g} years required)",
            "confidence": 0.95,
            "confidence_score": 0.95,
            "grounding_score": 0.9,
            "insufficient_grounding": False,
            "qualifying_period_failure": True,
            "service_years": round(years_service, 2),
            "deadline": deadline,
            "deadline_info": deadline_info,
            "citations": [
                {"cite": "ERA 1996 s.108", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/108"},
                {"cite": "ERA 1996 s.111(2)", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/111"},
            ],
        }

    years_for_award = min(int(years_service), 20)
    multiplier = 1.5 if age >= 41 else (1.0 if age >= 22 else 0.5)
    basic = years_for_award * multiplier * min(gross_weekly, required["weeks_pay_cap_amount"])
    basic = max(basic, required["basic_award_min"])
    comp = min(gross_weekly * 52, required["compensatory_cap_amount"])

    return {
        "viable_claim": True,
        "claim_type": "unfair_dismissal",
        "jurisdiction": "EW",
        "strength": "strong" if years_service >= 3 else "moderate",
        "confidence": 0.85,
        "confidence_score": 0.85,
        "grounding_score": 0.9,
        "insufficient_grounding": False,
        "service_years": round(years_service, 2),
        "deadline": deadline,
        "deadline_info": deadline_info,
        "estimated_basic_award": round(basic, 2),
        "estimated_compensatory": round(comp, 2),
        "estimated_total": round(basic + comp, 2),
        "citations": [
            {"cite": "ERA 1996 s.94", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/94"},
            {"cite": "ERA 1996 s.98", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/98"},
            {"cite": "ERA 1996 s.119", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/119"},
            {"cite": "ERA 1996 s.123", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/123"},
        ],
    }


def assess_unpaid_wages(facts: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    required = _require_rules("unpaid_wages", rules, ("time_limit_months",))
    if "missing_rules" in required:
        return required

    try:
        amount_owed = float(facts.get("amount_owed", 0))
        last_payment_date = datetime.fromisoformat(str(facts.get("last_payment_date", "")))
    except (TypeError, ValueError) as exc:
        return {
            "viable_claim": False,
            "claim_type": "unpaid_wages",
            "reason": f"Invalid facts: {exc}",
            "confidence": 0.0,
            "confidence_score": 0.0,
            "grounding_score": 0.0,
            "insufficient_grounding": True,
            "citations": [],
        }

    deadline = (
        last_payment_date
        + relativedelta(months=int(required["time_limit_months"]))
        - timedelta(days=1)
    ).date().isoformat()
    return {
        "viable_claim": amount_owed > 0,
        "claim_type": "unpaid_wages",
        "jurisdiction": "EW",
        "strength": "strong" if amount_owed >= 5000 else "moderate",
        "confidence": 0.9,
        "confidence_score": 0.9,
        "grounding_score": 0.9,
        "insufficient_grounding": False,
        "amount_owed": amount_owed,
        "deadline": deadline,
        "deadline_info": {"limitation_date": deadline, "source": "rules", "authority": "ERA 1996 s.23"},
        "citations": [{"cite": "ERA 1996 s.13"}, {"cite": "ERA 1996 s.23"}],
    }


def assess_wrongful_dismissal(facts: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    required = _require_rules(
        "wrongful_dismissal",
        rules,
        (
            "notice_qualifying_period_months",
            "max_statutory_notice_weeks",
            "et_time_limit_months",
        ),
    )
    if "missing_rules" in required:
        return required

    try:
        termination = datetime.fromisoformat(
            str(facts.get("termination_date") or facts.get("dismissal_date") or facts.get("edt") or "")
        )
        years_service = _years_service(facts, termination)
        weekly_pay = float(facts.get("gross_weekly_pay") or facts.get("weekly_pay") or 0)
        notice_given = float(facts.get("notice_given_weeks") or 0)
        contractual_notice = facts.get("contractual_notice_weeks")
        contractual_notice_weeks = float(contractual_notice) if contractual_notice is not None else None
    except (TypeError, ValueError) as exc:
        return {
            "viable_claim": False,
            "claim_type": "wrongful_dismissal",
            "reason": f"Invalid facts: {exc}",
            "confidence": 0.0,
            "confidence_score": 0.0,
            "grounding_score": 0.0,
            "insufficient_grounding": True,
            "citations": [],
        }

    service_months = years_service * 12
    if service_months < required["notice_qualifying_period_months"]:
        statutory_notice = 0.0
    elif years_service < 2:
        statutory_notice = 1.0
    else:
        statutory_notice = min(float(int(years_service)), required["max_statutory_notice_weeks"])

    required_notice = max(statutory_notice, contractual_notice_weeks or 0.0)
    shortfall_weeks = max(0.0, required_notice - notice_given)
    estimated_notice_pay = round(shortfall_weeks * weekly_pay, 2)
    deadline = (
        termination
        + relativedelta(months=int(required["et_time_limit_months"]))
        - timedelta(days=1)
    ).date().isoformat()

    return {
        "viable_claim": shortfall_weeks > 0,
        "claim_type": "wrongful_dismissal",
        "jurisdiction": "EW",
        "strength": "strong" if shortfall_weeks >= 2 else ("moderate" if shortfall_weeks > 0 else "low"),
        "confidence": 0.86,
        "confidence_score": 0.86,
        "grounding_score": 0.9,
        "insufficient_grounding": False,
        "service_years": round(years_service, 2),
        "statutory_notice_weeks": statutory_notice,
        "required_notice_weeks": required_notice,
        "notice_given_weeks": notice_given,
        "notice_shortfall_weeks": shortfall_weeks,
        "estimated_notice_pay": estimated_notice_pay,
        "deadline": deadline,
        "deadline_info": {
            "limitation_date": deadline,
            "source": "rules",
            "authority": "Employment Tribunals Extension of Jurisdiction Order 1994 arts.3,7",
        },
        "reason": (
            "Potential notice-pay shortfall based on statutory/contractual notice."
            if shortfall_weeks > 0
            else "No notice-pay shortfall appears from the supplied facts."
        ),
        "citations": [
            _citation("ERA 1996 s.86", "https://www.legislation.gov.uk/ukpga/1996/18/section/86"),
            _citation("Employment Tribunals Extension of Jurisdiction Order 1994 arts.3,7", "https://www.legislation.gov.uk/uksi/1994/1623"),
        ],
    }


def assess_redundancy(facts: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    required = _require_rules(
        "redundancy",
        rules,
        (
            "qualifying_period_years",
            "time_limit_months",
            "weeks_pay_cap_amount",
            "max_years_counted",
            "multiplier_under_22",
            "multiplier_22_to_40",
            "multiplier_41_plus",
        ),
    )
    if "missing_rules" in required:
        return required

    try:
        dismissal = datetime.fromisoformat(str(facts.get("dismissal_date") or facts.get("edt") or ""))
        years_service = _years_service(facts, dismissal)
        age = int(facts.get("age", 0))
        weekly_pay = float(facts.get("gross_weekly_pay") or facts.get("weekly_pay") or 0)
    except (TypeError, ValueError) as exc:
        return {
            "viable_claim": False,
            "claim_type": "redundancy",
            "reason": f"Invalid facts: {exc}",
            "confidence": 0.0,
            "confidence_score": 0.0,
            "grounding_score": 0.0,
            "insufficient_grounding": True,
            "citations": [],
        }

    qualifying_years = required["qualifying_period_years"]
    deadline = (
        dismissal
        + relativedelta(months=int(required["time_limit_months"]))
        - timedelta(days=1)
    ).date().isoformat()
    deadline_info = {"limitation_date": deadline, "source": "rules", "authority": "ERA 1996 s.164"}

    if years_service < qualifying_years:
        return {
            "viable_claim": False,
            "claim_type": "redundancy",
            "jurisdiction": "EW",
            "strength": "low",
            "confidence": 0.92,
            "confidence_score": 0.92,
            "grounding_score": 0.9,
            "insufficient_grounding": False,
            "service_years": round(years_service, 2),
            "deadline": deadline,
            "deadline_info": deadline_info,
            "reason": f"Does not meet statutory redundancy-payment qualifying period ({qualifying_years:g} years required).",
            "citations": [
                _citation("ERA 1996 s.155", "https://www.legislation.gov.uk/ukpga/1996/18/section/155"),
                _citation("ERA 1996 s.164", "https://www.legislation.gov.uk/ukpga/1996/18/section/164"),
            ],
        }

    years_for_payment = min(int(years_service), int(required["max_years_counted"]))
    capped_weekly_pay = min(weekly_pay, required["weeks_pay_cap_amount"])
    redundancy_weeks = 0.0
    for completed_year_offset in range(years_for_payment):
        age_in_year = age - completed_year_offset
        if age_in_year >= 41:
            redundancy_weeks += required["multiplier_41_plus"]
        elif age_in_year >= 22:
            redundancy_weeks += required["multiplier_22_to_40"]
        else:
            redundancy_weeks += required["multiplier_under_22"]
    statutory_payment = round(redundancy_weeks * capped_weekly_pay, 2)

    return {
        "viable_claim": statutory_payment > 0,
        "claim_type": "redundancy",
        "jurisdiction": "EW",
        "strength": "moderate",
        "confidence": 0.86,
        "confidence_score": 0.86,
        "grounding_score": 0.9,
        "insufficient_grounding": False,
        "service_years": round(years_service, 2),
        "years_counted_for_payment": years_for_payment,
        "redundancy_weeks": redundancy_weeks,
        "weekly_pay_cap_amount": required["weeks_pay_cap_amount"],
        "capped_weekly_pay": capped_weekly_pay,
        "estimated_statutory_redundancy_payment": statutory_payment,
        "deadline": deadline,
        "deadline_info": deadline_info,
        "reason": "Potential statutory redundancy payment based on age, service and capped weekly pay.",
        "citations": [
            _citation("ERA 1996 s.135", "https://www.legislation.gov.uk/ukpga/1996/18/section/135"),
            _citation("ERA 1996 s.139", "https://www.legislation.gov.uk/ukpga/1996/18/section/139"),
            _citation("ERA 1996 s.155", "https://www.legislation.gov.uk/ukpga/1996/18/section/155"),
            _citation("ERA 1996 s.162", "https://www.legislation.gov.uk/ukpga/1996/18/section/162"),
            _citation("ERA 1996 s.164", "https://www.legislation.gov.uk/ukpga/1996/18/section/164"),
        ],
    }


def assess_working_time(facts: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    required = _require_rules(
        "working_time",
        rules,
        (
            "max_weekly_hours",
            "daily_rest_hours",
            "weekly_rest_hours",
            "rest_break_minutes",
            "rest_break_trigger_hours",
        ),
    )
    if "missing_rules" in required:
        return required

    try:
        weekly_hours = float(facts.get("average_weekly_hours", 0))
        daily_rest = float(facts.get("daily_rest_hours", required["daily_rest_hours"]))
        weekly_rest = float(facts.get("weekly_rest_hours", required["weekly_rest_hours"]))
        shift_hours = float(facts.get("shift_hours", 0))
        break_minutes = float(facts.get("rest_break_minutes", required["rest_break_minutes"]))
        opted_out = bool(facts.get("signed_48_hour_opt_out", False))
    except (TypeError, ValueError) as exc:
        return {
            "viable_claim": False,
            "claim_type": "working_time",
            "reason": f"Invalid facts: {exc}",
            "confidence": 0.0,
            "confidence_score": 0.0,
            "grounding_score": 0.0,
            "insufficient_grounding": True,
            "citations": [],
        }

    violations: list[str] = []
    if weekly_hours > required["max_weekly_hours"] and not opted_out:
        violations.append("weekly_hours_above_48_without_opt_out")
    if daily_rest < required["daily_rest_hours"]:
        violations.append("daily_rest_below_required_hours")
    if weekly_rest < required["weekly_rest_hours"]:
        violations.append("weekly_rest_below_required_hours")
    if shift_hours > required["rest_break_trigger_hours"] and break_minutes < required["rest_break_minutes"]:
        violations.append("rest_break_below_required_minutes")

    return {
        "viable_claim": bool(violations),
        "claim_type": "working_time",
        "jurisdiction": "EW",
        "strength": "moderate" if violations else "low",
        "confidence": 0.84,
        "confidence_score": 0.84,
        "grounding_score": 0.9,
        "insufficient_grounding": False,
        "violations": violations,
        "thresholds": {
            "max_weekly_hours": required["max_weekly_hours"],
            "daily_rest_hours": required["daily_rest_hours"],
            "weekly_rest_hours": required["weekly_rest_hours"],
            "rest_break_trigger_hours": required["rest_break_trigger_hours"],
            "rest_break_minutes": required["rest_break_minutes"],
        },
        "reason": (
            "Potential Working Time Regulations breach based on supplied hours/rest facts."
            if violations else "No Working Time Regulations breach appears from the supplied hours/rest facts."
        ),
        "citations": [
            _citation("Working Time Regulations 1998 reg.4", "https://www.legislation.gov.uk/uksi/1998/1833/regulation/4"),
            _citation("Working Time Regulations 1998 reg.10", "https://www.legislation.gov.uk/uksi/1998/1833/regulation/10"),
            _citation("Working Time Regulations 1998 reg.11", "https://www.legislation.gov.uk/uksi/1998/1833/regulation/11"),
            _citation("Working Time Regulations 1998 reg.12", "https://www.legislation.gov.uk/uksi/1998/1833/regulation/12"),
        ],
    }


def assess_holiday_pay(facts: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    required = _require_rules(
        "holiday_pay",
        rules,
        (
            "annual_leave_weeks",
            "additional_leave_weeks",
            "total_annual_leave_weeks",
        ),
    )
    if "missing_rules" in required:
        return required

    try:
        leave_taken = float(facts.get("annual_leave_taken_weeks", 0))
        weekly_pay = float(facts.get("weekly_pay") or facts.get("gross_weekly_pay") or 0)
        untaken_leave = facts.get("untaken_leave_weeks")
        untaken_leave_weeks = float(untaken_leave) if untaken_leave is not None else max(0.0, required["total_annual_leave_weeks"] - leave_taken)
        employment_ended = bool(facts.get("employment_ended", False))
    except (TypeError, ValueError) as exc:
        return {
            "viable_claim": False,
            "claim_type": "holiday_pay",
            "reason": f"Invalid facts: {exc}",
            "confidence": 0.0,
            "confidence_score": 0.0,
            "grounding_score": 0.0,
            "insufficient_grounding": True,
            "citations": [],
        }

    leave_shortfall = round(max(0.0, required["total_annual_leave_weeks"] - leave_taken), 2)
    estimated_untaken_pay = round(untaken_leave_weeks * weekly_pay, 2) if weekly_pay else None
    viable = leave_shortfall > 0 or (employment_ended and untaken_leave_weeks > 0)

    return {
        "viable_claim": viable,
        "claim_type": "holiday_pay",
        "jurisdiction": "EW",
        "strength": "moderate" if viable else "low",
        "confidence": 0.84,
        "confidence_score": 0.84,
        "grounding_score": 0.9,
        "insufficient_grounding": False,
        "annual_leave_entitlement_weeks": required["total_annual_leave_weeks"],
        "regulation_13_leave_weeks": required["annual_leave_weeks"],
        "additional_leave_weeks": required["additional_leave_weeks"],
        "annual_leave_taken_weeks": leave_taken,
        "leave_shortfall_weeks": leave_shortfall,
        "untaken_leave_weeks": untaken_leave_weeks,
        "estimated_untaken_holiday_pay": estimated_untaken_pay,
        "reason": (
            "Potential holiday-pay/annual-leave issue based on entitlement and leave taken."
            if viable else "No holiday-pay/annual-leave shortfall appears from the supplied facts."
        ),
        "citations": [
            _citation("Working Time Regulations 1998 reg.13", "https://www.legislation.gov.uk/uksi/1998/1833/regulation/13"),
            _citation("Working Time Regulations 1998 reg.13A", "https://www.legislation.gov.uk/uksi/1998/1833/regulation/13A"),
            _citation("Working Time Regulations 1998 reg.14", "https://www.legislation.gov.uk/uksi/1998/1833/regulation/14"),
            _citation("Working Time Regulations 1998 reg.30", "https://www.legislation.gov.uk/uksi/1998/1833/regulation/30"),
        ],
    }


def assess_flexible_working(facts: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    required = _require_rules(
        "flexible_working",
        rules,
        (
            "day_one_application_right",
            "max_requests_per_12_months",
            "decision_period_months",
        ),
    )
    if "missing_rules" in required:
        return required

    try:
        requests_last_12_months = int(facts.get("requests_last_12_months", 0))
        refused = bool(facts.get("refused", False))
        consulted = bool(facts.get("consulted_before_refusal", True))
        request_date_raw = facts.get("request_date")
        decision_date_raw = facts.get("decision_date")
        request_date = datetime.fromisoformat(str(request_date_raw)) if request_date_raw else None
        decision_date = datetime.fromisoformat(str(decision_date_raw)) if decision_date_raw else None
    except (TypeError, ValueError) as exc:
        return {
            "viable_claim": False,
            "claim_type": "flexible_working",
            "reason": f"Invalid facts: {exc}",
            "confidence": 0.0,
            "confidence_score": 0.0,
            "grounding_score": 0.0,
            "insufficient_grounding": True,
            "citations": [],
        }

    eligible_to_apply = requests_last_12_months < required["max_requests_per_12_months"]
    decision_due_date = None
    decision_overdue = False
    if request_date:
        decision_due_date = (
            request_date
            + relativedelta(months=int(required["decision_period_months"]))
            - timedelta(days=1)
        ).date().isoformat()
        if decision_date:
            decision_overdue = decision_date.date().isoformat() > decision_due_date

    breach_reasons: list[str] = []
    if refused and not consulted:
        breach_reasons.append("refused_without_required_consultation")
    if decision_overdue:
        breach_reasons.append("decision_outside_statutory_period")

    return {
        "viable_claim": bool(breach_reasons),
        "claim_type": "flexible_working",
        "jurisdiction": "EW",
        "strength": "moderate" if breach_reasons else "low",
        "confidence": 0.83,
        "confidence_score": 0.83,
        "grounding_score": 0.9,
        "insufficient_grounding": False,
        "eligible_to_apply": eligible_to_apply,
        "requests_last_12_months": requests_last_12_months,
        "max_requests_per_12_months": required["max_requests_per_12_months"],
        "decision_period_months": required["decision_period_months"],
        "decision_due_date": decision_due_date,
        "breach_reasons": breach_reasons,
        "reason": (
            "Potential flexible-working procedure breach based on the supplied facts."
            if breach_reasons else "No flexible-working procedure breach appears from the supplied facts."
        ),
        "citations": [
            _citation("ERA 1996 s.80F", "https://www.legislation.gov.uk/ukpga/1996/18/section/80F"),
            _citation("ERA 1996 s.80G", "https://www.legislation.gov.uk/ukpga/1996/18/section/80G"),
            _citation("ERA 1996 s.80H", "https://www.legislation.gov.uk/ukpga/1996/18/section/80H"),
        ],
    }


def assess_employment_contracts(facts: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    numeric = _require_rules("employment_contracts", rules, ("day_one_particulars_anchor",))
    present = _require_present_rules(
        "employment_contracts",
        rules,
        (
            "written_particulars_right",
            "tribunal_reference_route",
            "section_38_award_anchor",
        ),
    )
    if "missing_rules" in numeric:
        return numeric
    if "missing_rules" in present:
        return present

    received_statement = bool(facts.get("received_written_statement", False))
    days_after_start = facts.get("days_after_start_received")
    try:
        days_after_start_received = float(days_after_start) if days_after_start is not None else None
    except (TypeError, ValueError) as exc:
        return {
            "viable_claim": False,
            "claim_type": "employment_contracts",
            "reason": f"Invalid facts: {exc}",
            "confidence": 0.0,
            "confidence_score": 0.0,
            "grounding_score": 0.0,
            "insufficient_grounding": True,
            "citations": [],
        }

    breach_reasons: list[str] = []
    if not received_statement:
        breach_reasons.append("written_statement_not_received")
    elif days_after_start_received is not None and days_after_start_received > numeric["day_one_particulars_anchor"]:
        breach_reasons.append("written_statement_not_provided_day_one")

    return {
        "viable_claim": bool(breach_reasons),
        "claim_type": "employment_contracts",
        "jurisdiction": "EW",
        "strength": "moderate" if breach_reasons else "low",
        "confidence": 0.83,
        "confidence_score": 0.83,
        "grounding_score": 0.9,
        "insufficient_grounding": False,
        "breach_reasons": breach_reasons,
        "day_one_particulars_anchor": numeric["day_one_particulars_anchor"],
        "reason": (
            "Potential written-particulars issue based on the supplied facts."
            if breach_reasons else "No written-particulars breach appears from the supplied facts."
        ),
        "citations": [
            _citation("ERA 1996 s.1", "https://www.legislation.gov.uk/ukpga/1996/18/section/1"),
            _citation("ERA 1996 s.11", "https://www.legislation.gov.uk/ukpga/1996/18/section/11"),
            _citation("Employment Act 2002 s.38", "https://www.legislation.gov.uk/ukpga/2002/22/section/38"),
        ],
    }


def assess_fixed_term_workers(facts: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    numeric = _require_rules("fixed_term_workers", rules, ("successive_contracts_years",))
    present = _require_present_rules(
        "fixed_term_workers",
        rules,
        ("less_favourable_treatment_right", "objective_justification_anchor"),
    )
    if "missing_rules" in numeric:
        return numeric
    if "missing_rules" in present:
        return present

    try:
        successive_years = float(facts.get("successive_fixed_term_contract_years", 0))
    except (TypeError, ValueError) as exc:
        return {
            "viable_claim": False,
            "claim_type": "fixed_term_workers",
            "reason": f"Invalid facts: {exc}",
            "confidence": 0.0,
            "confidence_score": 0.0,
            "grounding_score": 0.0,
            "insufficient_grounding": True,
            "citations": [],
        }
    less_favourable = bool(facts.get("less_favourable_treatment", False))
    objective_justification = bool(facts.get("objective_justification_given", False))

    breach_reasons: list[str] = []
    if less_favourable and not objective_justification:
        breach_reasons.append("less_favourable_treatment_without_objective_justification")
    if successive_years >= numeric["successive_contracts_years"]:
        breach_reasons.append("successive_fixed_term_contracts_at_or_above_four_year_anchor")

    return {
        "viable_claim": bool(breach_reasons),
        "claim_type": "fixed_term_workers",
        "jurisdiction": "EW",
        "strength": "moderate" if breach_reasons else "low",
        "confidence": 0.82,
        "confidence_score": 0.82,
        "grounding_score": 0.9,
        "insufficient_grounding": False,
        "breach_reasons": breach_reasons,
        "successive_contracts_years_anchor": numeric["successive_contracts_years"],
        "reason": (
            "Potential fixed-term worker issue based on treatment or successive-contract facts."
            if breach_reasons else "No fixed-term worker breach appears from the supplied facts."
        ),
        "citations": [
            _citation("Fixed-term Employees Regulations 2002 reg.3", "https://www.legislation.gov.uk/uksi/2002/2034/regulation/3"),
            _citation("Fixed-term Employees Regulations 2002 reg.8", "https://www.legislation.gov.uk/uksi/2002/2034/regulation/8"),
        ],
    }


def assess_part_time_workers(facts: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    present = _require_present_rules(
        "part_time_workers",
        rules,
        (
            "less_favourable_treatment_right",
            "objective_justification_anchor",
            "complaint_route",
        ),
    )
    if "missing_rules" in present:
        return present

    less_favourable = bool(facts.get("less_favourable_treatment", False))
    comparable_full_time_worker = bool(facts.get("comparable_full_time_worker", False))
    objective_justification = bool(facts.get("objective_justification_given", False))
    viable = less_favourable and comparable_full_time_worker and not objective_justification

    return {
        "viable_claim": viable,
        "claim_type": "part_time_workers",
        "jurisdiction": "EW",
        "strength": "moderate" if viable else "low",
        "confidence": 0.82,
        "confidence_score": 0.82,
        "grounding_score": 0.9,
        "insufficient_grounding": False,
        "breach_reasons": ["less_favourable_treatment_without_objective_justification"] if viable else [],
        "reason": (
            "Potential part-time worker less-favourable-treatment issue."
            if viable else "No part-time worker breach appears from the supplied facts."
        ),
        "citations": [
            _citation("Part-time Workers Regulations 2000 reg.5", "https://www.legislation.gov.uk/uksi/2000/1551/regulation/5"),
            _citation("Part-time Workers Regulations 2000 reg.8", "https://www.legislation.gov.uk/uksi/2000/1551/regulation/8"),
        ],
    }


def assess_agency_workers(facts: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    numeric = _require_rules("agency_workers", rules, ("qualifying_period_weeks",))
    present = _require_present_rules(
        "agency_workers",
        rules,
        ("equal_treatment_after_qualifying_period", "tribunal_complaint_route"),
    )
    if "missing_rules" in numeric:
        return numeric
    if "missing_rules" in present:
        return present

    try:
        weeks_on_assignment = float(facts.get("weeks_on_assignment", 0))
    except (TypeError, ValueError) as exc:
        return {
            "viable_claim": False,
            "claim_type": "agency_workers",
            "reason": f"Invalid facts: {exc}",
            "confidence": 0.0,
            "confidence_score": 0.0,
            "grounding_score": 0.0,
            "insufficient_grounding": True,
            "citations": [],
        }
    less_favourable_basic_conditions = bool(facts.get("less_favourable_basic_conditions", False))
    qualifying_period_met = weeks_on_assignment >= numeric["qualifying_period_weeks"]
    viable = qualifying_period_met and less_favourable_basic_conditions

    return {
        "viable_claim": viable,
        "claim_type": "agency_workers",
        "jurisdiction": "EW",
        "strength": "moderate" if viable else "low",
        "confidence": 0.82,
        "confidence_score": 0.82,
        "grounding_score": 0.9,
        "insufficient_grounding": False,
        "weeks_on_assignment": weeks_on_assignment,
        "qualifying_period_weeks": numeric["qualifying_period_weeks"],
        "qualifying_period_met": qualifying_period_met,
        "breach_reasons": ["less_favourable_basic_conditions_after_qualifying_period"] if viable else [],
        "reason": (
            "Potential agency-worker equal-treatment issue after the qualifying period."
            if viable else "No agency-worker equal-treatment breach appears from the supplied facts."
        ),
        "citations": [
            _citation("Agency Workers Regulations 2010 reg.5", "https://www.legislation.gov.uk/uksi/2010/93/regulation/5"),
            _citation("Agency Workers Regulations 2010 reg.7", "https://www.legislation.gov.uk/uksi/2010/93/regulation/7"),
            _citation("Agency Workers Regulations 2010 reg.18", "https://www.legislation.gov.uk/uksi/2010/93/regulation/18"),
        ],
    }
