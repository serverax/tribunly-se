"""
backend.domains.registry  -  the single source of truth for legal domains.

Domain packs under domains/<code>/ are loaded by loader.py and synced into
domain_registry at import time. Runtime register_domain() remains for tests.

Design properties (CLAUDE.md §4 modular, §9/§17 fail-closed):

  * A new domain is added by dropping a pack + domain_config.json  -  NO core edit.
  * Unknown domain            -> UnsupportedDomainError   (fail closed)
  * Registered-but-disabled   -> DomainDisabledError      (fail closed)
  * Unknown matter type       -> UnsupportedMatterError   (fail closed)
  * Supported scope = union of matter_types over ENABLED domains only.

This module imports NOTHING from any concrete domain implementation module.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from backend.domains.constants import DOMAIN_DEFAULT, active_domain_from_env
from backend.domains.loader import get_domain_pack, list_domain_packs, load_domain_pack
from backend.domains.pack_contract import DomainPack
from backend.domains.shared.errors import (
    DomainDisabledError,
    UnsupportedDomainError,
    UnsupportedMatterError,
)
from backend.domains.shared.templates import load_domain_templates, template_for
from backend.domains.shared.types import DomainSpec

logger = logging.getLogger(__name__)

domain_registry: Dict[str, DomainSpec] = {}


def _pack_to_spec(pack: DomainPack) -> DomainSpec:
    matter_types = list(pack.enabled_modules) if pack.enabled else []
    return {
        "name": pack.module_code,
        "enabled": bool(pack.enabled and pack.is_operational),
        "matter_types": matter_types,
        "jurisdiction": list(pack.jurisdiction),
        "rules_pack": pack.rules_namespace,
        "retrieval_domain": pack.retrieval_domain or pack.module_code,
        "templates_module": pack.templates_module,
        "label": pack.title,
    }


def sync_registry_from_packs(*, reload: bool = False) -> None:
    """Reload all packs from disk into domain_registry."""
    domain_registry.clear()
    for pack in list_domain_packs(reload=reload):
        domain_registry[pack.module_code] = _pack_to_spec(pack)
    if DOMAIN_DEFAULT not in domain_registry:
        logger.warning("Default domain %r missing from packs", DOMAIN_DEFAULT)


# Bootstrap on import
sync_registry_from_packs()


# ── Active domain (env / workspace) ───────────────────────────────────────────

def get_active_domain() -> str:
    """Return currently active domain code (LAWAPP_DOMAIN or default)."""
    code = active_domain_from_env()
    if code in domain_registry:
        return code
    return DOMAIN_DEFAULT


def list_domains() -> List[dict]:
    """All packs with API-facing metadata and status."""
    return [pack.to_api_dict() for pack in list_domain_packs()]


def switch_domain(code: str) -> str:
    """Validate pack exists; returns code (env must be set externally for persistence)."""
    pack = get_domain_pack(code)
    if pack is None:
        raise UnsupportedDomainError(code)
    return code


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
    spec = get_domain(domain)
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
    """Return the enabled domain that owns ``matter_type``, or None."""
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


# ── Runtime extensibility (tests + dynamic registration) ─────────────────────

def register_domain(spec: DomainSpec, *, overwrite: bool = False) -> None:
    """Register a new domain at runtime from a DomainSpec."""
    name = spec.get("name")
    if not name:
        raise ValueError("DomainSpec.name is required to register a domain.")
    if name in domain_registry and not overwrite:
        raise ValueError(
            f"Domain {name!r} already registered (pass overwrite=True to replace)."
        )
    spec.setdefault("enabled", False)
    spec.setdefault("matter_types", [])
    spec.setdefault("jurisdiction", [])
    domain_registry[name] = spec


def unregister_domain(name: str) -> None:
    """Remove a domain. Primarily for test isolation."""
    domain_registry.pop(name, None)


__all__ = [
    "DOMAIN_DEFAULT",
    "domain_registry",
    "DomainSpec",
    "UnsupportedDomainError",
    "DomainDisabledError",
    "UnsupportedMatterError",
    "sync_registry_from_packs",
    "get_active_domain",
    "list_domains",
    "switch_domain",
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
    "load_domain_pack",
    "get_domain_pack",
]
