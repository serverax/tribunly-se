"""
Mother controller  -  full control plane pipeline entry point.

Control flow:
  User -> Intake -> Retrieve -> Reason -> Govern -> Memory -> Learn -> Response

Calls REAL brain/orchestrator/retrieve/pipeline logic. No stub success paths.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.core.control_plane.agent_registry import ControlPlaneAgentRegistry
from backend.core.control_plane.governance_engine import GovernanceEngine
from backend.core.control_plane.learning_loop import LearningLoop
from backend.core.control_plane.memory_store import MemoryStore
from backend.core.control_plane.reasoning_router import ReasoningRouter

logger = logging.getLogger(__name__)


@dataclass
class MotherInput:
    query: str
    facts: dict
    jurisdiction: str = "EW"
    user_id: str = ""
    case_id: str = ""
    use_model: bool = True
    memory_consent: bool = False
    trace_id: Optional[str] = None


@dataclass
class MotherOutput:
    result: dict
    stages: list[dict] = field(default_factory=list)
    governance_verdict: str = "FAIL"
    trace_id: str = ""

    def to_dict(self) -> dict:
        out = dict(self.result)
        out["control_plane_stages"] = self.stages
        out["governance_verdict"] = self.governance_verdict
        out.setdefault("trace_id", self.trace_id)
        return out


class MotherController:
    """Mother Algorithm Control Plane v1 orchestrator."""

    def __init__(self) -> None:
        self.router = ReasoningRouter()
        self.governance = GovernanceEngine()
        self.memory = MemoryStore()
        self.learning = LearningLoop()
        self.agents = ControlPlaneAgentRegistry()

    def process(self, inp: MotherInput) -> MotherOutput:
        trace_id = inp.trace_id or str(uuid.uuid4())
        stages: list[dict] = []

        # Intake
        intake_agent = self.agents.get("intake")
        bundle_pre = None
        if intake_agent:
            try:
                from backend.core.classify import classify

                clf = classify(inp.query, inp.facts)
                bundle_pre = self.router.retrieve(
                    inp.query,
                    clf.matter_type if clf.in_scope else "out_of_scope",
                    inp.jurisdiction,
                )
                intake_result = intake_agent.process(inp.query, inp.facts, bundle_pre, inp.jurisdiction)
                stages.append({"stage": "intake", "status": intake_result.status, "agent": "intake"})
            except Exception as exc:
                stages.append({"stage": "intake", "status": "error", "detail": str(exc)})
        else:
            stages.append({"stage": "intake", "status": "skipped", "detail": "intake agent not registered"})

        # Fast deterministic lane (rules-only)
        lane_info = self.router.classify_lane(inp.query, inp.facts)
        stages.append({"stage": "route_lane", "status": "ok", "detail": lane_info})

        from backend.core.path_splitter import FAST_DETERMINISTIC

        if lane_info.get("lane") == FAST_DETERMINISTIC:
            result = self.router.assess_factual(inp.query, inp.facts, inp.jurisdiction)
            result["trace_id"] = trace_id
            result["control_plane"] = {"lane": "FAST_DETERMINISTIC"}
            gov = self.governance.evaluate(result, trace_id=trace_id)
            result.update(gov.to_metadata())
            stages.append({"stage": "govern", "status": gov.verdict})
            learn = self.learning.learn_from_assessment(result, gov.to_metadata(), trace_id=trace_id)
            stages.append({"stage": "learn", "status": "ok", "proposals": len(learn.get("proposals", []))})
            return MotherOutput(result=result, stages=stages, governance_verdict=gov.verdict, trace_id=trace_id)

        # Retrieve + swarm agents
        router_out = self.router.route_and_retrieve(inp.query, inp.facts, inp.jurisdiction)
        bundle = router_out.get("bundle")
        stages.append({
            "stage": "retrieve",
            "status": "ok" if bundle else "empty",
            "rules": router_out.get("rules_count", 0),
            "authorities": router_out.get("authorities_count", 0),
            "graph_nodes": len((router_out.get("graph_context") or {}).get("nodes", [])),
        })

        swarm_results = []
        for agent in self.agents.swarm_for_claim(router_out.get("claim_type", "unfair_dismissal")):
            if agent.name in ("intake", "reasoning"):
                continue
            try:
                ar = agent.process(inp.query, inp.facts, bundle, inp.jurisdiction)
                swarm_results.append(ar.to_dict())
                stages.append({"stage": f"agent_{agent.name}", "status": ar.status})
            except Exception as exc:
                stages.append({"stage": f"agent_{agent.name}", "status": "error", "detail": str(exc)})

        # Reason (real pipeline / brain orchestrator)
        if inp.use_model:
            from backend.core.brain import orchestrator

            result = orchestrator.execute_generative_lane(
                query=inp.query,
                context=inp.facts,
                case_id=inp.case_id,
                user_id=inp.user_id,
                jurisdiction=inp.jurisdiction,
                claim_type=router_out.get("claim_type", "unfair_dismissal"),
            )
        else:
            result = self.router.run_reasoning_pipeline(
                inp.query,
                inp.facts,
                jurisdiction=inp.jurisdiction,
                use_model=False,
            )

        result["trace_id"] = trace_id
        result["swarm_results"] = swarm_results
        stages.append({"stage": "reason", "status": result.get("status", "unknown")})

        # Govern
        gov = self.governance.evaluate(result, trace_id=trace_id)
        result.update(gov.to_metadata())
        stages.append({"stage": "govern", "status": gov.verdict})

        # Memory (consent-gated)
        if inp.memory_consent and inp.user_id:
            mem_id = self.memory.write_agent_memory(
                user_id=inp.user_id,
                case_id=inp.case_id or None,
                memory_key="last_assessment",
                memory_value={"status": result.get("status"), "claim_type": result.get("claim_type")},
                masked_value={"status": result.get("status")},
                consent_given=True,
            )
            stages.append({"stage": "memory", "status": "ok" if mem_id else "skipped"})
        else:
            stages.append({"stage": "memory", "status": "skipped", "detail": "no consent"})

        # Learn (proposals only)
        learn = self.learning.learn_from_assessment(result, gov.to_metadata(), trace_id=trace_id)
        result["learning"] = learn
        stages.append({"stage": "learn", "status": "ok", "proposals": len(learn.get("proposals", []))})

        self._persist_trace(trace_id, stages, gov.verdict, inp)

        return MotherOutput(
            result=result,
            stages=stages,
            governance_verdict=gov.verdict,
            trace_id=trace_id,
        )

    def _persist_trace(
        self,
        trace_id: str,
        stages: list[dict],
        verdict: str,
        inp: MotherInput,
    ) -> None:
        try:
            from ingestion.db import get_connection
            import json

            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE brain_traces
                        SET orchestration_stages = %s::jsonb,
                            compliance_verdict = %s
                        WHERE trace_id = %s
                        """,
                        (json.dumps(stages), verdict, trace_id),
                    )
                    if cur.rowcount == 0:
                        cur.execute(
                            """
                            INSERT INTO brain_traces (trace_id, user_id, case_id, jurisdiction,
                                orchestration_stages, compliance_verdict, status)
                            VALUES (%s, NULLIF(%s, '')::uuid, NULLIF(%s, '')::uuid, %s, %s::jsonb, %s, 'control_plane')
                            ON CONFLICT DO NOTHING
                            """,
                            (
                                trace_id,
                                inp.user_id,
                                inp.case_id,
                                inp.jurisdiction,
                                json.dumps(stages),
                                verdict,
                            ),
                        )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            logger.debug("brain_traces persist skipped: %s", exc)
