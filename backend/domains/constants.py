"""Platform-wide domain defaults (not domain-specific logic)."""

from __future__ import annotations

import os

# Single allowed default fallback when no domain is specified in request/env.
DOMAIN_DEFAULT: str = "employment"

ENV_DOMAIN_KEY = "LAWAPP_DOMAIN"

# Default jurisdiction when none supplied by the caller.
# Configurable via env so a future deployment can override without code changes.
DEFAULT_JURISDICTION: str = os.getenv("LAWAPP_DEFAULT_JURISDICTION", "EW")


def active_domain_from_env() -> str:
    """Return LAWAPP_DOMAIN env value or DOMAIN_DEFAULT."""
    return (os.getenv(ENV_DOMAIN_KEY) or DOMAIN_DEFAULT).strip().lower()
