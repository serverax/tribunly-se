"""
Learning loop  -  prediction vs outcome, offline-safe proposal creation.

NEVER writes rules or law tables directly.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.core.knowledge_proposer import propose_ingestion

logger = logging.getLogger(__name__)


class LearningLoop:
    """Record gaps and enqueue ingestion proposals only."""

    def record_prediction(
        self,
        assessment: dict,
        *,
        trace_id: Optional[str] = None,
    ) -> dict:
        return {
            "predicted_status": assessment.get("status"),
            "predicted_claim_type": assessment.get("claim_type"),
            "grounding_score": (assessment.get("assessment") or {}).get("grounding_score")
            if isinstance(assessment.get("assessment"), dict)
            else assessment.get("grounding_score"),
            "trace_id": trace_id or assessment.get("trace_id"),
        }

    def record_outcome_gap(
        self,
        *,
        source_type: str,
        authority_ref: str,
        rationale: str,
        gap_type: str = "retrieval_miss",
        trace_id: Optional[str] = None,
    ) -> dict:
        return propose_ingestion(
            source_type=source_type,
            authority_ref=authority_ref,
            rationale=rationale,
            gap_type=gap_type,
            trace_id=trace_id,
        )

    def learn_from_assessment(
        self,
        assessment: dict,
        governance: dict,
        *,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Offline-safe: proposals on gaps, never direct law writes."""
        prediction = self.record_prediction(assessment, trace_id=trace_id)
        proposals: list[dict] = []

        if assessment.get("status") == "insufficient_grounding":
            claim = assessment.get("claim_type", "unknown")
            proposals.append(
                self.record_outcome_gap(
                    source_type="rules",
                    authority_ref=f"{claim}.missing_rule",
                    rationale="Assessment failed grounding; propose rules ingestion review",
                    gap_type="insufficient_grounding",
                    trace_id=trace_id,
                )
            )

        if governance.get("governance_verdict") == "ESCALATE":
            cites = assessment.get("citations") or []
            for c in cites[:3]:
                if isinstance(c, dict) and c.get("cite"):
                    proposals.append(
                        self.record_outcome_gap(
                            source_type=c.get("type", "corpus"),
                            authority_ref=c.get("cite", ""),
                            rationale="Governance escalation: citation integrity gap",
                            gap_type="citation_gap",
                            trace_id=trace_id,
                        )
                    )

        return {"prediction": prediction, "proposals": proposals}
