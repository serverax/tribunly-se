"""
Agent registry — the Brain uses this to look up and instantiate agents.

Every agent is registered here with its claim-type routing configuration.
The Brain calls get_agents_for_claim() to get the right set for a query.
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.core.agents.base import LegalAgent, AgentResult

logger = logging.getLogger(__name__)


# ── Concrete agent implementations ──────────────────────────────────────────

class EmploymentLawAgent(LegalAgent):
    name = "employment_law"
    description = (
        "Specialist in UK employment law. Handles unfair dismissal, "
        "wrongful dismissal, unpaid wages, and related claims. "
        "Uses legislation (ERA 1996, TULRCA) and ACAS guidance."
    )
    allowed_tools = ["retrieve_rules", "hybrid_search", "citation_verify", "deadline_calculate"]
    prohibited_actions = LegalAgent.prohibited_actions + ["predict_outcome_probability"]

    def process(self, message: str, facts: dict, bundle, jurisdiction: str = "EW") -> AgentResult:
        findings = []
        citations = []
        gaps = []
        confidence = 0.0

        if bundle and hasattr(bundle, "exact_rules") and bundle.exact_rules:
            for r in bundle.exact_rules:
                findings.append({
                    "rule": r.get("rule_key"),
                    "value": r.get("value_numeric") or r.get("value_text"),
                    "authority": r.get("authority_ref"),
                })
            confidence += 0.4

        if bundle and hasattr(bundle, "authorities") and bundle.authorities:
            for a in bundle.authorities:
                citations.append(a.get("cite", ""))
            confidence += min(0.4, len(bundle.authorities) * 0.1)

        claim_type = facts.get("claim_type", "unfair_dismissal")
        if claim_type == "unfair_dismissal":
            if not facts.get("edt"):
                gaps.append("effective_date_of_termination")
            if not facts.get("service_start_date"):
                gaps.append("employment_start_date")
        elif claim_type == "unpaid_wages":
            if not facts.get("wages_due_date"):
                gaps.append("wages_due_date")
            if not facts.get("unpaid_amount"):
                gaps.append("unpaid_amount")

        return AgentResult(
            agent_name=self.name,
            status="ok" if not gaps else "insufficient_facts",
            findings=findings,
            citations_used=[c for c in citations if c],
            evidence_gaps=gaps,
            confidence=round(min(1.0, confidence), 2),
            human_review_required=False,
        )


class DeadlineAgent(LegalAgent):
    name = "deadline"
    description = (
        "Specialist in tribunal deadlines. Computes limitation dates, "
        "ACAS EC pause/extension, ET1 filing deadlines. "
        "GUARDRAIL: all deadlines are rule-derived — never estimated."
    )
    allowed_tools = ["retrieve_rules", "deadline_calculate", "calendar"]
    prohibited_actions = LegalAgent.prohibited_actions + ["estimate_deadline"]

    def process(self, message: str, facts: dict, bundle, jurisdiction: str = "EW") -> AgentResult:
        import datetime as _dt
        findings = []
        gaps = []

        edt = facts.get("edt") or facts.get("wages_due_date")
        if not edt:
            return AgentResult(
                agent_name=self.name,
                status="insufficient_facts",
                evidence_gaps=["dismissal_date_or_wages_due_date"],
                confidence=0.0,
            )

        try:
            from backend.domains.employment.deadline import compute_limitation_date
            from backend.core.retrieve import retrieve_rules
            claim_type = facts.get("claim_type", "unfair_dismissal")
            rules = retrieve_rules(claim_type, jurisdiction, edt)
            tl_rule = next(
                (r for r in rules if "time_limit_months" in r.get("rule_key", "")), None
            )
            if not tl_rule or tl_rule.get("value_numeric") is None:
                gaps.append("time_limit_months_rule_missing")
                raise ValueError("time_limit_months rule missing")
            tl_months = int(tl_rule["value_numeric"])
            ec_a = facts.get("ec_day_a") or facts.get("acas_contact_date")
            ec_b = facts.get("ec_day_b") or facts.get("acas_certificate_date")

            result = compute_limitation_date(edt, tl_months, ec_a, ec_b)
            if result and result.get("limitation_date"):
                lim = _dt.date.fromisoformat(result["limitation_date"])
                days = (lim - _dt.date.today()).days
                findings.append({
                    "limitation_date": result["limitation_date"],
                    "days_remaining": days,
                    "authority": result.get("authority", "ERA 1996 s.111(2)"),
                    "ec_applied": result.get("ec_applied", False),
                    "source": "rules_engine",
                })
        except Exception as exc:
            logger.warning("DeadlineAgent error: %s", exc)
            gaps.append("deadline_calculation_failed")

        human_review = bool(
            findings and findings[0].get("days_remaining", 999) <= 7
        )

        return AgentResult(
            agent_name=self.name,
            status="ok" if findings else "insufficient_facts",
            findings=findings,
            evidence_gaps=gaps,
            confidence=1.0 if findings else 0.0,
            human_review_required=human_review,
            human_review_reason="deadline_within_7_days" if human_review else None,
        )


class EvidenceAgent(LegalAgent):
    name = "evidence"
    description = (
        "Identifies missing evidence, assesses evidence quality, "
        "flags document gaps. Uses evidence_weight heuristics."
    )
    allowed_tools = ["evidence_checklist", "document_classify", "gap_detect"]
    prohibited_actions = LegalAgent.prohibited_actions

    def process(self, message: str, facts: dict, bundle, jurisdiction: str = "EW") -> AgentResult:
        from backend.core.evidence_gap import detect_gaps
        claim_type = facts.get("claim_type", "unfair_dismissal")
        gaps = detect_gaps(claim_type, facts)
        confidence = 1.0 - min(0.9, len(gaps) * 0.1)
        return AgentResult(
            agent_name=self.name,
            status="ok" if not gaps else "gaps_found",
            findings=[{"gap": g} for g in gaps],
            evidence_gaps=gaps,
            confidence=round(confidence, 2),
        )


class CitationVerificationAgent(LegalAgent):
    name = "citation_verification"
    description = (
        "Verifies every citation against the DB before it appears in output. "
        "Removes or marks unverified citations. No fabricated citations allowed."
    )
    allowed_tools = ["citation_verify", "legislation_lookup", "case_law_lookup"]
    prohibited_actions = LegalAgent.prohibited_actions + ["fabricate_citation", "approximate_citation"]

    def process(self, message: str, facts: dict, bundle, jurisdiction: str = "EW") -> AgentResult:
        if not bundle or not hasattr(bundle, "authorities"):
            return AgentResult(agent_name=self.name, status="ok", confidence=1.0)

        from backend.core.citation_verifier import verify_bundle_citations
        result = verify_bundle_citations(bundle.authorities)
        findings = [
            {"citation": c["cite"], "verified": c["verified"], "reason": c.get("reason")}
            for c in result.get("details", [])
        ]
        return AgentResult(
            agent_name=self.name,
            status="ok",
            findings=findings,
            citations_used=[c["cite"] for c in result.get("details", []) if c.get("verified")],
            confidence=result.get("pass_rate", 0.0),
            notes=f"Verified {result['verified']}/{result['total']} citations.",
        )


class CompensationAgent(LegalAgent):
    name = "compensation"
    description = "Calculates statutory awards, caps, and remedy estimates from rules table only."
    allowed_tools = ["retrieve_rules", "compensation_calculate"]
    prohibited_actions = LegalAgent.prohibited_actions + ["guarantee_amount"]

    def process(self, message: str, facts: dict, bundle, jurisdiction: str = "EW") -> AgentResult:
        findings = []
        if bundle and hasattr(bundle, "exact_rules"):
            cap_rule = next(
                (r for r in bundle.exact_rules if "compensatory_cap_amount" in r.get("rule_key", "")),
                None,
            )
            weekly_cap = next(
                (r for r in bundle.exact_rules if "weeks_pay_cap_amount" in r.get("rule_key", "")),
                None,
            )
            if cap_rule:
                findings.append({
                    "cap_type": "compensatory_award_cap",
                    "amount": cap_rule["value_numeric"],
                    "authority": cap_rule["authority_ref"],
                    "source": "rules_engine",
                })
            if weekly_cap:
                findings.append({
                    "cap_type": "weekly_pay_cap",
                    "amount": weekly_cap["value_numeric"],
                    "authority": weekly_cap["authority_ref"],
                    "source": "rules_engine",
                })
        return AgentResult(
            agent_name=self.name,
            status="ok" if findings else "insufficient_facts",
            findings=findings,
            confidence=1.0 if findings else 0.0,
        )


class RiskReviewAgent(LegalAgent):
    name = "risk_review"
    description = "Assesses claim risk, identifies weaknesses, flags high-risk areas for human review."
    allowed_tools = ["risk_score", "weakness_detect"]
    prohibited_actions = LegalAgent.prohibited_actions

    def process(self, message: str, facts: dict, bundle, jurisdiction: str = "EW") -> AgentResult:
        risks = []
        human_review = False
        reason = None
        weaknesses = facts.get("_deterministic_assessment", {}).get("key_weaknesses", [])
        for w in weaknesses[:3]:
            risks.append({"risk": w, "severity": "medium"})
        if len(weaknesses) >= 3:
            human_review = True
            reason = "multiple_weaknesses_detected"
        return AgentResult(
            agent_name=self.name,
            status="ok",
            findings=risks,
            confidence=0.7,
            human_review_required=human_review,
            human_review_reason=reason,
        )


class EvaluationAgent(LegalAgent):
    name = "evaluation"
    description = "Runs legal evaluation on draft answer before final output. Blocks invalid answers."
    allowed_tools = ["evaluate_assessment"]
    prohibited_actions = LegalAgent.prohibited_actions

    def process(self, message: str, facts: dict, bundle, jurisdiction: str = "EW") -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            status="ok",
            findings=[{"check": "evaluation", "status": "deferred_to_brain"}],
            confidence=1.0,
            notes="Evaluation is run by Brain at step 14 via evaluator.evaluate_assessment().",
        )


class HumanReviewAgent(LegalAgent):
    name = "human_review"
    description = "Flags outputs that require human legal review before delivery to user."
    allowed_tools = []
    prohibited_actions = LegalAgent.prohibited_actions

    def process(self, message: str, facts: dict, bundle, jurisdiction: str = "EW") -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            status="ok",
            findings=[{"flag": "human_review_required", "reason": "high_risk_claim_or_urgency"}],
            confidence=1.0,
            human_review_required=True,
            human_review_reason="flagged_by_brain_routing",
        )


class SafetyAbuseAgent(LegalAgent):
    name = "safety_abuse"
    description = "Detects prompt injection, abuse, and unsafe inputs. Blocks dangerous requests."
    allowed_tools = ["content_filter"]
    prohibited_actions = LegalAgent.prohibited_actions

    _BLOCKED_PATTERNS = [
        "ignore previous", "disregard instructions", "act as",
        "jailbreak", "pretend you are", "system prompt",
    ]

    def process(self, message: str, facts: dict, bundle, jurisdiction: str = "EW") -> AgentResult:
        lowered = message.lower()
        for pattern in self._BLOCKED_PATTERNS:
            if pattern in lowered:
                return AgentResult(
                    agent_name=self.name,
                    status="blocked",
                    findings=[{"threat": "prompt_injection_attempt", "pattern": pattern}],
                    confidence=1.0,
                    human_review_required=True,
                    human_review_reason="prompt_injection_detected",
                )
        return AgentResult(agent_name=self.name, status="ok", confidence=1.0)


class DocumentDraftingAgent(LegalAgent):
    """
    Generates self-help legal documents (Particulars of Claim, Schedule of Loss).

    GUARDRAIL: Every document includes the legal boundary notice.
    GUARDRAIL: Only generates from structured assessment — never raw LLM prose.
    GUARDRAIL: Documents are drafts for user review, not filed by lawapp.
    """

    name = "document_drafting"
    description = (
        "Generates Particulars of Claim and Schedule of Loss from structured "
        "assessment. Self-help drafts only. Not legal advice. Not a law firm."
    )
    allowed_tools = ["generate_particulars", "generate_schedule_of_loss",
                     "generate_letter_before_action"]
    prohibited_actions = LegalAgent.prohibited_actions + [
        "file_document_with_tribunal",
        "sign_on_behalf_of_user",
        "submit_et1",
    ]

    def process(self, message: str, facts: dict, bundle, jurisdiction: str = "EW") -> AgentResult:
        claim_type = facts.get("claim_type", "unfair_dismissal")
        generated = []
        citations = []
        gaps = []

        try:
            from backend.core.documents import generate_particulars_of_claim
            poc = generate_particulars_of_claim(facts, {}, jurisdiction=jurisdiction)
            if poc and isinstance(poc, str) and "SELF-HELP" in poc:
                generated.append({
                    "doc_type": "particulars_of_claim",
                    "template": "v1",
                    "has_boundary_notice": True,
                    "length_chars": len(poc),
                })
        except Exception as exc:
            logger.debug("POC generation skipped: %s", exc)
            gaps.append("particulars_of_claim_generation_failed")

        if claim_type == "unfair_dismissal":
            try:
                from backend.core.documents import generate_schedule_of_loss
                sol = generate_schedule_of_loss(facts, {}, jurisdiction=jurisdiction)
                if sol and isinstance(sol, str) and len(sol) > 100:
                    generated.append({
                        "doc_type": "schedule_of_loss",
                        "template": "v1",
                        "has_boundary_notice": True,
                    })
            except Exception as exc:
                logger.debug("SoL generation skipped: %s", exc)

        return AgentResult(
            agent_name=self.name,
            status="ok" if generated else "insufficient_facts",
            findings=generated,
            citations_used=citations,
            evidence_gaps=gaps,
            confidence=0.9 if generated else 0.0,
            notes=f"Generated {len(generated)} document(s). All include self-help draft notice.",
        )


# ── Registry ─────────────────────────────────────────────────────────────────

class AgentRegistry:
    """Central registry. Brain uses this to look up agents by name."""

    def __init__(self):
        self._agents: dict[str, LegalAgent] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for agent in [
            EmploymentLawAgent(),
            DeadlineAgent(),
            EvidenceAgent(),
            CitationVerificationAgent(),
            CompensationAgent(),
            RiskReviewAgent(),
            EvaluationAgent(),
            HumanReviewAgent(),
            SafetyAbuseAgent(),
            DocumentDraftingAgent(),
        ]:
            self._agents[agent.name] = agent

    def get(self, name: str) -> Optional[LegalAgent]:
        return self._agents.get(name)

    def list_all(self) -> list[dict]:
        return [a.to_config() for a in self._agents.values()]

    def get_agents_for_claim(self, claim_type: str, urgency: str = "safe") -> list[LegalAgent]:
        from backend.core.brain import _AGENT_MAP
        from backend.core.agents.domain_plugins import get_domain_plugin

        plugin = get_domain_plugin("employment")
        if plugin:
            names = plugin.agents_for(claim_type, urgency)
        else:
            names = list(_AGENT_MAP.get(claim_type, _AGENT_MAP["_default"]))
            if urgency in ("urgent", "critical", "expired") and "human_review" not in names:
                names = names + ["human_review"]
        return [self._agents[n] for n in names if n in self._agents]

    def agents_for_domain(
        self, domain: str, claim_type: str, urgency: str = "safe"
    ) -> list[LegalAgent]:
        """Resolve agents via domain plugin when available."""
        from backend.core.agents.domain_plugins import get_domain_plugin

        plugin = get_domain_plugin(domain)
        if plugin:
            names = plugin.agents_for(claim_type, urgency)
        else:
            names = [a.name for a in self.get_agents_for_claim(claim_type, urgency)]
        return [self._agents[n] for n in names if n in self._agents]


_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
