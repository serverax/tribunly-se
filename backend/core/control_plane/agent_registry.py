"""
Control plane agent registry  -  Mother swarm agent lookup.
"""

from __future__ import annotations

from typing import Optional

from backend.core.agents.base import LegalAgent
from backend.core.agents.registry import get_registry


SWARM_AGENT_NAMES = (
    "intake",
    "retrieval",
    "graph",
    "reasoning",
    "risk",
    "judge",
    "document",
)


class ControlPlaneAgentRegistry:
    """Swarm agents for Mother control plane orchestration."""

    def __init__(self) -> None:
        self._registry = get_registry()

    def get(self, name: str) -> Optional[LegalAgent]:
        return self._registry.get(name)

    def swarm_for_claim(self, claim_type: str, urgency: str = "safe") -> list[LegalAgent]:
        agents = []
        for name in SWARM_AGENT_NAMES:
            a = self._registry.get(name)
            if a:
                agents.append(a)
        if not agents:
            return self._registry.get_agents_for_claim(claim_type, urgency)
        return agents

    def list_swarm(self) -> list[dict]:
        return [a.to_config() for n in SWARM_AGENT_NAMES if (a := self._registry.get(n))]
