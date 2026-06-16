"""
AI Router  -  controlled by Brain.

Routes queries to the appropriate processing path:
  - lite_llm_plus_glossary: simple generic questions
  - rules_engine_only: deterministic deadline/eligibility
  - rag_plus_rules: citation-backed legal questions (no LLM)
  - full_legal_pipeline: personal case analysis (full Brain)
  - human_review_required: high-risk, complex, or urgent cases

GUARDRAIL: The router never sends personal facts to Lite LLM.
           Lite LLM is only allowed for generic, non-personal queries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# ── Risk/complexity scoring ───────────────────────────────────────────────────

_GENERIC_PATTERNS = [
    r"what is (unfair dismissal|wrongful dismissal|acas|early conciliation|redundancy)",
    r"how (does|do) (tribunal|employment tribunal|acas)",
    r"define (unfair|wrongful|dismissal|tribunal|settlement)",
    r"explain (unfair|wrongful|dismissal|tribunal|acas|redundancy)",
    r"what does .* (mean|stand for)",
    r"what (is|are) the rules for",
    r"what (is|are) .* (time limit|deadline|qualifying period)",
]

_HIGH_RISK_PATTERNS = [
    r"whistleblow",
    r"discrimination",
    r"protected characteristic",
    r"pregnancy",
    r"maternity",
    r"disability",
    r"settlement agreement",
    r"compromise agreement",
    r"tribunal (submission|hearing|case)",
    r"particulars of claim",
    r"et1",
]

_PERSONAL_SIGNALS = [
    r"\b(i|my|me|we|our)\b.*(dismiss|sack|fired|redundan|paid|wage|salary)",
    r"(my employer|my manager|my boss)",
    r"(last (week|month|year)|yesterday|today|on \w+ \d+)",
    r"(dismissed|sacked|fired|let go) (on|at|in|last|this)",
    r"(i was|i have been|i got)",
]

_DEADLINE_PATTERNS = [
    r"\b(when|how long|time limit|deadline|limit|days?|months?|years?)\b.*\b(claim|tribunal|et1|acas|appeal)\b",
    r"\b(claim|tribunal|acas)\b.*\b(when|deadline|by when|time limit)\b",
]


def _score_query(message: str, facts: dict) -> dict:
    """Compute routing dimensions from query text and facts."""
    lowered = message.lower()
    has_personal_facts = bool(facts.get("edt") or facts.get("service_start_date") or
                              facts.get("wages_due_date"))

    is_generic = any(re.search(p, lowered) for p in _GENERIC_PATTERNS) and not has_personal_facts
    is_high_risk = any(re.search(p, lowered) for p in _HIGH_RISK_PATTERNS)
    is_personal = has_personal_facts or any(re.search(p, lowered) for p in _PERSONAL_SIGNALS)
    is_deadline_only = (
        any(re.search(p, lowered) for p in _DEADLINE_PATTERNS)
        and has_personal_facts
        and not is_high_risk
    )

    # Risk level
    if is_high_risk:
        risk = "high"
    elif is_personal:
        risk = "medium"
    else:
        risk = "low"

    return {
        "is_generic": is_generic,
        "is_high_risk": is_high_risk,
        "is_personal": is_personal,
        "is_deadline_only": is_deadline_only,
        "has_personal_facts": has_personal_facts,
        "risk_level": risk,
    }


@dataclass
class RoutingDecision:
    path: str                        # Processing path identifier
    risk_level: str                  # "low" | "medium" | "high"
    agents: list[str]
    use_llm: bool
    use_rag: bool
    use_rules_engine: bool
    evaluation_required: bool
    human_review_flag: bool
    reason: str
    lite_llm_safe: bool              # True if Lite LLM may be used (no personal facts)

    def to_dict(self) -> dict:
        return {
            "selected_path": self.path,
            "risk_level": self.risk_level,
            "agents": self.agents,
            "use_llm": self.use_llm,
            "use_rag": self.use_rag,
            "use_rules_engine": self.use_rules_engine,
            "evaluation_required": self.evaluation_required,
            "human_review_flag": self.human_review_flag,
            "reason": self.reason,
            "lite_llm_safe": self.lite_llm_safe,
        }


def route(message: str, facts: dict, claim_type: Optional[str] = None) -> RoutingDecision:
    """
    Determine the processing path for a query.

    Called by Brain at step 7. The routing decision controls:
      - Which LLM (if any) is called
      - Which agents are activated
      - Whether evaluation is required
      - Whether human review is flagged

    GUARDRAIL: Lite LLM path is only used when lite_llm_safe=True.
               Personal facts must NEVER go to Lite LLM.
    """
    dims = _score_query(message, facts)

    # ── Path 1: Generic question  -  lite LLM + glossary ───────────────────────
    if dims["is_generic"] and not dims["has_personal_facts"]:
        return RoutingDecision(
            path="lite_llm_plus_glossary",
            risk_level="low",
            agents=["safety_abuse"],
            use_llm=True,
            use_rag=False,
            use_rules_engine=False,
            evaluation_required=False,
            human_review_flag=False,
            reason="generic_non_personal_question",
            lite_llm_safe=True,
        )

    # ── Path 2: Deadline-only  -  rules engine ─────────────────────────────────
    if dims["is_deadline_only"] and not dims["is_high_risk"]:
        return RoutingDecision(
            path="rules_engine_only",
            risk_level="low",
            agents=["deadline", "citation_verification"],
            use_llm=False,
            use_rag=True,
            use_rules_engine=True,
            evaluation_required=True,
            human_review_flag=False,
            reason="deterministic_deadline_only",
            lite_llm_safe=False,
        )

    # ── Path 3: High-risk  -  full pipeline + human review ─────────────────────
    if dims["is_high_risk"]:
        return RoutingDecision(
            path="full_legal_pipeline_plus_human_review",
            risk_level="high",
            agents=["employment_law", "deadline", "evidence", "risk_review",
                    "citation_verification", "evaluation", "human_review"],
            use_llm=True,
            use_rag=True,
            use_rules_engine=True,
            evaluation_required=True,
            human_review_flag=True,
            reason="high_risk_claim_pattern",
            lite_llm_safe=False,
        )

    # ── Path 4: Personal case  -  full pipeline ────────────────────────────────
    if dims["is_personal"] or dims["has_personal_facts"]:
        return RoutingDecision(
            path="full_legal_pipeline",
            risk_level="medium",
            agents=["employment_law", "deadline", "evidence",
                    "citation_verification", "evaluation"],
            use_llm=True,
            use_rag=True,
            use_rules_engine=True,
            evaluation_required=True,
            human_review_flag=False,
            reason="personal_case_facts_present",
            lite_llm_safe=False,
        )

    # ── Default: RAG + rules, no personal LLM ────────────────────────────────
    return RoutingDecision(
        path="rag_plus_rules",
        risk_level="low",
        agents=["employment_law", "citation_verification"],
        use_llm=False,
        use_rag=True,
        use_rules_engine=True,
        evaluation_required=False,
        human_review_flag=False,
        reason="generic_legal_question_with_rag",
        lite_llm_safe=False,
    )
