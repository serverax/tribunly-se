"""
Domain plugins  -  legal-area modules for agent orchestration.

Each plugin binds a retrieval domain tag (e.g. employment_uk) to:
  - supported claim types
  - default agent roster
  - tool names exposed to the orchestrator

Plugins do NOT replace backend.domains.registry (matter/domain enablement).
They extend agent routing for a registered, enabled domain.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DOMAINS_ROOT = Path(__file__).resolve().parents[3] / "domains"


@dataclass
class DomainPluginSpec:
    """Declarative config loaded from domains/<pack>/domain_config.json."""

    domain_id: str
    title: str
    retrieval_domain: str
    active_claim_types: list[str] = field(default_factory=list)
    jurisdictions: list[str] = field(default_factory=list)
    default_agents: list[str] = field(default_factory=list)
    default_tools: list[str] = field(default_factory=list)
    config_path: Optional[str] = None


class DomainPlugin(ABC):
    """Plugin contract for a legal domain pack."""

    spec: DomainPluginSpec

    @abstractmethod
    def claim_types(self) -> list[str]:
        """Claim types this plugin handles."""

    @abstractmethod
    def agents_for(self, claim_type: str, urgency: str = "safe") -> list[str]:
        """Agent names to activate for a claim + urgency."""

    @abstractmethod
    def tools_for(self, claim_type: str) -> list[str]:
        """Tool names available to agents for this claim."""


class EmploymentUkPlugin(DomainPlugin):
    """First production plugin  -  maps employment domain → employment_uk pack."""

    _DEFAULT_AGENTS = [
        "employment_law",
        "deadline",
        "evidence",
        "citation_verification",
        "evaluation",
    ]
    _URGENCY_EXTRA = ["human_review"]
    _DEFAULT_TOOLS = [
        "deadline_calculate",
        "hybrid_search",
        "citation_verify",
        "document_extract",
        "companies_house_lookup",
    ]

    def __init__(self) -> None:
        cfg_path = _DOMAINS_ROOT / "employment_uk" / "domain_config.json"
        spec = DomainPluginSpec(
            domain_id="employment",
            title="UK Employment Law",
            retrieval_domain="employment_uk",
            config_path=str(cfg_path) if cfg_path.exists() else None,
        )
        if cfg_path.exists():
            try:
                raw = json.loads(cfg_path.read_text(encoding="utf-8"))
                spec.title = raw.get("title", spec.title)
                spec.retrieval_domain = raw.get("domain", spec.retrieval_domain)
                spec.active_claim_types = list(raw.get("active_claim_types") or [])
                spec.jurisdictions = list(raw.get("jurisdictions") or [])
            except Exception as exc:
                logger.warning("employment_uk domain_config load failed: %s", exc)
        spec.default_agents = list(self._DEFAULT_AGENTS)
        spec.default_tools = list(self._DEFAULT_TOOLS)
        self.spec = spec

    def claim_types(self) -> list[str]:
        if self.spec.active_claim_types:
            return list(self.spec.active_claim_types)
        return ["unfair_dismissal", "unpaid_wages"]

    def agents_for(self, claim_type: str, urgency: str = "safe") -> list[str]:
        from backend.core.brain import _AGENT_MAP

        names = list(_AGENT_MAP.get(claim_type, _AGENT_MAP["_default"]))
        if urgency in ("urgent", "critical", "expired") and "human_review" not in names:
            names = names + self._URGENCY_EXTRA
        return names

    def tools_for(self, claim_type: str) -> list[str]:
        return list(self.spec.default_tools)


_PLUGINS: dict[str, DomainPlugin] = {}


def _bootstrap_plugins() -> None:
    global _PLUGINS
    if _PLUGINS:
        return
    emp = EmploymentUkPlugin()
    _PLUGINS["employment"] = emp
    _PLUGINS["employment_uk"] = emp


def get_domain_plugin(domain_or_retrieval_tag: str) -> Optional[DomainPlugin]:
    """Resolve plugin by domain name or retrieval tag (e.g. employment_uk)."""
    _bootstrap_plugins()
    key = (domain_or_retrieval_tag or "").strip().lower()
    return _PLUGINS.get(key)


def list_domain_plugins() -> list[dict]:
    _bootstrap_plugins()
    return [
        {
            "domain_id": p.spec.domain_id,
            "retrieval_domain": p.spec.retrieval_domain,
            "title": p.spec.title,
            "claim_types": p.claim_types(),
            "default_agents": p.spec.default_agents,
            "default_tools": p.spec.default_tools,
        }
        for p in _PLUGINS.values()
    ]
