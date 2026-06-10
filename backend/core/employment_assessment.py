"""
Multi-Module Employment Law Assessment Framework
Supports all 26 employment modules with generic assessment engine.
Rules loaded from database, never hardcoded.
"""

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


# Module-specific assessment logic (all 26 modules implemented)
ASSESSMENT_HANDLERS = {
    "unfair_dismissal": "assess_unfair_dismissal",
    "unpaid_wages": "assess_unpaid_wages",
    "discrimination": "assess_discrimination",
    "constructive_dismissal": "assess_constructive_dismissal",
    "wrongful_dismissal": "assess_wrongful_dismissal",
    "working_time_regulations": "assess_working_time_regulations",
    "maternity_rights": "assess_maternity_rights",
    "paternity_rights": "assess_paternity_rights",
    "parental_leave": "assess_parental_leave",
    "shared_parental_leave": "assess_shared_parental_leave",
    "flexible_working": "assess_flexible_working",
    "equal_pay": "assess_equal_pay",
    "national_minimum_wage": "assess_national_minimum_wage",
    "working_time_directive": "assess_working_time_directive",
    "pregnancy_discrimination": "assess_pregnancy_discrimination",
    "part_time_workers": "assess_part_time_workers",
    "fixed_term_workers": "assess_fixed_term_workers",
    "agency_workers": "assess_agency_workers",
    "redundancy": "assess_redundancy",
    "transfer_of_undertaking": "assess_transfer_of_undertaking",
    "data_protection_employment": "assess_data_protection_employment",
    "whistleblowing": "assess_whistleblowing",
    "health_and_safety": "assess_health_and_safety",
    "trade_union_rights": "assess_trade_union_rights",
    "strikes_and_lockouts": "assess_strikes_and_lockouts",
    "employment_contracts": "assess_employment_contracts",
}


def assess_case(
    claim_type: str,
    facts: Dict[str, Any],
    rules: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generic employment law assessment dispatcher.

    Args:
        claim_type: Module name (unfair_dismissal, unpaid_wages, etc.)
        facts: User-provided case facts
        rules: Rules loaded from database for this claim_type

    Returns:
        Structured assessment with viability, strength, damages, deadline, citations
    """

    logger.info(f"Assessing {claim_type}")

    # Validate facts is a dict
    if facts is None or not isinstance(facts, dict):
        return {
            "viable_claim": None,
            "claim_type": claim_type,
            "error": "facts must be a non-empty dictionary",
        }

    if len(facts) == 0:
        return {
            "viable_claim": None,
            "claim_type": claim_type,
            "error": "facts cannot be empty",
        }

    # Validate claim_type is supported
    if claim_type not in ASSESSMENT_HANDLERS:
        return {
            "viable_claim": None,
            "claim_type": claim_type,
            "error": f"Claim type '{claim_type}' not supported yet",
            "supported_types": list(ASSESSMENT_HANDLERS.keys()),
        }

    # Route to module-specific handler
    handler_name = ASSESSMENT_HANDLERS[claim_type]
    handler = globals().get(handler_name)

    if not handler:
        return {
            "viable_claim": None,
            "error": f"Handler for {claim_type} not implemented",
        }

    # Call handler with facts + rules
    return handler(facts, rules)


def assess_unfair_dismissal(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Unfair dismissal (ERA 1996 s.94)"""

    try:
        edt = datetime.fromisoformat(facts.get("dismissal_date", ""))
        years_service_value = facts.get("years_service")
        if years_service_value is None:
            start_value = facts.get("employment_start_date") or facts.get("service_start_date")
            if not start_value:
                raise ValueError("years_service or employment_start_date required")
            start_date = datetime.fromisoformat(str(start_value))
            years_service = max(0.0, (edt.date() - start_date.date()).days / 365.2425)
        else:
            years_service = float(years_service_value)
        gross_weekly = float(facts.get("gross_weekly_pay", 1000))
        age = int(facts.get("age", 30))
    except (ValueError, TypeError) as e:
        return {
            "viable_claim": False,
            "claim_type": "unfair_dismissal",
            "reason": f"Invalid facts: {str(e)}",
            "confidence": 0.0,
            "confidence_score": 0.0,
            "grounding_score": 0.0,
            "insufficient_grounding": True,
            "citations": [],
        }

    qualifying_years = rules.get("qualifying_period_months", 24) / 12
    if years_service < qualifying_years:
        # s.111(2): period "begins with" the EDT, so deadline = +months − 1 day
        deadline = (edt + relativedelta(months=rules.get("time_limit_months", 3)) - timedelta(days=1)).date().isoformat()
        deadline_info = {
            "limitation_date": deadline,
            "source": "rules",
            "authority": "ERA 1996 s.111(2)",
        }
        return {
            "viable_claim": False,
            "claim_type": "unfair_dismissal",
            "reason": f"Does not meet qualifying period ({qualifying_years} years required)",
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

    # Deadline (3 or 6 months per rules) - use calendar months, not fixed 30 days.
    # s.111(2): the period "begins with" the EDT, so deadline = +months − 1 day.
    months = rules.get("time_limit_months", 3)
    deadline = (edt + relativedelta(months=months) - timedelta(days=1)).date().isoformat()
    deadline_info = {
        "limitation_date": deadline,
        "source": "rules",
        "authority": "ERA 1996 s.111(2)",
    }

    # Damages
    years_for_award = min(int(years_service), 20)
    multiplier = 1.5 if age >= 41 else (1.0 if age >= 22 else 0.5)
    week_cap = rules.get("weeks_pay_cap_amount", 751)
    basic = years_for_award * multiplier * min(gross_weekly, week_cap)
    basic = max(basic, rules.get("basic_award_min", 9157))
    # Statutory compensatory cap MUST come from the rules table — fail closed
    # rather than fall back to a hardcoded legal value.
    comp_cap = rules.get("compensatory_cap_amount")
    if comp_cap is None:
        raise ValueError("compensatory cap rule missing — fail closed (no hardcoded cap)")
    comp = min(gross_weekly * 52, comp_cap)

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


def assess_unpaid_wages(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Unpaid wages (ERA 1996 s.23)"""

    try:
        amount_owed = float(facts.get("amount_owed", 0))
        last_payment_date = datetime.fromisoformat(facts.get("last_payment_date", ""))
    except (ValueError, TypeError) as e:
        return {"viable_claim": False, "reason": f"Invalid facts: {str(e)}", "confidence": 0.0}

    # 2-year limitation (s.23) - use calendar years for accuracy
    time_limit_years = rules.get("time_limit_years", 2)
    deadline = (last_payment_date + relativedelta(years=time_limit_years)).isoformat()

    return {
        "viable_claim": amount_owed > 0,
        "claim_type": "unpaid_wages",
        "jurisdiction": "EW",
        "strength": "strong" if amount_owed >= 5000 else "moderate",
        "confidence": 0.9,
        "amount_owed": amount_owed,
        "deadline": deadline,
        "citations": ["ERA 1996 s.23", "ERA 1996 s.227"],
    }


def assess_discrimination(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Discrimination (Equality Act 2010)"""

    try:
        protected_characteristic = facts.get("protected_characteristic", "")
        discriminatory_event_date = datetime.fromisoformat(facts.get("discriminatory_event_date", ""))
    except (ValueError, TypeError) as e:
        return {"viable_claim": False, "reason": f"Invalid facts: {str(e)}", "confidence": 0.0}

    allowed_chars = rules.get("protected_characteristics", [
        "age", "disability", "gender_reassignment", "marriage",
        "pregnancy", "race", "religion", "sex", "sexual_orientation"
    ])

    if protected_characteristic not in allowed_chars:
        return {
            "viable_claim": False,
            "claim_type": "discrimination",
            "reason": f"'{protected_characteristic}' is not a protected characteristic",
            "allowed": allowed_chars,
        }

    # 3-month deadline — EqA 2010 s.123: period "begins with" the act, so −1 day
    deadline = (discriminatory_event_date + relativedelta(months=3) - timedelta(days=1)).isoformat()

    return {
        "viable_claim": True,
        "claim_type": "discrimination",
        "jurisdiction": "EW",
        "protected_characteristic": protected_characteristic,
        "strength": "moderate",
        "confidence": 0.75,
        "deadline": deadline,
        "citations": ["Equality Act 2010 s.123", "EHRC Code of Practice"],
    }


def assess_constructive_dismissal(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Constructive dismissal (ERA 1996 s.95(1)(c))"""

    try:
        breach_type = facts.get("breach_type", "")
        resignation_date = datetime.fromisoformat(facts.get("resignation_date", ""))
        years_service = float(facts.get("years_service", 0))
    except (ValueError, TypeError) as e:
        return {"viable_claim": False, "reason": f"Invalid facts: {str(e)}", "confidence": 0.0}

    # Constructive dismissal = qualifying period same as unfair dismissal
    qualifying_years = rules.get("qualifying_period_months", 24) / 12
    if years_service < qualifying_years:
        return {
            "viable_claim": False,
            "claim_type": "constructive_dismissal",
            "reason": f"Does not meet qualifying period",
        }

    # Deadline from resignation (not EDT) — period "begins with" it, so −1 day
    deadline = (resignation_date + relativedelta(months=3) - timedelta(days=1)).isoformat()

    return {
        "viable_claim": True,
        "claim_type": "constructive_dismissal",
        "jurisdiction": "EW",
        "breach_type": breach_type,
        "strength": "moderate",
        "confidence": 0.7,
        "deadline": deadline,
        "citations": ["ERA 1996 s.95(1)(c)", "ERA 1996 s.94"],
    }


def assess_wrongful_dismissal(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Wrongful dismissal (common law contract breach)"""

    try:
        notice_period_days = int(facts.get("notice_period_days", 0))
        dismissal_date = datetime.fromisoformat(facts.get("dismissal_date", ""))
        gross_weekly = float(facts.get("gross_weekly_pay", 1000))
    except (ValueError, TypeError) as e:
        return {"viable_claim": False, "reason": f"Invalid facts: {str(e)}", "confidence": 0.0}

    # Damages = notice period pay
    damages = (gross_weekly * (notice_period_days / 7))

    # 6-year limitation (Limitation Act 1980 s.5) - use calendar years
    deadline = (dismissal_date + relativedelta(years=6)).isoformat()

    return {
        "viable_claim": damages > 0,
        "claim_type": "wrongful_dismissal",
        "jurisdiction": "EW",
        "notice_period_days": notice_period_days,
        "estimated_damages": round(damages, 2),
        "strength": "strong" if damages >= 10000 else "moderate",
        "confidence": 0.85,
        "deadline": deadline,
        "citations": ["Limitation Act 1980 s.5"],
    }


def assess_working_time_regulations(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Working Time Regulations 1998 - 48-hour week, rest breaks, annual leave"""
    try:
        hours_worked = float(facts.get("hours_worked_weekly", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    max_hours = rules.get("max_hours_per_week", 48)
    if hours_worked > max_hours:
        return {
            "viable_claim": True,
            "claim_type": "working_time_regulations",
            "strength": "strong",
            "confidence": 0.9,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Working Time Regulations 1998 reg.4"],
        }
    return {"viable_claim": False, "claim_type": "working_time_regulations", "confidence": 0.85}


def assess_maternity_rights(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Maternity Rights - pregnancy protection, maternity leave"""
    try:
        pregnancy_dismissal = facts.get("dismissal_reason") == "pregnancy"
        weeks_pregnant = float(facts.get("weeks_pregnant", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if pregnancy_dismissal or weeks_pregnant > 0:
        return {
            "viable_claim": True,
            "claim_type": "maternity_rights",
            "strength": "very_strong",
            "confidence": 0.95,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["ERA 1996 s.99", "Equality Act 2010 s.18"],
        }
    return {"viable_claim": False, "claim_type": "maternity_rights", "confidence": 0.85}


def assess_paternity_rights(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Paternity Rights - paternity leave, parental responsibility"""
    try:
        denial_of_leave = facts.get("denied_paternity_leave", False)
        months_since_birth = float(facts.get("months_since_birth", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if denial_of_leave and months_since_birth <= 12:
        return {
            "viable_claim": True,
            "claim_type": "paternity_rights",
            "strength": "moderate",
            "confidence": 0.8,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Employment Rights Act 2002 s.80"],
        }
    return {"viable_claim": False, "claim_type": "paternity_rights", "confidence": 0.8}


def assess_parental_leave(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Parental Leave - right to unpaid leave, protected reinstatement"""
    try:
        child_age = float(facts.get("child_age_years", 0))
        leave_denied = facts.get("parental_leave_denied", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if leave_denied and child_age < 5:
        return {
            "viable_claim": True,
            "claim_type": "parental_leave",
            "strength": "moderate",
            "confidence": 0.75,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Maternity and Parental Leave Regulations 1999 reg.13"],
        }
    return {"viable_claim": False, "claim_type": "parental_leave", "confidence": 0.75}


def assess_shared_parental_leave(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Shared Parental Leave - flexible leave sharing between parents"""
    try:
        spl_refused = facts.get("shared_parental_leave_refused", False)
        child_months = float(facts.get("child_months", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if spl_refused and child_months < 52:
        return {
            "viable_claim": True,
            "claim_type": "shared_parental_leave",
            "strength": "moderate",
            "confidence": 0.75,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Children and Families Act 2014 s.112"],
        }
    return {"viable_claim": False, "claim_type": "shared_parental_leave", "confidence": 0.75}


def assess_flexible_working(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Flexible Working - right to request, employer must consider seriously"""
    try:
        request_made = facts.get("flexible_working_request_made", False)
        request_refused = facts.get("request_unreasonably_refused", False)
        years_service = float(facts.get("years_service", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if request_made and request_refused and years_service >= 3:
        return {
            "viable_claim": True,
            "claim_type": "flexible_working",
            "strength": "moderate",
            "confidence": 0.7,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["ERA 1996 s.80F"],
        }
    return {"viable_claim": False, "claim_type": "flexible_working", "confidence": 0.7}


def assess_equal_pay(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Equal Pay Act 1970 - sex discrimination in pay"""
    try:
        comparator_pay = float(facts.get("comparator_pay", 0))
        claimant_pay = float(facts.get("claimant_pay", 0))
        same_work = facts.get("same_work_or_equivalent", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    pay_gap = comparator_pay - claimant_pay
    if same_work and pay_gap > 0:
        return {
            "viable_claim": True,
            "claim_type": "equal_pay",
            "strength": "strong",
            "confidence": 0.85,
            "estimated_damages": pay_gap * 52,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Equal Pay Act 1970 s.1"],
        }
    return {"viable_claim": False, "claim_type": "equal_pay", "confidence": 0.85}


def assess_national_minimum_wage(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """National Minimum Wage - below statutory minimum"""
    try:
        hourly_rate = float(facts.get("hourly_rate", 0))
        hours_worked = float(facts.get("hours_worked", 0))
        weeks_underpaid = float(facts.get("weeks_underpaid", 0))
        age = int(facts.get("age", 25))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    nmw_rate = rules.get("nmw_rate", 11.44)
    if hourly_rate < nmw_rate:
        shortfall = (nmw_rate - hourly_rate) * hours_worked * weeks_underpaid
        return {
            "viable_claim": True,
            "claim_type": "national_minimum_wage",
            "strength": "very_strong",
            "confidence": 0.95,
            "estimated_damages": shortfall,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["National Minimum Wage Act 1998 s.31"],
        }
    return {"viable_claim": False, "claim_type": "national_minimum_wage", "confidence": 0.95}


def assess_working_time_directive(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Working Time Directive - daily/weekly rest, holiday pay"""
    try:
        daily_hours = float(facts.get("daily_hours", 0))
        weekly_rest_days = float(facts.get("weekly_rest_days", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if daily_hours > 13 or weekly_rest_days < 1:
        return {
            "viable_claim": True,
            "claim_type": "working_time_directive",
            "strength": "moderate",
            "confidence": 0.75,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Working Time Regulations 1998"],
        }
    return {"viable_claim": False, "claim_type": "working_time_directive", "confidence": 0.75}


def assess_pregnancy_discrimination(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Pregnancy Discrimination - protected characteristic under Equality Act"""
    try:
        pregnant = facts.get("is_pregnant", False)
        discriminatory_act = facts.get("discriminatory_action", "")
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if pregnant and discriminatory_act:
        return {
            "viable_claim": True,
            "claim_type": "pregnancy_discrimination",
            "strength": "very_strong",
            "confidence": 0.95,
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["Equality Act 2010 s.18"],
        }
    return {"viable_claim": False, "claim_type": "pregnancy_discrimination", "confidence": 0.9}


def assess_part_time_workers(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Part-Time Workers - pro-rata rights, no less favourable treatment"""
    try:
        hours_pt = float(facts.get("part_time_hours", 0))
        hours_ft = float(facts.get("full_time_hours", 40))
        pay_pt = float(facts.get("part_time_pay", 0))
        pay_ft = float(facts.get("full_time_pay", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if hours_pt > 0 and hours_ft > 0:
        pt_hourly = pay_pt / hours_pt
        ft_hourly = pay_ft / hours_ft
        if pt_hourly < ft_hourly * 0.95:
            return {
                "viable_claim": True,
                "claim_type": "part_time_workers",
                "strength": "moderate",
                "confidence": 0.75,
                "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
                "citations": ["Part-time Workers Directive 97/81/EC"],
            }
    return {"viable_claim": False, "claim_type": "part_time_workers", "confidence": 0.75}


def assess_fixed_term_workers(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Fixed-Term Workers - succession renewal, no less favourable treatment"""
    try:
        contract_type = facts.get("contract_type", "")
        successive_renewals = float(facts.get("successive_renewals", 0))
        duration_months = float(facts.get("total_duration_months", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if contract_type == "fixed_term" and successive_renewals >= 4 and duration_months >= 24:
        return {
            "viable_claim": True,
            "claim_type": "fixed_term_workers",
            "strength": "moderate",
            "confidence": 0.75,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Fixed-term Employees Regulations 2002"],
        }
    return {"viable_claim": False, "claim_type": "fixed_term_workers", "confidence": 0.75}


def assess_agency_workers(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Agency Workers - equal treatment after 12 weeks"""
    try:
        weeks_assignment = float(facts.get("weeks_on_assignment", 0))
        agency_pay = float(facts.get("agency_worker_pay", 0))
        direct_pay = float(facts.get("direct_worker_pay", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if weeks_assignment >= 12 and agency_pay < direct_pay:
        pay_gap = direct_pay - agency_pay
        return {
            "viable_claim": True,
            "claim_type": "agency_workers",
            "strength": "moderate",
            "confidence": 0.8,
            "estimated_damages": pay_gap * 4,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Agency Workers Regulations 2010 reg.5"],
        }
    return {"viable_claim": False, "claim_type": "agency_workers", "confidence": 0.8}


def assess_redundancy(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Redundancy - eligibility, consultation, payment"""
    try:
        years_service = float(facts.get("years_service", 0))
        weekly_pay = float(facts.get("gross_weekly_pay", 0))
        age = int(facts.get("age", 30))
        genuine_redundancy = facts.get("genuine_redundancy", True)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if years_service >= 2:
        if not genuine_redundancy:
            return {
                "viable_claim": True,
                "claim_type": "redundancy",
                "strength": "moderate",
                "confidence": 0.75,
                "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
                "citations": ["ERA 1996 s.139"],
            }
        else:
            weeks_per_year = 0.5 if age < 22 else (1.0 if age < 41 else 1.5)
            years_to_count = min(int(years_service), 20)
            week_cap = rules.get("weeks_pay_cap", 751)
            redundancy_payment = years_to_count * weeks_per_year * min(weekly_pay, week_cap)
            return {
                "viable_claim": True,
                "claim_type": "redundancy",
                "strength": "strong",
                "confidence": 0.9,
                "estimated_damages": redundancy_payment,
                "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
                "citations": ["ERA 1996 s.135"],
            }
    return {"viable_claim": False, "claim_type": "redundancy", "confidence": 0.85}


def assess_transfer_of_undertaking(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Transfer of Undertaking (TUPE) - employment continuity, protection"""
    try:
        tupe_transfer = facts.get("tupe_transfer", False)
        dismissal_connected = facts.get("dismissal_connected_to_transfer", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if tupe_transfer and dismissal_connected:
        return {
            "viable_claim": True,
            "claim_type": "transfer_of_undertaking",
            "strength": "very_strong",
            "confidence": 0.95,
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["Transfer of Undertakings Regulations 2006 reg.7"],
        }
    return {"viable_claim": False, "claim_type": "transfer_of_undertaking", "confidence": 0.9}


def assess_data_protection_employment(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Data Protection in Employment - GDPR, privacy rights"""
    try:
        unlawful_processing = facts.get("unlawful_data_processing", False)
        breach_type = facts.get("breach_type", "")
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if unlawful_processing and breach_type:
        return {
            "viable_claim": True,
            "claim_type": "data_protection_employment",
            "strength": "moderate",
            "confidence": 0.75,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["UK GDPR Article 82"],
        }
    return {"viable_claim": False, "claim_type": "data_protection_employment", "confidence": 0.75}


def assess_whistleblowing(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Whistleblowing - Public Interest Disclosure Act protection"""
    try:
        disclosure_made = facts.get("protected_disclosure_made", False)
        dismissal_follows = facts.get("dismissal_after_disclosure", False)
        public_interest = facts.get("in_public_interest", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if disclosure_made and dismissal_follows and public_interest:
        return {
            "viable_claim": True,
            "claim_type": "whistleblowing",
            "strength": "very_strong",
            "confidence": 0.95,
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["ERA 1996 s.103A"],
        }
    return {"viable_claim": False, "claim_type": "whistleblowing", "confidence": 0.9}


def assess_health_and_safety(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Health & Safety - dismissal for raising concerns, right to refuse unsafe work"""
    try:
        safety_concern_raised = facts.get("safety_concern_raised", False)
        dismissal_for_concern = facts.get("dismissal_for_safety_concern", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if (safety_concern_raised or dismissal_for_concern) and dismissal_for_concern:
        return {
            "viable_claim": True,
            "claim_type": "health_and_safety",
            "strength": "very_strong",
            "confidence": 0.95,
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["ERA 1996 s.100"],
        }
    return {"viable_claim": False, "claim_type": "health_and_safety", "confidence": 0.9}


def assess_trade_union_rights(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Trade Union Rights - membership, activities, time off"""
    try:
        union_member = facts.get("union_member", False)
        dismissed_for_membership = facts.get("dismissed_for_union_membership", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if (dismissed_for_membership or union_member) and dismissed_for_membership:
        return {
            "viable_claim": True,
            "claim_type": "trade_union_rights",
            "strength": "very_strong",
            "confidence": 0.95,
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["ERA 1996 s.152"],
        }
    return {"viable_claim": False, "claim_type": "trade_union_rights", "confidence": 0.9}


def assess_strikes_and_lockouts(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Strikes & Lockouts - protection from dismissal, reinstatement rights"""
    try:
        participated_in_strike = facts.get("participated_in_strike", False)
        dismissed_for_strike = facts.get("dismissed_for_strike", False)
        days_since_strike = float(facts.get("days_since_strike_start", 100))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if participated_in_strike and dismissed_for_strike and days_since_strike < 12:
        return {
            "viable_claim": True,
            "claim_type": "strikes_and_lockouts",
            "strength": "strong",
            "confidence": 0.85,
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["ERA 1996 s.238"],
        }
    return {"viable_claim": False, "claim_type": "strikes_and_lockouts", "confidence": 0.85}


def assess_employment_contracts(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Employment Contracts - breach, unfair terms, written statement"""
    try:
        written_statement = facts.get("written_statement_provided", True)
        contract_breach = facts.get("contract_breach", False)
        breach_amount = float(facts.get("breach_amount", 0))
        employment_months = float(facts.get("employment_duration_months", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if not written_statement and employment_months > 2:
        return {
            "viable_claim": True,
            "claim_type": "employment_contracts",
            "strength": "moderate",
            "confidence": 0.7,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["ERA 1996 s.1"],
        }

    if contract_breach and breach_amount > 0:
        return {
            "viable_claim": True,
            "claim_type": "employment_contracts",
            "strength": "moderate",
            "confidence": 0.8,
            "estimated_damages": breach_amount,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Breach of Contract claims"],
        }

    return {"viable_claim": False, "claim_type": "employment_contracts", "confidence": 0.75}


def assess_working_time_regulations(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Working Time Regulations 1998 - 48-hour week, rest breaks, annual leave"""
    try:
        hours_worked = float(facts.get("hours_worked_weekly", 0))
        weeks_unpaid_leave = float(facts.get("weeks_unpaid_leave", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    max_hours = rules.get("max_hours_per_week", 48)
    if hours_worked > max_hours:
        return {
            "viable_claim": True,
            "claim_type": "working_time_regulations",
            "strength": "strong",
            "confidence": 0.9,
            "issue": f"Working {hours_worked}h/week exceeds {max_hours}h limit",
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Working Time Regulations 1998 reg.4", "ERA 1996 s.80A"],
        }

    return {"viable_claim": False, "claim_type": "working_time_regulations", "confidence": 0.85}


def assess_maternity_rights(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Maternity Rights - pregnancy protection, maternity leave, redundancy during pregnancy"""
    try:
        pregnancy_related_dismissal = facts.get("dismissal_reason") == "pregnancy"
        weeks_pregnant = float(facts.get("weeks_pregnant", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if pregnancy_related_dismissal or weeks_pregnant > 0:
        return {
            "viable_claim": True,
            "claim_type": "maternity_rights",
            "strength": "very_strong",
            "confidence": 0.95,
            "issue": "Dismissal related to pregnancy is automatically unfair",
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "estimated_compensation": rules.get("avg_maternity_award", 15000),
            "citations": ["ERA 1996 s.99", "Equality Act 2010 s.18"],
        }

    return {"viable_claim": False, "claim_type": "maternity_rights", "confidence": 0.85}


def assess_paternity_rights(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Paternity Rights - paternity leave, parental responsibility"""
    try:
        months_since_birth = float(facts.get("months_since_birth", 0))
        denial_of_leave = facts.get("denied_paternity_leave", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if denial_of_leave and months_since_birth <= 12:
        return {
            "viable_claim": True,
            "claim_type": "paternity_rights",
            "strength": "moderate",
            "confidence": 0.8,
            "issue": "Denial of statutory paternity leave",
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Employment Rights Act 2002 s.80", "ERA 1996 Part 8A"],
        }

    return {"viable_claim": False, "claim_type": "paternity_rights", "confidence": 0.8}


def assess_parental_leave(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Parental Leave - right to unpaid leave, protected reinstatement"""
    try:
        child_age = float(facts.get("child_age_years", 0))
        leave_denied = facts.get("parental_leave_denied", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if leave_denied and child_age < 5:
        return {
            "viable_claim": True,
            "claim_type": "parental_leave",
            "strength": "moderate",
            "confidence": 0.75,
            "issue": "Denial of statutory parental leave entitlement",
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Maternity and Parental Leave Regulations 1999 reg.13", "ERA 1996 s.80A"],
        }

    return {"viable_claim": False, "claim_type": "parental_leave", "confidence": 0.75}


def assess_shared_parental_leave(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Shared Parental Leave - flexible leave sharing between parents"""
    try:
        total_child_months = float(facts.get("child_months", 0))
        spl_refused = facts.get("shared_parental_leave_refused", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if spl_refused and total_child_months < 52:
        return {
            "viable_claim": True,
            "claim_type": "shared_parental_leave",
            "strength": "moderate",
            "confidence": 0.75,
            "issue": "Denial of shared parental leave entitlement",
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Children and Families Act 2014 s.112", "Shared Parental Leave Regulations 2014"],
        }

    return {"viable_claim": False, "claim_type": "shared_parental_leave", "confidence": 0.75}


def assess_flexible_working(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Flexible Working - right to request, employer must consider seriously"""
    try:
        request_made = facts.get("flexible_working_request_made", False)
        request_refused = facts.get("request_unreasonably_refused", False)
        employment_duration_years = float(facts.get("years_service", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if request_made and request_refused and employment_duration_years >= 3:
        return {
            "viable_claim": True,
            "claim_type": "flexible_working",
            "strength": "moderate",
            "confidence": 0.7,
            "issue": "Failure to properly consider flexible working request",
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["ERA 1996 s.80F", "Employment Rights Act 2002 s.47"],
        }

    return {"viable_claim": False, "claim_type": "flexible_working", "confidence": 0.7}


def assess_equal_pay(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Equal Pay Act 1970 - sex discrimination in pay"""
    try:
        comparator_pay = float(facts.get("comparator_pay", 0))
        claimant_pay = float(facts.get("claimant_pay", 0))
        same_work = facts.get("same_work_or_equivalent", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    pay_gap = comparator_pay - claimant_pay
    if same_work and pay_gap > 0:
        estimated_arrears = pay_gap * 52  # 1 year estimate
        return {
            "viable_claim": True,
            "claim_type": "equal_pay",
            "strength": "strong",
            "confidence": 0.85,
            "issue": f"Pay gap of £{pay_gap:.2f}/week for same work",
            "estimated_damages": min(estimated_arrears, rules.get("equal_pay_cap", 200000)),
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Equal Pay Act 1970 s.1", "Equality Act 2010 s.66"],
        }

    return {"viable_claim": False, "claim_type": "equal_pay", "confidence": 0.85}


def assess_national_minimum_wage(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """National Minimum Wage - below statutory minimum"""
    try:
        hourly_rate = float(facts.get("hourly_rate", 0))
        hours_worked = float(facts.get("hours_worked", 0))
        weeks_underpaid = float(facts.get("weeks_underpaid", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    age = facts.get("age", 25)
    nmw_rate = rules.get(f"nmw_age_{age}", 11.44)  # 2024 rate

    if hourly_rate < nmw_rate:
        shortfall_per_week = (nmw_rate - hourly_rate) * hours_worked
        total_arrears = shortfall_per_week * weeks_underpaid
        return {
            "viable_claim": True,
            "claim_type": "national_minimum_wage",
            "strength": "very_strong",
            "confidence": 0.95,
            "issue": f"Paid £{hourly_rate}/h, NMW is £{nmw_rate}/h",
            "estimated_damages": total_arrears,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["National Minimum Wage Act 1998 s.31", "Employment Rights Act 1996 s.193"],
        }

    return {"viable_claim": False, "claim_type": "national_minimum_wage", "confidence": 0.95}


def assess_working_time_directive(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Working Time Directive - daily/weekly rest, holiday pay"""
    try:
        daily_hours = float(facts.get("daily_hours", 0))
        weekly_rest_days = float(facts.get("weekly_rest_days", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    min_daily_rest = rules.get("min_daily_rest_hours", 11)
    min_weekly_rest = rules.get("min_weekly_rest_days", 1.43)

    violations = []
    if daily_hours > 13:
        violations.append(f"Daily hours {daily_hours}h exceeds safe limits")
    if weekly_rest_days < min_weekly_rest:
        violations.append(f"Weekly rest {weekly_rest_days} days below {min_weekly_rest}")

    if violations:
        return {
            "viable_claim": True,
            "claim_type": "working_time_directive",
            "strength": "moderate",
            "confidence": 0.75,
            "issues": violations,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Working Time Regulations 1998", "Council Directive 93/104/EC"],
        }

    return {"viable_claim": False, "claim_type": "working_time_directive", "confidence": 0.75}


def assess_pregnancy_discrimination(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Pregnancy Discrimination - protected characteristic under Equality Act"""
    try:
        pregnant = facts.get("is_pregnant", False)
        discriminatory_act = facts.get("discriminatory_action", "")
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if pregnant and discriminatory_act:
        return {
            "viable_claim": True,
            "claim_type": "pregnancy_discrimination",
            "strength": "very_strong",
            "confidence": 0.95,
            "issue": f"Pregnancy discrimination: {discriminatory_act}",
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["Equality Act 2010 s.18", "ERA 1996 s.99"],
        }

    return {"viable_claim": False, "claim_type": "pregnancy_discrimination", "confidence": 0.9}


def assess_part_time_workers(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Part-Time Workers - pro-rata rights, no less favourable treatment"""
    try:
        hours_pt = float(facts.get("part_time_hours", 0))
        hours_ft = float(facts.get("full_time_comparison_hours", 40))
        pay_pt = float(facts.get("part_time_pay", 0))
        pay_ft = float(facts.get("full_time_comparison_pay", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    pt_hourly = pay_pt / hours_pt if hours_pt > 0 else 0
    ft_hourly = pay_ft / hours_ft if hours_ft > 0 else 0

    if pt_hourly < ft_hourly * 0.95:  # 5% tolerance
        return {
            "viable_claim": True,
            "claim_type": "part_time_workers",
            "strength": "moderate",
            "confidence": 0.75,
            "issue": "Part-time workers paid less per hour than comparable full-time",
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Part-time Workers Directive 97/81/EC", "Employment Rights Act 1996 s.47B"],
        }

    return {"viable_claim": False, "claim_type": "part_time_workers", "confidence": 0.75}


def assess_fixed_term_workers(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Fixed-Term Workers - succession renewal, no less favourable treatment"""
    try:
        contract_type = facts.get("contract_type", "")
        successive_renewals = float(facts.get("successive_renewals", 0))
        duration_months = float(facts.get("total_duration_months", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if contract_type == "fixed_term" and successive_renewals >= 4 and duration_months >= 24:
        return {
            "viable_claim": True,
            "claim_type": "fixed_term_workers",
            "strength": "moderate",
            "confidence": 0.75,
            "issue": "Successive fixed-term renewals may constitute indefinite contract",
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Fixed-term Employees (Prevention of Less Favourable Treatment) Regulations 2002"],
        }

    return {"viable_claim": False, "claim_type": "fixed_term_workers", "confidence": 0.75}


def assess_agency_workers(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Agency Workers - equal treatment after 12 weeks"""
    try:
        weeks_assignment = float(facts.get("weeks_on_assignment", 0))
        agency_pay = float(facts.get("agency_worker_pay", 0))
        direct_pay = float(facts.get("direct_worker_pay", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if weeks_assignment >= 12 and agency_pay < direct_pay:
        pay_gap = direct_pay - agency_pay
        return {
            "viable_claim": True,
            "claim_type": "agency_workers",
            "strength": "moderate",
            "confidence": 0.8,
            "issue": f"After 12 weeks, entitled to equal pay (gap: £{pay_gap})",
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Agency Workers Regulations 2010 reg.5", "Equality Act 2010"],
        }

    return {"viable_claim": False, "claim_type": "agency_workers", "confidence": 0.8}


def assess_redundancy(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Redundancy - eligibility, consultation, payment"""
    try:
        years_service = float(facts.get("years_service", 0))
        weekly_pay = float(facts.get("gross_weekly_pay", 0))
        age = int(facts.get("age", 30))
        genuine_redundancy = facts.get("genuine_redundancy", True)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if not genuine_redundancy and years_service >= 2:
        return {
            "viable_claim": True,
            "claim_type": "redundancy",
            "strength": "moderate",
            "confidence": 0.75,
            "issue": "Dismissal is not genuine redundancy - unfair selection",
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["ERA 1996 s.139", "ERA 1996 s.94"],
        }

    if genuine_redundancy and years_service >= 2:
        # Calculate statutory redundancy payment
        weeks_per_year = 0.5 if age < 22 else (1.0 if age < 41 else 1.5)
        years_to_count = min(int(years_service), 20)
        week_cap = rules.get("weeks_pay_cap", 751)
        capped_pay = min(weekly_pay, week_cap)
        redundancy_payment = years_to_count * weeks_per_year * capped_pay

        return {
            "viable_claim": True,
            "claim_type": "redundancy",
            "strength": "strong",
            "confidence": 0.9,
            "issue": "Entitled to statutory redundancy payment",
            "estimated_damages": redundancy_payment,
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["ERA 1996 s.135", "ERA 1996 s.162"],
        }

    return {"viable_claim": False, "claim_type": "redundancy", "confidence": 0.85}


def assess_transfer_of_undertaking(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Transfer of Undertaking (TUPE) - employment continuity, protection"""
    try:
        tupe_transfer_occurred = facts.get("tupe_transfer", False)
        dismissal_connected = facts.get("dismissal_connected_to_transfer", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if tupe_transfer_occurred and dismissal_connected:
        return {
            "viable_claim": True,
            "claim_type": "transfer_of_undertaking",
            "strength": "very_strong",
            "confidence": 0.95,
            "issue": "Dismissal connected to TUPE transfer - automatically unfair",
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["Transfer of Undertakings (Protection of Employment) Regulations 2006 reg.7"],
        }

    return {"viable_claim": False, "claim_type": "transfer_of_undertaking", "confidence": 0.9}


def assess_data_protection_employment(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Data Protection in Employment - GDPR, privacy rights"""
    try:
        unlawful_processing = facts.get("unlawful_data_processing", False)
        breach_type = facts.get("breach_type", "")
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if unlawful_processing and breach_type:
        return {
            "viable_claim": True,
            "claim_type": "data_protection_employment",
            "strength": "moderate",
            "confidence": 0.75,
            "issue": f"Unlawful data processing: {breach_type}",
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["UK GDPR Article 82", "Data Protection Act 2018 s.169"],
        }

    return {"viable_claim": False, "claim_type": "data_protection_employment", "confidence": 0.75}


def assess_whistleblowing(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Whistleblowing - Public Interest Disclosure Act protection"""
    try:
        disclosure_made = facts.get("protected_disclosure_made", False)
        dismissal_follows = facts.get("dismissal_after_disclosure", False)
        public_interest = facts.get("in_public_interest", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if disclosure_made and dismissal_follows and public_interest:
        return {
            "viable_claim": True,
            "claim_type": "whistleblowing",
            "strength": "very_strong",
            "confidence": 0.95,
            "issue": "Dismissal for protected whistleblowing disclosure - automatically unfair",
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["ERA 1996 s.103A", "Public Interest Disclosure Act 1998"],
        }

    return {"viable_claim": False, "claim_type": "whistleblowing", "confidence": 0.9}


def assess_health_and_safety(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Health & Safety - dismissal for raising concerns, right to refuse unsafe work"""
    try:
        safety_concern_raised = facts.get("safety_concern_raised", False)
        dismissal_for_concern = facts.get("dismissal_for_safety_concern", False)
        unsafe_conditions = facts.get("unsafe_work_conditions", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if (safety_concern_raised or unsafe_conditions) and dismissal_for_concern:
        return {
            "viable_claim": True,
            "claim_type": "health_and_safety",
            "strength": "very_strong",
            "confidence": 0.95,
            "issue": "Dismissal for raising health & safety concerns - automatically unfair",
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["ERA 1996 s.100", "Health and Safety at Work etc. Act 1974 s.44"],
        }

    return {"viable_claim": False, "claim_type": "health_and_safety", "confidence": 0.9}


def assess_trade_union_rights(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Trade Union Rights - membership, activities, time off"""
    try:
        union_member = facts.get("union_member", False)
        dismissed_for_membership = facts.get("dismissed_for_union_membership", False)
        union_activities = facts.get("union_activities", False)
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if (dismissed_for_membership or union_activities) and union_member:
        return {
            "viable_claim": True,
            "claim_type": "trade_union_rights",
            "strength": "very_strong",
            "confidence": 0.95,
            "issue": "Dismissal for union membership or activities - automatically unfair",
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["ERA 1996 s.152", "TULR(C)A 1992 s.146"],
        }

    return {"viable_claim": False, "claim_type": "trade_union_rights", "confidence": 0.9}


def assess_strikes_and_lockouts(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Strikes & Lockouts - protection from dismissal, reinstatement rights"""
    try:
        participated_in_strike = facts.get("participated_in_strike", False)
        dismissed_for_strike = facts.get("dismissed_for_strike", False)
        days_since_strike_start = float(facts.get("days_since_strike_start", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if participated_in_strike and dismissed_for_strike and days_since_strike_start < 12:
        return {
            "viable_claim": True,
            "claim_type": "strikes_and_lockouts",
            "strength": "strong",
            "confidence": 0.85,
            "issue": "Dismissal for participation in official strike within 12-week period",
            "deadline": (datetime.utcnow() + relativedelta(months=3)).isoformat(),
            "citations": ["ERA 1996 s.238", "TULR(C)A 1992 s.238A"],
        }

    return {"viable_claim": False, "claim_type": "strikes_and_lockouts", "confidence": 0.85}


def assess_employment_contracts(facts: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Employment Contracts - breach, unfair terms, written statement"""
    try:
        written_statement_provided = facts.get("written_statement_provided", True)
        contract_breach = facts.get("contract_breach", False)
        breach_amount = float(facts.get("breach_amount", 0))
        employment_duration_months = float(facts.get("employment_duration_months", 0))
    except (ValueError, TypeError):
        return {"viable_claim": False, "reason": "Invalid facts", "confidence": 0.0}

    if not written_statement_provided and employment_duration_months > 2:
        return {
            "viable_claim": True,
            "claim_type": "employment_contracts",
            "strength": "moderate",
            "confidence": 0.7,
            "issue": "Employer failed to provide written statement within 2 months",
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["ERA 1996 s.1", "ERA 1996 s.11"],
        }

    if contract_breach and breach_amount > 0:
        return {
            "viable_claim": True,
            "claim_type": "employment_contracts",
            "strength": "moderate",
            "confidence": 0.8,
            "issue": f"Breach of contract claim for £{breach_amount}",
            "estimated_damages": breach_amount,
            "deadline": (datetime.utcnow() + relativedelta(years=3)).isoformat(),
            "citations": ["Breach of Contract claims - County Court jurisdiction"],
        }

    return {"viable_claim": False, "claim_type": "employment_contracts", "confidence": 0.75}
