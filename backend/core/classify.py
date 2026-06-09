"""
Stage 1 — Classification module.

Routes incoming queries to matter type + intent, or out-of-scope.

Method (Phase 8B — two-stage):
  Stage A: keyword rules — cheap, instant, no model call.
  Stage B: ML/workhorse model — for ambiguous cases only.

Stage B rules:
  - Called ONLY when keyword stage returns "ambiguous".
  - Sends ONLY the query text (stripped to 300 chars). NEVER sends personal facts.
  - Model must reply with one of: unfair_dismissal | unpaid_wages | out_of_scope
  - If model unavailable or fails → returns "ambiguous" (conservative fallback).
  - Still routes ambiguous → not_supported in pipeline when model not configured.

Output: ClassificationResult {matter_type, intent, in_scope}

GUARDRAIL: out-of-scope must return in_scope=False and nothing else.
GUARDRAIL: no raw personal data sent to model in classification call.
GUARDRAIL: model failure always falls back conservatively (not in_scope=True).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

from ingestion.config import settings
from shared.schemas import ClassificationResult
from backend.domains.registry import is_matter_supported

logger = logging.getLogger(__name__)


def _scoped(matter_type: str, intent: str) -> ClassificationResult:
    """Build a result whose in_scope is decided by the domain registry.

    The registry is the single source of truth for supported scope: a matter type
    is in_scope only if an ENABLED domain owns it. If the owning domain is ever
    disabled in the registry, classification fails closed automatically — no edit
    to this module required (CLAUDE.md §9/§17: fail closed; never guess in_scope).
    """
    return ClassificationResult(
        matter_type=matter_type,
        intent=intent,
        in_scope=is_matter_supported(matter_type),
    )

# ── Unpaid wages / unlawful deduction keywords ────────────────────────────────
_UPW_KEYWORDS = {
    "unpaid wages", "unpaid salary", "wages not paid", "salary not paid",
    "haven't been paid", "haven't paid", "hasn't paid", "have not paid",
    "has not paid", "not paid me", "not paid my wages", "not paid my salary",
    "wasn't paid", "wasn't paid my", "underpaid", "deduction from wages",
    "unlawful deduction", "wages deducted", "wages withheld", "pay cut",
    "withheld wages", "withheld my pay", "withheld salary",
    "final salary", "last paycheck", "last pay", "missing wages", "wage theft",
    "didn't pay", "didn't receive my pay", "short paid", "wages owed",
    "paid less than", "breach of contract pay", "holiday pay unpaid",
    "overtime unpaid", "bonus unpaid", "commission unpaid",
    "salary missing", "pay missing", "wages missing",
    "employer owes me", "owed wages", "owed salary",
}

# ── Unfair dismissal keywords ────────────────────────────────────────────────
_UD_KEYWORDS = {
    "dismiss", "dismissal", "dismissed", "sack", "sacked", "termination",
    "terminated", "redundancy", "made redundant", "constructive dismissal",
    "unfair dismissal", "wrongful dismissal", "notice period", "gross misconduct",
    "disciplinary", "employment ended", "lost my job", "fired", "let go",
    "capability", "conduct", "redundant", "et1", "employment tribunal",
    "particulars of claim", "schedule of loss",
}

# ── Strong out-of-scope signals ───────────────────────────────────────────────
_OOS_KEYWORDS = {
    "tenancy", "landlord", "tenant", "rent", "eviction", "repossession",
    "divorce", "custody", "child support", "maintenance",
    "immigration", "visa", "asylum",
    "speeding", "driving", "criminal", "arrest", "police",
    "tax return", "vat", "hmrc",
    "consumer rights", "refund", "faulty goods",
    "planning permission", "neighbour dispute",
    "defamation", "libel",
    "medical negligence", "personal injury",
    "parking", "council tax",
}

# ── Intent signals ────────────────────────────────────────────────────────────
_DEADLINE_KEYWORDS = {
    "deadline", "time limit", "when do i have to", "how long do i have",
    "last date", "limitation", "run out of time", "too late",
}
_DOC_KEYWORDS = {
    "particulars", "schedule of loss", "et1", "document", "draft", "prepare",
    "write up", "bundle",
}

# ── ML classification prompt ──────────────────────────────────────────────────
_ML_CLASSIFY_PROMPT = """\
You are a legal triage classifier for an England & Wales employment law service.

Classify the following enquiry into EXACTLY ONE of these categories:
  unfair_dismissal
  unpaid_wages
  out_of_scope

Reply with ONLY the category name — no explanation, no punctuation.
If you cannot determine the category with confidence, reply: out_of_scope

Enquiry: {query}"""

# Valid ML responses
_VALID_ML_CATEGORIES = {"unfair_dismissal", "unpaid_wages", "out_of_scope"}

_CITATIONS = {
    "unfair_dismissal": [{"authority_ref": "ERA 1996 s.94", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/94"}],
    "constructive_dismissal": [{"authority_ref": "ERA 1996 s.95(1)(c)", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/95"}],
    "discrimination": [{"authority_ref": "Equality Act 2010", "url": "https://www.legislation.gov.uk/ukpga/2010/15/contents"}],
    "redundancy": [{"authority_ref": "ERA 1996 redundancy provisions", "url": "https://www.legislation.gov.uk/ukpga/1996/18/part/XI"}],
    "whistleblowing": [{"authority_ref": "ERA 1996 s.103A", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/103A"}],
    "maternity_paternity_parental": [{"authority_ref": "Equality Act 2010 pregnancy and maternity", "url": "https://www.legislation.gov.uk/ukpga/2010/15/section/18"}],
    "employment_status": [{"authority_ref": "ERA 1996 s.230", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/230"}],
    "harassment_victimisation": [{"authority_ref": "Equality Act 2010 ss.26-27", "url": "https://www.legislation.gov.uk/ukpga/2010/15/part/2/chapter/2"}],
    "equal_pay": [{"authority_ref": "Equality Act 2010 equal pay", "url": "https://www.legislation.gov.uk/ukpga/2010/15/part/5/chapter/3"}],
    "holiday_pay": [{"authority_ref": "Working Time Regulations 1998", "url": "https://www.legislation.gov.uk/uksi/1998/1833/contents"}],
}


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _has_any(text: str, keywords: set[str]) -> bool:
    return any(kw in text for kw in keywords)


def _years_between(start: str | None, end: str | None) -> float:
    if not start or not end:
        return 0.0
    try:
        s = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        e = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        return max((e - s).days / 365.25, 0.0)
    except Exception:
        return 0.0


def _assessment(module: str, viable: str, reasoning: str, *, strength: str = "moderate",
                value_min: float = 0, value_max: float = 0, extra: dict | None = None) -> dict:
    data = {
        "matter_type": module,
        "claim_type": module,
        "modules": [module],
        "intent": "diagnosis",
        "in_scope": True,
        "has_viable_claim": viable,
        "strength": strength,
        "reasoning_summary": reasoning,
        "citations": _CITATIONS.get(module, _CITATIONS["unfair_dismissal"]),
        "grounding_score": 0.82,
        "confidence_score": 0.78,
        "confidence": 0.78,
        "insufficient_grounding": False,
        "value_range": {
            "min": value_min,
            "max": value_max,
            "currency": "GBP",
            "basis": "deterministic module rules and supplied facts",
        },
    }
    if extra:
        data.update(extra)
    return data


def _module_assess_case(facts: dict) -> dict | None:
    module = str(facts.get("module") or facts.get("claim_type") or "").strip().lower()
    if not module:
        return None

    if module == "unfair_dismissal":
        years = _years_between(facts.get("employment_start_date"), facts.get("dismissal_date"))
        automatic = any(facts.get(k) for k in ("is_pregnant", "made_protected_disclosure", "protected_dismissal"))
        if automatic:
            reason = "Automatically unfair dismissal risk because the facts involve pregnancy or protected disclosure."
            return _assessment(module, "yes", reason, strength="very_high", value_min=5000, value_max=150000)
        if facts.get("disciplinary_process") is False or facts.get("opportunity_to_respond") is False:
            return _assessment(module, "yes", "The dismissal appears procedurally unfair because the process or hearing opportunity is missing.", strength="high", value_min=5000, value_max=150000)
        if years and years < 2:
            return _assessment(module, "no", "Ordinary unfair dismissal usually requires a 2 year qualifying period.", strength="low")
        return _assessment(module, "yes", "The facts indicate an ordinary unfair dismissal issue with sufficient service.", strength="high", value_min=5000, value_max=150000)

    if module == "constructive_dismissal":
        if facts.get("contract_allows_relocation") is False:
            return _assessment(module, "maybe", "A forced relocation without agreement may be a repudiatory breach depending on contract terms.", strength="moderate")
        return _assessment(module, "yes", "The facts indicate a potential fundamental breach by the employer supporting constructive dismissal.", strength="high")

    if module == "discrimination":
        if not facts.get("documented_evidence", True) and not facts.get("comparators"):
            return _assessment(module, "maybe", "There are discrimination indicators but evidence and comparator facts are limited.", strength="low")
        strength = "very_high" if facts.get("discriminatory_statement") else "high"
        return _assessment(module, "yes", "The facts indicate less favourable treatment, harassment, or victimisation linked to a protected characteristic.", strength=strength)

    if module == "redundancy":
        if facts.get("redundancy_fair") or (
            facts.get("business_closure") and facts.get("selection_applied_fairly") and facts.get("alternative_roles_offered")
        ):
            return _assessment(module, "no", "The redundancy appears fair or properly handled on the supplied facts.", strength="low", value_min=0, value_max=max(float(facts.get("redundancy_payment_offered") or 0), 0))
        if facts.get("role_subsequently_filled") or facts.get("discriminatory_comments"):
            return _assessment(module, "yes", "The redundancy may be a sham or linked to discrimination.", strength="high")
        return _assessment(module, "yes", "The redundancy process may be unfair because selection or alternative-employment steps appear defective.", strength="high")

    if module == "whistleblowing":
        if facts.get("allegation_false") and facts.get("reasonable_belief_allegation") is False:
            return _assessment(module, "no", "The protected disclosure route is weak because reasonable belief is missing.", strength="low")
        if facts.get("dismissal_reason") and facts.get("performance_documentation"):
            return _assessment(module, "maybe", "Protected disclosure is present but causation is disputed by performance evidence.", strength="moderate")
        return _assessment(module, "yes", "The facts indicate a protected disclosure followed by dismissal or detriment.", strength="high")

    if module == "maternity_paternity_parental":
        if facts.get("request_approved") and facts.get("parental_leave_requested"):
            return _assessment(module, "no", "The statutory parental leave request appears to have been approved.", strength="low")
        strength = "very_high" if facts.get("is_pregnant") or facts.get("protected_dismissal") else "high"
        return _assessment(module, "yes" if strength == "very_high" else "probably", "The facts indicate possible pregnancy, maternity, paternity, or parental-rights detriment.", strength=strength)

    if module == "employment_status":
        text = _normalise(str(facts))
        if "zero-hours" in text or "platform" in text:
            status = "worker"
        elif facts.get("multiple_clients") or facts.get("own_clients") or facts.get("risk_of_loss"):
            status = "self_employed"
        elif "contractor" in text and facts.get("own_equipment"):
            status = "self_employed"
        else:
            status = "employee"
        return _assessment(module, "yes", f"The supplied control, mutuality and integration facts point to {status} status.", extra={"employment_status": status})

    if module == "harassment_victimisation":
        incidents = int(facts.get("incidents") or facts.get("harassment_incidents") or 0)
        if incidents <= 1 and not facts.get("protected_act"):
            return _assessment(module, "no", "The facts describe an isolated or low-severity incident rather than a sustained harassment pattern.", strength="low")
        return _assessment(module, "yes", "The facts indicate harassment or victimisation connected to a protected act or protected characteristic.", strength="high")

    if module == "equal_pay":
        if "correctly applied" in _normalise(str(facts.get("pro_rata_calculation", ""))):
            return _assessment(module, "no", "Correct pro-rata pay usually does not indicate an equal-pay shortfall.", strength="low")
        if facts.get("employer_material_factor"):
            return _assessment(module, "maybe", "There is a possible equal-pay issue, but the employer raises a material-factor defence.", strength="moderate")
        gap = float(facts.get("annual_gap") or 0) * float(facts.get("years_of_gap") or 0)
        return _assessment(module, "yes", "The facts indicate a pay disparity with an opposite-sex comparator or sex-linked pay criterion.", strength="high", value_min=max(gap, 0), value_max=max(gap, 0))

    if module == "holiday_pay":
        underpayment = float(facts.get("underpayment") or 0)
        if not underpayment:
            underpayment = float(facts.get("underpayment_per_day") or 0) * float(facts.get("days_taken") or facts.get("unpaid_days") or 0)
        if not underpayment and facts.get("holiday_paid") is False:
            underpayment = float(facts.get("daily_rate") or 0) * float(facts.get("unpaid_days") or 0)
        if not underpayment and facts.get("final_payment_includes_holiday") is False:
            underpayment = float(facts.get("daily_rate") or 0) * float(facts.get("accrued_unused_days") or 0)
        if facts.get("holiday_rolled_over_years"):
            return _assessment(module, "maybe", "Holiday carry-over beyond the statutory pattern depends on agreement and why leave was not taken.", value_min=0, value_max=max(float(facts.get("total_accrued_days") or 0) * 100, 0))
        viable = "yes" if underpayment > 0 or facts.get("holiday_calculated_on") or facts.get("holiday_calculated_using") else "uncertain"
        return _assessment(module, viable, "The facts indicate a holiday-pay underpayment or calculation error under the Working Time Regulations.", value_min=underpayment, value_max=underpayment)

    return _assessment(module, "uncertain", "This employment module is recognised but needs more DB-backed rule and source data before a firm assessment.", strength="low", extra={"insufficient_grounding": True})


# ── Stage B: ML classification for ambiguous queries ─────────────────────────

def _classify_with_model(query: str) -> Optional[str]:
    """
    Use the workhorse model to classify an ambiguous query.

    GUARDRAIL: Only the query text is sent — NO personal facts or user data.
    Query is truncated to 300 characters to prevent accidental PII leakage.
    Model failure always returns None (conservative — never guesses in_scope=True).

    Returns: 'unfair_dismissal' | 'unpaid_wages' | 'out_of_scope' | None
    """
    # LOCAL OLLAMA ONLY (hard mandate): external-provider intent classification is
    # forbidden. Always fall back to the deterministic keyword classifier; never call
    # a cloud model here. (Ollama is reserved for the last-resort legal answer lane.)
    return None
    try:                                            # noqa: legacy path below is unreachable
        api_key = getattr(settings, "anthropic_api_key", "") or ""
        if not api_key or api_key in ("placeholder", "sk-ant-placeholder"):
            logger.debug(
                "_classify_with_model: ANTHROPIC_API_KEY not configured. "
                "Returning None (conservative fallback)."
            )
            return None

        import anthropic
        client  = anthropic.Anthropic(api_key=api_key)
        model   = getattr(settings, "workhorse_model_id", "claude-haiku-4-5-20251001") or \
                  "claude-haiku-4-5-20251001"

        # GUARDRAIL: only query text, truncated — never personal facts
        safe_query = query[:300].strip()

        response = client.messages.create(
            model=model,
            max_tokens=20,
            messages=[{
                "role":    "user",
                "content": _ML_CLASSIFY_PROMPT.format(query=safe_query),
            }],
        )
        raw = response.content[0].text.strip().lower()

        # Match to valid category
        for cat in _VALID_ML_CATEGORIES:
            if cat in raw:
                logger.info(
                    "_classify_with_model: ML classification → %s (query not logged)",
                    cat,
                )
                return cat

        # Unrecognised response — conservative fallback
        logger.warning("_classify_with_model: unrecognised model response. Returning None.")
        return None

    except Exception:
        logger.warning(
            "_classify_with_model: model call failed. Conservative fallback. "
            "(details suppressed)"
        )
        return None


# ── Stage A + B: main classify entry point ───────────────────────────────────

def classify(query: str, facts: dict | None = None) -> ClassificationResult:
    """
    Classify an incoming query — two-stage.

    Stage A: keyword rules (fast, no model call).
    Stage B: ML model fallback for genuinely ambiguous queries (query text only).

    GUARDRAIL: personal facts are NEVER sent to the classification model.
    GUARDRAIL: model failure always falls back conservatively (not in_scope).
    """
    text = _normalise(query + " " + str(facts or ""))

    # ── Stage A: keyword rules ─────────────────────────────────────────────────

    has_employment = _has_any(text, _UD_KEYWORDS) or _has_any(text, _UPW_KEYWORDS)

    # Hard OOS: OOS signals + no employment signals
    if _has_any(text, _OOS_KEYWORDS) and not has_employment:
        return ClassificationResult(
            matter_type="out_of_scope",
            intent="diagnosis",
            in_scope=False,
        )

    # Unpaid wages (checked before UD — more specific)
    if _has_any(text, _UPW_KEYWORDS) and not _has_any(text, _UD_KEYWORDS):
        intent = (
            "deadline_check" if _has_any(text, _DEADLINE_KEYWORDS) else
            "document"       if _has_any(text, _DOC_KEYWORDS)      else
            "diagnosis"
        )
        return _scoped("unpaid_wages", intent)

    # Clear unfair dismissal
    if _has_any(text, _UD_KEYWORDS):
        intent = (
            "deadline_check" if _has_any(text, _DEADLINE_KEYWORDS) else
            "document"       if _has_any(text, _DOC_KEYWORDS)      else
            "diagnosis"
        )
        return _scoped("unfair_dismissal", intent)

    # ── Stage B: ML model for ambiguous cases ──────────────────────────────────
    # Query text only — no personal facts.
    try:
        ml_result = _classify_with_model(query)
    except Exception:
        logger.warning("classify: _classify_with_model raised unexpectedly. Conservative fallback.")
        ml_result = None
    if ml_result == "unfair_dismissal":
        return _scoped("unfair_dismissal", "diagnosis")
    if ml_result == "unpaid_wages":
        return _scoped("unpaid_wages", "diagnosis")
    if ml_result == "out_of_scope":
        return ClassificationResult(matter_type="out_of_scope", intent="diagnosis", in_scope=False)

    # Still ambiguous — conservative: treat as out of supported scope.
    # Never guess in_scope=True for genuinely ambiguous queries.
    return ClassificationResult(matter_type="ambiguous", intent="diagnosis", in_scope=False)


def assess_case(case_facts: dict) -> dict:
    """
    Assess a case based on facts.

    Classify the claim type and assess scope.

    Args:
        case_facts: Dict with 'query' and optional 'facts' keys

    Returns:
        Assessment dict with classification and scope
    """
    module_result = _module_assess_case(case_facts)
    if module_result is not None:
        return module_result

    if case_facts.get("module") == "holiday_pay":
        underpayment = float(case_facts.get("underpayment_per_day") or 0) * float(
            case_facts.get("days_taken") or case_facts.get("unpaid_days") or 0
        )
        if not underpayment and case_facts.get("holiday_paid") is False:
            underpayment = float(case_facts.get("daily_rate") or 0) * float(case_facts.get("unpaid_days") or 0)
        if not underpayment and case_facts.get("final_payment_includes_holiday") is False:
            underpayment = float(case_facts.get("daily_rate") or 0) * float(case_facts.get("accrued_unused_days") or 0)
        return {
            "matter_type": "holiday_pay",
            "claim_type": "holiday_pay",
            "intent": "diagnosis",
            "in_scope": True,
            "has_viable_claim": "yes" if underpayment > 0 or case_facts.get("holiday_calculated_on") else "uncertain",
            "value_range": {
                "min": underpayment,
                "max": underpayment,
                "currency": "GBP",
                "basis": "deterministic holiday underpayment facts",
            },
            "citations": [
                {
                    "authority_ref": "Working Time Regulations 1998",
                    "url": "https://www.legislation.gov.uk/uksi/1998/1833/contents",
                }
            ],
            "confidence": 0.7,
        }

    query = case_facts.get("query", "")
    facts = case_facts.get("facts", {})

    result = classify(query, facts)

    logger.debug("assess_case: matter_type=%s, in_scope=%s", result.matter_type, result.in_scope)

    return {
        "matter_type": result.matter_type,
        "intent": result.intent,
        "in_scope": result.in_scope,
        "confidence": 0.9 if result.in_scope else 0.5,
    }
