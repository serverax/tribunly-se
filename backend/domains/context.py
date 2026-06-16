"""Resolve active domain from request, facts, or environment (generic, no legal logic)."""

from __future__ import annotations

from typing import Optional

from backend.domains.constants import DOMAIN_DEFAULT, active_domain_from_env
from backend.domains.loader import get_domain_pack
from backend.domains.shared.errors import DomainDisabledError, UnsupportedDomainError


def resolve_request_domain(
    *,
    domain_code: Optional[str] = None,
    header_domain: Optional[str] = None,
    facts: Optional[dict] = None,
) -> str:
    """
    Priority: explicit body/param > X-Lawapp-Domain header > facts.domain_code >
    LAWAPP_DOMAIN env > DOMAIN_DEFAULT.
    """
    candidates = [
        domain_code,
        header_domain,
        (facts or {}).get("domain_code"),
        active_domain_from_env(),
        DOMAIN_DEFAULT,
    ]
    for raw in candidates:
        if raw and str(raw).strip():
            return str(raw).strip().lower()
    return DOMAIN_DEFAULT


def require_operational_domain(domain_code: str):
    """Fail closed if pack missing, disabled, or stub/unavailable."""
    pack = get_domain_pack(domain_code)
    if pack is None:
        raise UnsupportedDomainError(domain_code)
    if not pack.is_operational:
        raise DomainDisabledError(domain_code)
    return pack


def domain_unavailable_response(domain_code: str, exc: Exception) -> dict:
    """Honest API payload for stub/disabled domains (no fake assessment)."""
    pack = get_domain_pack(domain_code)
    status = pack.status.value if pack else "unavailable"
    title = pack.title if pack else domain_code
    return {
        "status": "domain_unavailable",
        "domain_code": domain_code,
        "domain_title": title,
        "domain_status": status,
        "message": (
            f"{title} is not available in LawApp yet. "
            "Only enabled domain packs with verified corpus and rules can be assessed."
        ),
        "error": type(exc).__name__,
        "invokes_llm": False,
        "result_type": "domain_gate",
    }
