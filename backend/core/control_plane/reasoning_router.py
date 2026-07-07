"""
Reasoning router  -  selects RAG, graph, rules, or LLM lane.

Routes to real retrieve/orchestrator logic; never returns fake retrieval.
Domain-specific retrieval scoping is delegated to domain packs via domain_code.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from backend.domains.constants import DOMAIN_DEFAULT
from backend.domains.context import resolve_request_domain
from backend.domains.registry import jurisdiction_supported_for_domain

logger = logging.getLogger(__name__)


class ReasoningRouter:
    """Route a classified matter to the correct reasoning backends."""

    def assess_factual(
        self,
        query: str,
        facts: dict,
        jurisdiction: str = "EW",
        *,
        domain: Optional[str] = None,
    ) -> dict:
        """FAST_DETERMINISTIC lane: rules-table only, fail-closed."""
        from backend.core.classify import classify
        from backend.core.path_splitter import route as split_route
        from backend.core.retrieve import retrieve_rules

        domain_code = resolve_request_domain(domain_code=domain, facts=facts) or DOMAIN_DEFAULT
        decision = split_route(query, facts)
        base = {
            "intent": decision.intent,
            "lane": decision.lane,
            "invokes_llm": False,
            "result_type": "final_governed_assessment",
            "jurisdiction": jurisdiction,
            "domain_code": domain_code,
        }
        if not jurisdiction_supported_for_domain(domain_code, jurisdiction):
            return {
                **base,
                "status": "not_supported",
                "message": (
                    f"{jurisdiction} is not verified for domain {domain_code!r}  -  fail closed."
                ),
            }
        c = classify(query, facts or {})
        if not getattr(c, "in_scope", True):
            return {**base, "status": "not_supported", "message": "Out of scope for this system  -  no guess."}
        claim = getattr(c, "matter_type", None) or "unfair_dismissal"
        try:
            rules = retrieve_rules(claim, jurisdiction, date.today(), domain=domain_code)
        except Exception as exc:
            logger.warning("Factual rules lookup failed closed: %s", exc)
            return {
                **base,
                "status": "not_supported",
                "claim_type": claim,
                "citations": [],
                "reason": "rules lookup unavailable  -  fail closed",
            }
        if not rules:
            return {
                **base,
                "status": "not_supported",
                "claim_type": claim,
                "citations": [],
                "reason": "no verified rules for this jurisdiction  -  fail closed",
            }
        citations = [
            {
                "cite": (r.get("authority") or r.get("authority_ref") or r.get("rule_key")),
                "rule_key": r.get("rule_key"),
                "source": "rules_table",
                "url": r.get("source_url"),
            }
            for r in rules
        ]
        return {
            **base,
            "status": "ok",
            "claim_type": claim,
            "source": "rules_table",
            "rules": rules,
            "citations": citations,
        }

    def classify_lane(self, query: str, facts: dict) -> dict:
        from backend.core.path_splitter import route as split_route

        decision = split_route(query, facts)
        return {
            "lane": decision.lane,
            "intent": decision.intent,
            "reason": getattr(decision, "reason", ""),
        }

    def retrieve(
        self,
        query: str,
        claim_type: str,
        jurisdiction: str,
        ref_date: Optional[date] = None,
        *,
        domain: Optional[str] = None,
    ) -> Any:
        from backend.core.retrieve import retrieve

        ref = ref_date or date.today()
        domain_code = domain or DOMAIN_DEFAULT
        return retrieve(query, claim_type, jurisdiction, ref, domain=domain_code)

    def retrieve_rules(
        self,
        claim_type: str,
        jurisdiction: str,
        ref_date: Optional[date] = None,
        *,
        domain: Optional[str] = None,
    ) -> list[dict]:
        from backend.core.retrieve import retrieve_rules

        domain_code = domain or DOMAIN_DEFAULT
        return retrieve_rules(claim_type, jurisdiction, ref_date or date.today(), domain=domain_code)

    def route_and_retrieve(
        self,
        query: str,
        facts: dict,
        jurisdiction: str = "EW",
        *,
        domain: Optional[str] = None,
    ) -> dict:
        from backend.core.classify import classify

        domain_code = resolve_request_domain(domain_code=domain, facts=facts) or DOMAIN_DEFAULT
        lane = self.classify_lane(query, facts)
        clf = classify(query, facts)
        claim_type = clf.matter_type if clf.in_scope else "out_of_scope"

        result: dict[str, Any] = {
            "lane": lane,
            "domain_code": domain_code,
            "classification": {
                "in_scope": clf.in_scope,
                "matter_type": clf.matter_type,
                "intent": clf.intent,
            },
            "claim_type": claim_type,
        }

        if not clf.in_scope:
            result["bundle"] = None
            return result

        ref_str = (
            facts.get("edt")
            or facts.get("dismissal_date")
            or facts.get("wages_due_date")
            or facts.get("effective_date_of_termination")
        )
        try:
            ref_date = date.fromisoformat(str(ref_str)) if ref_str else date.today()
        except ValueError:
            ref_date = date.today()

        bundle = self.retrieve(
            query, claim_type, jurisdiction, ref_date, domain=domain_code,
        )
        graph_ctx = None
        try:
            from backend.core.control_plane.graph_controller import GraphController

            graph_ctx = GraphController().enrich_bundle_context(claim_type, jurisdiction)
        except Exception as exc:
            logger.debug("Graph context skipped: %s", exc)

        result["bundle"] = bundle
        result["graph_context"] = graph_ctx
        result["rules_count"] = len(getattr(bundle, "exact_rules", []) or [])
        result["authorities_count"] = len(getattr(bundle, "authorities", []) or [])
        return result

    def run_reasoning_pipeline(
        self,
        query: str,
        facts: dict,
        *,
        jurisdiction: str = "EW",
        use_model: bool = True,
        model=None,
        domain: Optional[str] = None,
    ) -> dict:
        """Full reasoning via pipeline.assess (real governed path)."""
        from backend.core.models import StubReasoningModel, select_model
        from backend.core.pipeline import assess as pipeline_assess
        from ingestion.config import settings

        domain_code = resolve_request_domain(domain_code=domain, facts=facts) or DOMAIN_DEFAULT
        router_out = self.route_and_retrieve(
            query, facts, jurisdiction, domain=domain_code,
        )
        if not router_out["classification"]["in_scope"]:
            from backend.core.govern import build_not_supported_response

            return {**build_not_supported_response(router_out["claim_type"]), **router_out}

        _model = model
        if not use_model:
            _model = StubReasoningModel()
        elif _model is None:
            _model = select_model(settings)

        assessment = pipeline_assess(
            query,
            facts,
            model=_model,
            jurisdiction=jurisdiction,
            graph_context=router_out.get("graph_context"),
            domain=domain_code,
        )
        assessment["domain_code"] = domain_code
        assessment["control_plane"] = {
            "router": {
                "lane": router_out["lane"],
                "rules_count": router_out.get("rules_count"),
                "authorities_count": router_out.get("authorities_count"),
                "graph_nodes": len((router_out.get("graph_context") or {}).get("nodes", [])),
            }
        }
        return assessment
