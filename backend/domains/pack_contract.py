"""
Domain pack contract: every law pack under domains/ must satisfy this interface.

Core orchestration imports ONLY this module and loader.py, never pack-specific logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class PackStatus(str, Enum):
    PRODUCTION = "production"
    PARTIAL = "partial"
    STUB = "stub"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class DomainPack:
    """Loaded domain pack metadata (declarative, no legal reasoning)."""

    module_code: str
    title: str
    jurisdiction: list[str]
    country_code: str = "GB"
    enabled: bool = False
    status: PackStatus = PackStatus.UNAVAILABLE
    rules_namespace: Optional[str] = None
    retrieval_domain: Optional[str] = None
    enabled_modules: list[str] = field(default_factory=list)
    ingestion_sources_path: Optional[str] = None
    template_paths: list[str] = field(default_factory=list)
    prompt_overrides_path: Optional[str] = None
    validation_rules_path: Optional[str] = None
    pack_root: Optional[Path] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_operational(self) -> bool:
        """True when the pack may serve live assessments."""
        return self.enabled and self.status in (PackStatus.PRODUCTION, PackStatus.PARTIAL)

    @property
    def templates_module(self) -> Optional[str]:
        """Import path for backend template registry when pack is employment."""
        if self.module_code == "employment":
            return "backend.domains.employment.templates"
        return None

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "code": self.module_code,
            "title": self.title,
            "country_code": self.country_code,
            "jurisdiction": list(self.jurisdiction),
            "enabled": self.enabled,
            "status": self.status.value,
            "rules_namespace": self.rules_namespace,
            "retrieval_domain": self.retrieval_domain,
            "enabled_modules": list(self.enabled_modules),
            "ingestion_sources": self.ingestion_sources_path,
            "template_paths": list(self.template_paths),
            "prompt_overrides_path": self.prompt_overrides_path,
            "validation_rules_path": self.validation_rules_path,
            "operational": self.is_operational,
        }


def validate_pack_config(raw: dict[str, Any], pack_code: str) -> list[str]:
    """Return validation errors; empty list means structurally valid."""
    errors: list[str] = []
    required = ("module_code", "title", "jurisdiction", "status")
    for key in required:
        if not raw.get(key):
            errors.append(f"{pack_code}: missing required field {key!r}")
    code = raw.get("module_code")
    if code and code != pack_code:
        errors.append(f"{pack_code}: module_code {code!r} must match directory name")
    status = raw.get("status")
    if status and status not in {s.value for s in PackStatus}:
        errors.append(f"{pack_code}: invalid status {status!r}")
    return errors
