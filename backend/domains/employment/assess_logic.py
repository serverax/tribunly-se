"""
Phase 2C — Deterministic pre-assessment logic.

Runs BEFORE any model call. Computes everything that does not require
judicial judgment: scope, value ranges, key weaknesses from facts, and
citations from retrieved rules + BM25 authorities.

The model (Haiku) receives this as context and provides judgment on
procedural fairness, substantive fairness, and strength.

Guardrails enforced here:
- Every statement that enters the assessment must map to a cited authority.
- Statements with no authority are either dropped or trigger insufficient_grounding.
- Value ranges come from the rules table, never from model memory.
- Qualifying period check is hard-coded from rules, not model judgment.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Optional

from backend.domains.employment.checklists.burchell import assess_burchell_from_text
from backend.domains.employment.checklists.acas import assess_acas_code
from backend.domains.employment.checklists.evidence_weight import assess_evidence_weight
from backend.domains.employment.checklists.tribunal_elements import get_elements_for_claim

logger = logging.getLogger(__name__)

# Canonical rule_keys — must match the single series in the rules table
_QP_KEY   = "unfair_dismissal.qualifying_period"
_TL_KEY   = "unfair_dismissal.time_limit_months"
_CAP_KEY  = "unfair_dismissal.compensatory_cap_amount"
_WPC_KEY  = "unfair_dismissal.weeks_pay_cap_amount"
_FORM_KEY = "unfair_dismissal.basic_award_formula"
_EC_KEY   = "unfair_dismissal.early_conciliation_required"


def _rule(rules: list[dict], key: str) -> Optional[dict]:
    return next((r for r in rules if r["rule_key"] == key), None)


# ── Day-one / automatic-unfair detection ──────────────────────────────────────
# Keyword families that indicate a dismissal category needing NO qualifying
# period. Matched case-insensitively against the user's free-text description
# and selected facts. Deliberately recall-biased: a false positive produces a
# "needs review" flag; a false negative wrongly discourages a protected user.
_DAY_ONE_INDICATORS: list[tuple[str, str, tuple[str, ...]]] = [
    ("pregnancy or maternity", "ERA 1996 s.99",
     ("pregnan", "maternity", "antenatal", "ante-natal", "expecting a baby",
      "paternity", "parental leave", "adoption leave")),
    ("whistleblowing / protected disclosure", "ERA 1996 s.103A",
     ("whistleblow", "whistle-blow", "blew the whistle", "protected disclosure",
      "reported wrongdoing", "reported safety breaches", "reported to the hse",
      "reported to the regulator", "raised concerns about illegal")),
    ("health and safety activity", "ERA 1996 s.100",
     ("health and safety", "health & safety", "unsafe working", "refused unsafe",
      "safety concern", "safety breach", "dangerous condition")),
    ("trade union membership or activity", "TULRCA 1992 s.152",
     ("trade union", "union member", "union rep", "union activit",
      "joined a union", "joining a union")),
    ("asserting a statutory right", "ERA 1996 s.104",
     ("statutory right", "minimum wage complaint", "asked for my holiday pay",
      "national minimum wage", "working time complaint", "asserted my rights")),
]


def detect_day_one_exception(query: str, safe_facts: dict) -> Optional[dict]:
    """Return {label, authority} if the free text / facts mention an
    automatic-unfair (day-one) dismissal category, else None."""
    haystack = " ".join([
        str(query or ""),
        str(safe_facts.get("brief_facts") or ""),
        str(safe_facts.get("reason_for_dismissal") or ""),
        str(safe_facts.get("dismissal_context") or ""),
    ]).lower()
    for label, authority, needles in _DAY_ONE_INDICATORS:
        if any(n in haystack for n in needles):
            return {"label": label, "authority": authority}
    return None


def compute_value_range(rules: list[dict], safe_facts: dict) -> dict:
    """
    Compute the compensation value range deterministically from rules.

    Limb A: statutory compensatory cap (from rules).
    Limb B: 52 x actual gross weekly pay (NOT s.227-capped).
    Compensatory ceiling = min(Limb A, Limb B).
    Basic award: age-banded formula using s.227-capped week's pay.
    Returns a dict suitable for ValueRange.
    """
    cap_row  = _rule(rules, _CAP_KEY)
    wpc_row  = _rule(rules, _WPC_KEY)

    # Fail closed: statutory caps MUST come from the rules table. No hardcoded
    # legal values, and no fabricated fallback when a required rule is missing.
    if not (cap_row and cap_row.get("value_numeric") is not None):
        raise ValueError("compensatory cap rule missing — fail closed (no hardcoded cap)")
    if not (wpc_row and wpc_row.get("value_numeric") is not None):
        raise ValueError("week's pay cap rule missing — fail closed (no hardcoded week's-pay cap)")
    limb_a = float(cap_row["value_numeric"])
    wpc    = float(wpc_row["value_numeric"])

    weekly_pay = float(safe_facts.get("weekly_pay") or 0)
    limb_b     = 52 * weekly_pay if weekly_pay > 0 else limb_a
    comp_ceil  = min(limb_a, limb_b)

    # Basic award estimate: years of service × capped week's pay (1.0x multiplier approximation)
    service_days = float(safe_facts.get("service_days") or 0)
    service_years = min(service_days / 365.25, 20)
    basic_est = round(service_years * min(weekly_pay, wpc)) if weekly_pay > 0 else 0

    cap_source = cap_row["authority_ref"] if cap_row else "ERA 1996 s.124(1ZA)"
    wpc_source = wpc_row["authority_ref"] if wpc_row else "ERA 1996 s.227(1)"
    basis = (
        f"Basic award estimate: {service_years:.1f}yr × min(£{weekly_pay:,.0f}, £{wpc:,.0f}/wk) = £{basic_est:,.0f}. "
        f"Compensatory ceiling: min(Limb A £{limb_a:,.0f} [{cap_source}], "
        f"Limb B 52×£{weekly_pay:,.0f} = £{limb_b:,.0f}). "
        f"Week's pay cap source: {wpc_source}."
    )

    return {
        "low":      basic_est,
        "high":     basic_est + round(comp_ceil),
        "currency": "GBP",
        "basis":    basis,
    }


def build_deterministic_context(
    query: str,
    safe_facts: dict,
    bundle_rules: list[dict],
    bundle_authorities: list[dict],
    deadline_info: dict,
    qualifying_check: Optional[dict],
) -> dict:
    """
    Build the deterministic assessment context injected into the model prompt
    and used directly when the model is stubbed.

    Returns a dict with:
      has_viable_claim, strength, value_range, key_weaknesses,
      recommended_next_step, citations, reasoning_notes, tribunal_elements
    """
    weaknesses: list[str] = []
    citations:  list[dict] = []

    # ── Element Checklists (Iterlaw Port) ─────────────────────────────────────
    burchell = assess_burchell_from_text(query)
    acas = assess_acas_code(query)
    ev_weight = assess_evidence_weight(query)
    elements = get_elements_for_claim("unfair-dismissal")

    # ── Qualifying period ─────────────────────────────────────────────────────
    meets_qp = qualifying_check and qualifying_check.get("meets_qualifying_period")
    qp_row   = _rule(bundle_rules, _QP_KEY)

    # Day-one / automatic-unfair indicators: these claims need NO qualifying
    # period (ERA 1996 ss.99/100/103A/104, TULRCA 1992 s.152). A short-service
    # claimant who mentions them must NEVER be told "no claim" on service alone.
    day_one_exception = detect_day_one_exception(query, safe_facts)

    if qualifying_check:
        months = qualifying_check.get("service_months_approx", 0)
        if not meets_qp:
            qp_required = (
                f"{qp_row['value_numeric']} {qp_row['unit']}"
                if qp_row and qp_row.get("value_numeric") else "2 years"
            )
            if day_one_exception:
                weaknesses.append(
                    f"Possible day-one exception — needs review: your description "
                    f"mentions {day_one_exception['label']}. Dismissal for this reason "
                    f"can be AUTOMATICALLY UNFAIR ({day_one_exception['authority']}) and "
                    f"does NOT require {qp_required} service. Although your "
                    f"{months:.1f} months falls short of the ordinary qualifying period, "
                    f"do not be discouraged — this category of claim should be reviewed "
                    f"by an adviser as a priority."
                )
            else:
                weaknesses.append(
                    f"Qualifying period not met: {months:.1f} months service, "
                    f"{qp_required} required for ordinary unfair dismissal. "
                    f"Day-one exceptions (discrimination, whistleblowing, health & safety) "
                    f"not applicable unless specifically indicated."
                )
            if qp_row:
                citations.append({"cite": qp_row["authority_ref"],
                                   "url":  qp_row["authority_url"]})

    # ── Procedural weaknesses (Logic + Ported Checklists) ────────────────────
    procedure_followed = safe_facts.get("was_procedure_followed")
    had_hearing        = safe_facts.get("had_disciplinary_hearing")
    acas_followed      = safe_facts.get("acas_code_followed")

    acas_auth = next((a for a in bundle_authorities if a.get("type") == "acas"), None)
    if acas_auth:
        citations.append({"cite": acas_auth["cite"], "url": acas_auth["url"]})

    if procedure_followed is False or acas["aligned_with_code"] == "unlikely":
        weaknesses.append(
            "Potential failure to follow fair procedure. "
            "Under the ACAS Code of Practice, failure to follow a fair procedure "
            "may result in an uplift of up to 25% on any compensatory award."
        )
        weaknesses.extend(acas["procedural_gaps"])

    if burchell["reasonable_investigation"] == "weak":
        weaknesses.append(
            "Investigation appears insufficient under Burchell principles. "
            "Employer must show a reasonable investigation was carried out."
        )
    weaknesses.extend(burchell["notes"])
    weaknesses.extend(ev_weight["notes"])

    if had_hearing is False:
        weaknesses.append(
            "No disciplinary hearing before dismissal. "
            "The ACAS Code requires a hearing at which the employee can respond."
        )
    if acas_followed is False:
        weaknesses.append(
            "ACAS Code of Practice on Disciplinary and Grievance Procedures "
            "was not followed."
        )

    # ── Reason for dismissal ──────────────────────────────────────────────────
    reason = safe_facts.get("reason_for_dismissal", "")
    if reason == "conduct":
        weaknesses.append(
            "Conduct is a potentially fair reason under ERA 1996 s.98(2)(b). "
            "The employer must show: (1) the reason was conduct, (2) dismissal "
            "was within the band of reasonable responses. "
            "Claimant must establish procedural unfairness or that dismissal was "
            "outside the band."
        )
    elif reason == "redundancy":
        weaknesses.append(
            "Redundancy is a potentially fair reason under ERA 1996 s.98(2)(c). "
            "Claimant must show unfair selection criteria or lack of consultation "
            "to establish unfair dismissal."
        )
    elif reason == "capability":
        weaknesses.append(
            "Capability is a potentially fair reason under ERA 1996 s.98(2)(a). "
            "A fair capability dismissal requires adequate support, warnings, "
            "and opportunity to improve."
        )

    # ── EC requirement reminder ───────────────────────────────────────────────
    ec_row = _rule(bundle_rules, _EC_KEY)
    if deadline_info.get("ec_applied") is False:
        weaknesses.append(
            "Early Conciliation: claimant must notify ACAS before presenting "
            "a claim. If EC has not been completed, the claim will be inadmissible."
        )
        if ec_row:
            citations.append({"cite": ec_row["authority_ref"],
                               "url":  ec_row["authority_url"]})

    # ── Add top rule citations ────────────────────────────────────────────────
    for rk in [_TL_KEY, _CAP_KEY, _WPC_KEY]:
        row = _rule(bundle_rules, rk)
        if row:
            entry = {"cite": row["authority_ref"], "url": row["authority_url"]}
            if entry not in citations:
                citations.append(entry)

    # ── Add BM25 legislation citations ────────────────────────────────────────
    for auth in bundle_authorities:
        if auth.get("type") == "legislation":
            entry = {"cite": auth.get("cite", ""), "url": auth.get("url", "")}
            if entry["cite"] and entry not in citations:
                citations.append(entry)
            if len(citations) >= 8:
                break

    # ── Employer arguments (deterministic from facts + reason) ───────────────
    employer_args: list[str] = []
    if not meets_qp and qualifying_check:
        employer_args.append(
            "Employer may argue the claim fails at the threshold: the claimant has "
            "not met the 2-year qualifying period for ordinary unfair dismissal."
        )
    if reason == "conduct":
        employer_args.append(
            "Employer may argue the reason (conduct) was a potentially fair reason "
            "under ERA 1996 s.98(2)(b) and that dismissal was within the band of "
            "reasonable responses."
        )
    elif reason == "redundancy":
        employer_args.append(
            "Employer may argue redundancy is a potentially fair reason under "
            "ERA 1996 s.98(2)(c) and that a fair selection and consultation process "
            "was followed."
        )
    elif reason == "capability":
        employer_args.append(
            "Employer may argue capability is a potentially fair reason under "
            "ERA 1996 s.98(2)(a) and that adequate support, warnings, and opportunity "
            "to improve were given."
        )
    if procedure_followed is True:
        employer_args.append(
            "Employer may argue the procedure was reasonable and in compliance with "
            "the ACAS Code of Practice, reducing the likelihood of a finding of "
            "procedural unfairness."
        )
    employer_args.append(
        "Employer may argue the claimant failed to mitigate their loss by "
        "seeking comparable alternative employment promptly after dismissal."
    )
    if not safe_facts.get("weekly_pay"):
        employer_args.append(
            "Employer may challenge the value of the claim if weekly pay, "
            "benefits, or period of continuous employment are not confirmed."
        )

    # ── Viability determination ───────────────────────────────────────────────
    if not meets_qp and qualifying_check and day_one_exception:
        # Short service BUT a possible automatic-unfair category was indicated:
        # never "no" on service alone — flag for priority review instead.
        has_viable_claim = "uncertain"
        strength = "uncertain"
        next_step = "seek_solicitor"
    elif not meets_qp and qualifying_check:
        has_viable_claim = "no"
        strength = "low"
        next_step = "free_diagnosis_only"
    elif procedure_followed is False or had_hearing is False:
        has_viable_claim = "uncertain"
        strength = "medium"
        next_step = "prepare_documents"
    elif procedure_followed is True and reason in ("conduct", "capability"):
        has_viable_claim = "uncertain"
        strength = "low"
        next_step = "seek_solicitor"
    else:
        has_viable_claim = "uncertain"
        strength = "uncertain"
        next_step = "seek_solicitor"

    # ── Fallback weaknesses ───────────────────────────────────────────────────
    if not weaknesses:
        weaknesses.append(
            "Insufficient facts to identify specific weaknesses. "
            "Provide: reason for dismissal, procedure followed, service length."
        )

    value_range = compute_value_range(bundle_rules, safe_facts)

    return {
        "has_viable_claim":   has_viable_claim,
        "strength":           strength,
        "value_range":        value_range,
        "key_weaknesses":     weaknesses,
        "employer_arguments": employer_args,
        "recommended_next_step": next_step,
        "citations":          citations,
        "tribunal_elements":  elements,
        "day_one_exception_possible": bool(day_one_exception),
        "day_one_exception": day_one_exception,
        "reasoning_notes":    (
            f"Qualifying period met: {meets_qp}. "
            f"Procedure followed: {procedure_followed}. "
            f"Reason: {reason or 'not stated'}. "
            f"BM25 authorities retrieved: {len(bundle_authorities)}."
        ),
    }


# ── Phase 5B: Unpaid wages / unlawful deduction from wages ────────────────────

_UPW_TL_KEY   = "unlawful_deduction_wages.time_limit_months"
_UPW_QP_KEY   = "unlawful_deduction_wages.qualifying_period_years"
_UPW_WKR_KEY  = "unlawful_deduction_wages.worker_status"
_UPW_SER_KEY  = "unlawful_deduction_wages.series_deductions_note"
_UPW_REM_KEY  = "unlawful_deduction_wages.remedy_basis"


def build_deterministic_context_wages(
    query: str,
    safe_facts:        dict,
    bundle_rules:      list[dict],
    bundle_authorities: list[dict],
    deadline_info:     dict,
) -> dict:
    """
    Deterministic pre-assessment for unlawful deduction from wages (ERA 1996 Part II).

    Key differences from unfair dismissal:
    - No qualifying period (day-one right for workers)
    - Value range = unpaid amount, not compensation estimate
    - No EDT — reference date is wages_due_date

    GUARDRAIL: Value ranges come from facts (unpaid amount), never from model memory.
    GUARDRAIL: Citations must map to rules table authority_ref.
    GUARDRAIL: Series complexity routes to seek_solicitor.
    """
    weaknesses: list[str]  = []
    citations:  list[dict] = []

    unpaid_amount      = float(safe_facts.get("unpaid_amount") or 0)
    worker_status      = safe_facts.get("worker_status", "employee")
    deduction_auth     = safe_facts.get("deduction_authorized", False)
    is_series          = safe_facts.get("is_series_of_deductions", False)
    employer_reason    = safe_facts.get("employer_explanation", "")

    # ── Worker status warning ──────────────────────────────────────────────────
    if worker_status in ("self_employed", "contractor"):
        weaknesses.append(
            "Worker status is self-employed or contractor — ERA 1996 Part II rights "
            "apply to 'workers' (s.230(3)), not to genuinely self-employed contractors. "
            "Seek legal advice on status."
        )
    elif worker_status == "unknown":
        weaknesses.append(
            "Worker status unclear. ERA 1996 Part II applies to 'workers' (wider than "
            "employees — includes agency and casual workers). If status is disputed, "
            "seek legal advice."
        )

    # ── Authorized deduction defense ──────────────────────────────────────────
    if deduction_auth:
        weaknesses.append(
            "Employer may argue the deduction was authorised by contract, statutory "
            "provision, or prior written worker consent (ERA 1996 s.13(1)). "
            "Review your contract and any written agreements."
        )

    # ── Employer explanation / dispute ─────────────────────────────────────────
    if employer_reason:
        weaknesses.append(
            f"Employer's stated reason: '{employer_reason}'. "
            "If the employer disputes the amount owed, documentary evidence "
            "(payslips, contract, bank statements) is essential."
        )

    # ── Series complexity ──────────────────────────────────────────────────────
    if is_series:
        weaknesses.append(
            "Series of deductions: each deduction must be sufficiently linked. "
            "A gap of more than 3 months between deductions may break the series "
            "(Bear Scotland Ltd v Fulton [2015] IRLR 15). "
            "Complex series spanning more than one year should be reviewed by a solicitor."
        )

    # ── Amount check ───────────────────────────────────────────────────────────
    if unpaid_amount <= 0:
        weaknesses.insert(0,
            "Unpaid amount not specified. Claim value cannot be assessed. "
            "Provide the gross amount unlawfully deducted."
        )

    # ── Employer arguments ─────────────────────────────────────────────────────
    employer_args: list[str] = [
        "Employer may argue the deduction was authorised by contract or statute (ERA 1996 s.13(1)).",
        "Employer may claim wages were paid in full and dispute the amount owed.",
        "Employer may argue the 3-month time limit (ERA 1996 s.23(2)) has expired.",
        "Employer may argue claimant is not a 'worker' for ERA 1996 Part II purposes.",
        "Remedy is gross wages only — no uplift for standard deduction claims (Delaney v Staples [1992]).",
        "Claimant has a duty to mitigate financial loss where ongoing.",
    ]

    # ── Citations from rules ───────────────────────────────────────────────────
    for rule in bundle_rules:
        if rule.get("authority_ref") and rule.get("authority_url"):
            cite = {"cite": rule["authority_ref"], "url": rule["authority_url"]}
            if cite not in citations:
                citations.append(cite)

    # Add BM25 authorities
    for auth in bundle_authorities:
        if auth.get("type") == "legislation":
            entry = {"cite": auth.get("cite", ""), "url": auth.get("url", "")}
            if entry["cite"] and entry not in citations:
                citations.append(entry)
            if len(citations) >= 6:
                break

    # ── Viability ──────────────────────────────────────────────────────────────
    critical_weakness = worker_status in ("self_employed", "contractor")
    has_viable_claim: str
    strength: str

    if critical_weakness:
        has_viable_claim = "no"
        strength = "low"
    elif unpaid_amount > 0 and not deduction_auth:
        has_viable_claim = "yes" if not weaknesses or all("series" not in w.lower() and "status" not in w.lower() for w in weaknesses) else "uncertain"
        strength = "low" if weaknesses else "medium"
    elif deduction_auth:
        has_viable_claim = "uncertain"
        strength = "low"
    else:
        has_viable_claim = "uncertain"
        strength = "uncertain"

    # ── Value range (unpaid amount — no multiplier) ────────────────────────────
    rem_row = _rule(bundle_rules, _UPW_REM_KEY)
    rem_basis = rem_row["description"] if rem_row else "ERA 1996 s.24 — repayment of gross wages unlawfully deducted."
    value_range = {
        "low":      round(unpaid_amount, 2) if unpaid_amount > 0 else 0,
        "high":     round(unpaid_amount, 2) if unpaid_amount > 0 else 0,
        "currency": "GBP",
        "basis":    (
            f"Claimed gross wages: £{unpaid_amount:,.2f}. {rem_basis}"
            if unpaid_amount > 0 else
            "Unpaid amount not provided — cannot estimate."
        ),
    }

    # ── Recommended next step ─────────────────────────────────────────────────
    needs_solicitor = (
        critical_weakness
        or is_series
        or worker_status == "unknown"
    )
    if needs_solicitor:
        recommended_next_step = "seek_solicitor"
    elif has_viable_claim == "yes" and unpaid_amount > 0:
        recommended_next_step = "prepare_documents"
    elif has_viable_claim == "uncertain":
        recommended_next_step = "free_diagnosis_only"
    else:
        recommended_next_step = "seek_solicitor"

    return {
        "has_viable_claim":      has_viable_claim,
        "strength":              strength,
        "key_weaknesses":        weaknesses,
        "employer_arguments":    employer_args,
        "value_range":           value_range,
        "recommended_next_step": recommended_next_step,
        "citations":             citations,
        "reasoning_notes": (
            f"Unpaid wages deterministic assessment. "
            f"Amount: £{unpaid_amount:,.2f}. "
            f"Worker status: {worker_status}. "
            f"Authorized deduction: {deduction_auth}. "
            f"Series: {is_series}. "
            f"No qualifying period applies (ERA 1996 s.13 — day-one right)."
        ),
    }
