"""
Governed orchestrator — classify → route → delegate → merge.

Single entry for domain-aware agent routing. Used by Brain step 11b and
exposed as brain.Orchestrator for API callers.

GUARDRAIL: Agents return AgentResult only; merge output is trace metadata,
not user-facing legal advice.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.core.agents.base import AgentResult
from backend.core.agents.registry import get_registry
from backend.core.agents.domain_plugins import get_domain_plugin

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationResult:
    """Merged output from a delegate pass."""

    domain: str
    claim_type: str
    agents_run: list[str] = field(default_factory=list)
    agent_results: list[dict] = field(default_factory=list)
    tools_available: list[str] = field(default_factory=list)
    human_review_required: bool = False
    evidence_gaps: list[str] = field(default_factory=list)
    stages: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "claim_type": self.claim_type,
            "agents_run": self.agents_run,
            "agent_results": self.agent_results,
            "tools_available": self.tools_available,
            "human_review_required": self.human_review_required,
            "evidence_gaps": self.evidence_gaps,
            "stages": self.stages,
        }


class Orchestrator:
    """
    Institutional governed pipeline orchestrator.

    Stages:
      1. classify — jurisdiction, legal area, claim type (via classify module)
      2. route    — select agents + tools from domain plugin
      3. delegate — run each agent.process()
      4. merge    — combine AgentResults into OrchestrationResult
    """

    def classify(self, message: str, facts: dict, jurisdiction: str = "EW") -> dict:
        from backend.core.classify import classify as _classify

        clf = _classify(message, facts)
        j = (facts.get("jurisdiction") or jurisdiction or "EW").upper()
        if j not in ("EW", "SC", "NI"):
            j = "EW"
        claim_type = clf.matter_type if clf.in_scope else "out_of_scope"
        legal_area = "employment_law" if clf.in_scope else "out_of_scope"
        return {
            "jurisdiction": j,
            "legal_area": legal_area,
            "claim_type": claim_type,
            "in_scope": clf.in_scope,
            "intent": clf.intent,
            "classification": clf,
        }

    def route(
        self,
        claim_type: str,
        urgency: str = "safe",
        domain: str = "employment",
    ) -> dict:
        from backend.domains.registry import require_domain, retrieval_domain_for

        require_domain(domain)
        retrieval_tag = retrieval_domain_for(domain)
        plugin = get_domain_plugin(domain) or get_domain_plugin(retrieval_tag)
        if plugin:
            agents = plugin.agents_for(claim_type, urgency)
            tools = plugin.tools_for(claim_type)
        else:
            registry = get_registry()
            agents = [a.name for a in registry.get_agents_for_claim(claim_type, urgency)]
            tools = []
        return {
            "domain": domain,
            "retrieval_domain": retrieval_tag,
            "agents": agents,
            "tools": tools,
        }

    def delegate(
        self,
        agent_names: list[str],
        message: str,
        facts: dict,
        bundle: Any,
        jurisdiction: str = "EW",
    ) -> list[AgentResult]:
        registry = get_registry()
        results: list[AgentResult] = []
        for name in agent_names:
            agent = registry.get(name)
            if agent is None:
                logger.warning("Unknown agent %r — skipped", name)
                continue
            try:
                results.append(agent.process(message, facts, bundle, jurisdiction))
            except Exception as exc:
                logger.warning("Agent %s failed: %s", name, exc)
                results.append(
                    AgentResult(
                        agent_name=name,
                        status="error",
                        notes=str(exc),
                        confidence=0.0,
                    )
                )
        return results

    def merge(self, agent_results: list[AgentResult], route: dict) -> OrchestrationResult:
        gaps: list[str] = []
        human = False
        serialized: list[dict] = []
        for ar in agent_results:
            serialized.append(ar.to_dict())
            gaps.extend(ar.evidence_gaps)
            if ar.human_review_required:
                human = True
        # De-dupe gaps preserving order
        seen: set[str] = set()
        unique_gaps = [g for g in gaps if g not in seen and not seen.add(g)]
        return OrchestrationResult(
            domain=route.get("domain", "employment"),
            claim_type=route.get("claim_type", ""),
            agents_run=[ar.agent_name for ar in agent_results],
            agent_results=serialized,
            tools_available=list(route.get("tools") or []),
            human_review_required=human,
            evidence_gaps=unique_gaps,
        )

    def run_stages(
        self,
        message: str,
        facts: dict,
        bundle: Any,
        *,
        jurisdiction: str = "EW",
        claim_type: Optional[str] = None,
        urgency: str = "safe",
        domain: str = "employment",
        agent_names: Optional[list[str]] = None,
    ) -> OrchestrationResult:
        """Full classify → route → delegate → merge with stage audit trail."""
        stages: list[dict] = []

        classification = self.classify(message, facts, jurisdiction)
        stages.append({"stage": "classify", "status": "ok", "detail": {
            "claim_type": classification["claim_type"],
            "legal_area": classification["legal_area"],
            "in_scope": classification["in_scope"],
        }})

        effective_claim = claim_type or classification["claim_type"]
        route = self.route(effective_claim, urgency, domain)
        route["claim_type"] = effective_claim
        stages.append({"stage": "route", "status": "ok", "detail": {
            "agents": route["agents"],
            "tools": route["tools"],
            "retrieval_domain": route["retrieval_domain"],
        }})

        names = agent_names if agent_names is not None else route["agents"]
        agent_results = self.delegate(names, message, facts, bundle, classification["jurisdiction"])
        stages.append({"stage": "delegate", "status": "ok", "detail": {
            "agents_run": [r.agent_name for r in agent_results],
            "statuses": {r.agent_name: r.status for r in agent_results},
        }})

        merged = self.merge(agent_results, route)
        merged.stages = stages
        stages.append({"stage": "merge", "status": "ok", "detail": {
            "human_review_required": merged.human_review_required,
            "evidence_gaps": merged.evidence_gaps,
        }})
        return merged

    def execute_generative_lane(
        self,
        query: str,
        context: dict,
        case_id: str,
        user_id: str,
        jurisdiction: str = "EW",
        claim_type: str = "unfair_dismissal",
    ) -> dict:
        """Backward-compatible entry — delegates to brain.execute_generative_lane."""
        from backend.core.brain import execute_generative_lane as _lane

        return _lane(
            query=query,
            context=context,
            case_id=case_id,
            user_id=user_id,
            jurisdiction=jurisdiction,
            claim_type=claim_type,
        )

    def available_tools(self, domain: str = "employment", claim_type: str = "unfair_dismissal") -> list[str]:
        route = self.route(claim_type, domain=domain)
        return list(route.get("tools") or [])


# Module singleton used by brain.py
orchestrator = Orchestrator()
