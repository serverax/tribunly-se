"""
backend.domains.registry  -  the single source of truth for legal domains.

Everything that needs to know "is this domain/matter supported, and by whom"
must ask the registry. Nothing else may hardcode the list of domains or the
mapping of matter types to domains.

Design properties (CLAUDE.md §4 modular, §9/§17 fail-closed):

  * A new domain is added by registering a DomainSpec  -  NO edit to shared core.
  * Unknown domain            -> UnsupportedDomainError   (fail closed)
  * Registered-but-disabled   -> DomainDisabledError      (fail closed)
  * Unknown matter type       -> UnsupportedMatterError   (fail closed)
  * Supported scope = union of matter_types over ENABLED domains only.

This module imports NOTHING from any concrete domain (employment etc.). It only
references domains by their declarative DomainSpec, so the dependency arrow
points domain -> registry, never registry -> domain.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from backend.domains.shared.errors import (
    UnsupportedDomainError,
    DomainDisabledError,
    UnsupportedMatterError,
)
from backend.domains.shared.types import DomainSpec
from backend.domains.shared.templates import load_domain_templates, template_for
from backend.domains.employment.modules import production_module_keys

# ──────────────────────────────────────────────────────────────────────────────
# The registry.
#
# employment is the only production-ready domain today. immigration & housing are
# scaffolded placeholders, disabled until they have real rules, corpus, templates
# and tests. matter_types for employment reflect the production subset of the
# 24-module UK employment catalogue in backend.domains.employment.modules.
# CLAUDE.md §15: report reality, not marketing.
# ──────────────────────────────────────────────────────────────────────────────
domain_registry: Dict[str, DomainSpec] = {
    "employment": {
        "name": "employment",
        "enabled": True,
        "matter_types": production_module_keys(),
        "jurisdiction": ["EW", "S"],
        "rules_pack": "employment_rules",
        "retrieval_domain": "employment_uk",
        "templates_module": "backend.domains.employment.templates",
        "label": "Employment (UK)",
    },
    "immigration": {
        "name": "immigration",
        "enabled": False,
        "matter_types": [],
        "jurisdiction": [],
        "rules_pack": None,
        "retrieval_domain": None,
        "templates_module": None,
        "label": "Immigration (placeholder  -  not enabled)",
    },
    "housing": {
        "name": "housing",
        "enabled": False,
        "matter_types": [],
        "jurisdiction": [],
        "rules_pack": None,
        "retrieval_domain": None,
        "templates_module": None,
        "label": "Housing (placeholder  -  not enabled)",
    },
}


# ── Domain lookups ────────────────────────────────────────────────────────────

def get_domain(domain: str) -> DomainSpec:
    """Return the DomainSpec for ``domain`` or raise UnsupportedDomainError."""
    spec = domain_registry.get(domain)
    if spec is None:
        raise UnsupportedDomainError(domain)
    return spec


def is_domain_registered(domain: str) -> bool:
    return domain in domain_registry


def is_domain_enabled(domain: str) -> bool:
    """True only if the domain is registered AND enabled. Never raises."""
    spec = domain_registry.get(domain)
    return bool(spec and spec.get("enabled"))


def enabled_domains() -> List[str]:
    return [name for name, spec in domain_registry.items() if spec.get("enabled")]


def require_domain(domain: str) -> DomainSpec:
    """Return the spec only if the domain is enabled; else fail closed."""
    spec = get_domain(domain)               # UnsupportedDomainError if unknown
    if not spec.get("enabled"):
        raise DomainDisabledError(domain)
    return spec


# ── Matter-type resolution ────────────────────────────────────────────────────

def supported_matter_types() -> List[str]:
    """Union of matter_types across ENABLED domains (the platform's real scope)."""
    out: List[str] = []
    for name in enabled_domains():
        for mt in domain_registry[name].get("matter_types", []):
            if mt not in out:
                out.append(mt)
    return out


def is_matter_supported(matter_type: str) -> bool:
    """True if some ENABLED domain owns ``matter_type``. Never raises."""
    return matter_type in supported_matter_types()


def resolve_domain_for_matter(matter_type: str) -> Optional[str]:
    """Return the enabled domain that owns ``matter_type``, or None.

    Disabled domains are intentionally invisible here  -  fail closed.
    """
    for name in enabled_domains():
        if matter_type in domain_registry[name].get("matter_types", []):
            return name
    return None


def require_supported_matter(matter_type: str) -> str:
    """Return the owning enabled domain or raise UnsupportedMatterError."""
    domain = resolve_domain_for_matter(matter_type)
    if domain is None:
        raise UnsupportedMatterError(matter_type)
    return domain


# ── Jurisdiction ──────────────────────────────────────────────────────────────

def jurisdiction_supported_for_domain(domain: str, jurisdiction: str) -> bool:
    """True if ``domain`` is enabled and serves ``jurisdiction``."""
    if not is_domain_enabled(domain):
        return False
    return jurisdiction in domain_registry[domain].get("jurisdiction", [])


# ── Retrieval scoping ─────────────────────────────────────────────────────────

def retrieval_domain_for(domain: str) -> str:
    """Return the retrieval/audit domain tag for an enabled ``domain``."""
    spec = require_domain(domain)
    return spec.get("retrieval_domain") or domain


# ── Runtime extensibility (proves: new domain, no core rewrite) ───────────────

def register_domain(spec: DomainSpec, *, overwrite: bool = False) -> None:
    """Register a new domain at runtime from a DomainSpec.

    This is the extensibility seam: a future immigration/housing domain  -  or a
    test domain  -  becomes supported purely by registering a spec here, with no
    change to shared core, classify, retrieve, or this module's logic.
    """
    name = spec.get("name")
    if not name:
        raise ValueError("DomainSpec.name is required to register a domain.")
    if name in domain_registry and not overwrite:
        raise ValueError(
            f"Domain {name!r} already registered (pass overwrite=True to replace)."
        )
    # Normalise required collection fields so downstream code never sees None.
    spec.setdefault("enabled", False)
    spec.setdefault("matter_types", [])
    spec.setdefault("jurisdiction", [])
    domain_registry[name] = spec


def unregister_domain(name: str) -> None:
    """Remove a domain. Primarily for test isolation."""
    domain_registry.pop(name, None)


__all__ = [
    "domain_registry",
    "DomainSpec",
    "UnsupportedDomainError",
    "DomainDisabledError",
    "UnsupportedMatterError",
    "get_domain",
    "is_domain_registered",
    "is_domain_enabled",
    "enabled_domains",
    "require_domain",
    "supported_matter_types",
    "is_matter_supported",
    "resolve_domain_for_matter",
    "require_supported_matter",
    "jurisdiction_supported_for_domain",
    "retrieval_domain_for",
    "register_domain",
    "unregister_domain",
    "load_domain_templates",
    "template_for",
]
