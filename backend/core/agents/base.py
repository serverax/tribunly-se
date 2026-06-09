"""
Base agent protocol for lawapp legal agents.

Every agent:
  - Has a fixed name, description, and allowed_tools list
  - Has a prohibited_actions list (guardrails)
  - Has a process() method called by the Brain
  - May NOT answer directly — output goes through Brain → Evaluation → Answer
  - MUST return a structured AgentResult, never raw prose
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentResult:
    """Structured output from any agent. Never returned to user directly."""
    agent_name: str
    status: str                      # "ok" | "insufficient_facts" | "blocked" | "error"
    findings: list[dict] = field(default_factory=list)
    citations_used: list[str] = field(default_factory=list)
    evidence_gaps: list[str] = field(default_factory=list)
    human_review_required: bool = False
    human_review_reason: Optional[str] = None
    confidence: float = 0.0          # 0.0 – 1.0
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "status": self.status,
            "findings": self.findings,
            "citations_used": self.citations_used,
            "evidence_gaps": self.evidence_gaps,
            "human_review_required": self.human_review_required,
            "human_review_reason": self.human_review_reason,
            "confidence": self.confidence,
            "notes": self.notes,
        }


class LegalAgent(ABC):
    """Abstract base for all lawapp legal agents."""

    name: str = "base_agent"
    description: str = "Base agent"
    allowed_tools: list[str] = []
    prohibited_actions: list[str] = [
        "file_claim",
        "represent_user",
        "provide_guarantee",
        "litigation_conduct",
        "sign_documents",
    ]

    @abstractmethod
    def process(
        self,
        message: str,
        facts: dict,
        bundle: Any,
        jurisdiction: str = "EW",
    ) -> AgentResult:
        """
        Process a legal request and return structured findings.

        GUARDRAIL: Never return raw legal advice. Return AgentResult only.
        GUARDRAIL: Never fabricate citations.
        GUARDRAIL: If prohibited_action detected, return status="blocked".
        """

    def _check_prohibited(self, text: str) -> Optional[str]:
        lowered = text.lower()
        for act in self.prohibited_actions:
            if act.replace("_", " ") in lowered or act in lowered:
                return act
        return None

    def to_config(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "allowed_tools": self.allowed_tools,
            "prohibited_actions": self.prohibited_actions,
        }
