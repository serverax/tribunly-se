"""
Mother Algorithm swarm agents.

Each agent delegates to real backend functions and returns AgentResult for brain_traces.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.agents.base import AgentResult, LegalAgent

logger = logging.getLogger(__name__)


class IntakeAgent(LegalAgent):
    name = "intake"
    description = "Classifies jurisdiction, claim type, urgency; detects missing facts."
    allowed_tools = ["classify", "validate_facts"]

    def process(self, message: str, facts: dict, bundle: Any, jurisdiction: str = "EW") -> AgentResult:
        from backend.core.classify import classify
        from backend.core.evidence_gap import detect_gaps

        clf = classify(message, facts)
        gaps = detect_gaps(clf.matter_type if clf.in_scope else "unknown", facts) if clf.in_scope else []
        return AgentResult(
            agent_name=self.name,
            status="ok" if clf.in_scope else "out_of_scope",
            findings=[{
                "in_scope": clf.in_scope,
                "matter_type": clf.matter_type,
                "intent": clf.intent,
                "jurisdiction": jurisdiction,
            }],
            evidence_gaps=gaps,
            confidence=1.0 if clf.in_scope else 0.0,
        )


class RetrievalAgent(LegalAgent):
    name = "retrieval"
    description = "Hybrid RAG + rules retrieval from Postgres corpus."
    allowed_tools = ["retrieve", "hybrid_search", "retrieve_rules"]

    def process(self, message: str, facts: dict, bundle: Any, jurisdiction: str = "EW") -> AgentResult:
        if not bundle:
            return AgentResult(
                agent_name=self.name,
                status="insufficient_facts",
                evidence_gaps=["retrieval_bundle_empty"],
                confidence=0.0,
            )
        rules = getattr(bundle, "exact_rules", []) or []
        auths = getattr(bundle, "authorities", []) or []
        return AgentResult(
            agent_name=self.name,
            status="ok" if rules or auths else "insufficient_facts",
            findings=[{"rules": len(rules), "authorities": len(auths)}],
            citations_used=[a.get("cite", "") for a in auths if isinstance(a, dict) and a.get("cite")],
            confidence=min(1.0, (len(rules) + len(auths)) * 0.15),
        )


class GraphAgent(LegalAgent):
    name = "graph"
    description = "Postgres legal_nodes/legal_edges BFS traversal (NOT Neo4j)."
    allowed_tools = ["graph_traverse", "legal_graph"]

    def process(self, message: str, facts: dict, bundle: Any, jurisdiction: str = "EW") -> AgentResult:
        from backend.core.control_plane.graph_controller import GraphController

        claim = facts.get("claim_type") or "unfair_dismissal"
        g = GraphController().get_subgraph(claim, jurisdiction)
        nodes = g.get("nodes") or []
        return AgentResult(
            agent_name=self.name,
            status="ok" if nodes else "empty",
            findings=[{"root": g.get("root_node"), "nodes": len(nodes), "edges": len(g.get("edges") or [])}],
            confidence=min(1.0, len(nodes) * 0.1),
            notes="Postgres graph: legal_nodes/legal_edges",
        )


class ReasoningAgent(LegalAgent):
    name = "reasoning"
    description = "Routes to governed pipeline assess (rules + RAG + local LLM)."
    allowed_tools = ["pipeline_assess", "orchestrator"]

    def process(self, message: str, facts: dict, bundle: Any, jurisdiction: str = "EW") -> AgentResult:
        from backend.core.models import StubReasoningModel
        from backend.core.pipeline import assess

        result = assess(message, facts, model=StubReasoningModel(), jurisdiction=jurisdiction)
        return AgentResult(
            agent_name=self.name,
            status=result.get("status", "unknown"),
            findings=[{"status": result.get("status"), "claim_type": result.get("claim_type")}],
            confidence=float((result.get("assessment") or {}).get("confidence_score", 0) or 0),
            notes="Delegated to pipeline.assess (stub model for agent stage)",
        )


class RiskAgent(LegalAgent):
    name = "risk"
    description = "Deadline urgency, weaknesses, human-review flags."
    allowed_tools = ["risk_score", "deadline_calculate"]

    def process(self, message: str, facts: dict, bundle: Any, jurisdiction: str = "EW") -> AgentResult:
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


class JudgeAgent(LegalAgent):
    name = "judge"
    description = "Governance + citation verification gate (Critic/CitationGuard)."
    allowed_tools = ["govern", "citation_verify", "legal_truth_validator"]

    def process(self, message: str, facts: dict, bundle: Any, jurisdiction: str = "EW") -> AgentResult:
        assessment = facts.get("_assessment_snapshot") or {}
        if not assessment:
            if bundle and hasattr(bundle, "authorities"):
                from backend.core.citation_verifier import verify_bundle_citations

                v = verify_bundle_citations(bundle.authorities)
                return AgentResult(
                    agent_name=self.name,
                    status="ok" if v.get("failed", 1) == 0 else "blocked",
                    findings=[v],
                    confidence=v.get("pass_rate", 0.0),
                )
            return AgentResult(agent_name=self.name, status="deferred", notes="Awaiting assessment snapshot")

        from backend.core.legal_truth_validator import validate_assessment_truth

        v = validate_assessment_truth(assessment)
        return AgentResult(
            agent_name=self.name,
            status="ok" if v.passed else "blocked",
            findings=v.checks,
            confidence=1.0 if v.passed else 0.0,
            human_review_required=not v.passed,
            human_review_reason="legal_truth_failed" if not v.passed else None,
        )


class DocumentAgent(LegalAgent):
    name = "document"
    description = "Self-help document drafts from structured assessment."
    allowed_tools = ["generate_particulars", "generate_schedule_of_loss"]

    def process(self, message: str, facts: dict, bundle: Any, jurisdiction: str = "EW") -> AgentResult:
        claim_type = facts.get("claim_type", "unfair_dismissal")
        generated = []
        gaps = []
        try:
            from backend.core.documents import generate_particulars_of_claim

            poc = generate_particulars_of_claim(facts, {}, jurisdiction=jurisdiction)
            if poc and isinstance(poc, str) and "SELF-HELP" in poc:
                generated.append({"doc_type": "particulars_of_claim", "length_chars": len(poc)})
        except Exception as exc:
            logger.debug("DocumentAgent POC skipped: %s", exc)
            gaps.append("particulars_of_claim_generation_failed")
        if claim_type == "unfair_dismissal":
            try:
                from backend.core.documents import generate_schedule_of_loss

                sol = generate_schedule_of_loss(facts, {}, jurisdiction=jurisdiction)
                if sol and isinstance(sol, str) and len(sol) > 100:
                    generated.append({"doc_type": "schedule_of_loss"})
            except Exception as exc:
                logger.debug("DocumentAgent SoL skipped: %s", exc)
        return AgentResult(
            agent_name=self.name,
            status="ok" if generated else "insufficient_facts",
            findings=generated,
            evidence_gaps=gaps,
            confidence=0.9 if generated else 0.0,
        )


SWARM_AGENTS = [
    IntakeAgent(),
    RetrievalAgent(),
    GraphAgent(),
    ReasoningAgent(),
    RiskAgent(),
    JudgeAgent(),
    DocumentAgent(),
]
