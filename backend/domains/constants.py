"""Platform-wide domain defaults (not domain-specific logic)."""

from __future__ import annotations

import os

# Single allowed default fallback when no domain is specified in request/env.
DOMAIN_DEFAULT: str = "employment"

ENV_DOMAIN_KEY = "LAWAPP_DOMAIN"


def active_domain_from_env() -> str:
    """Return LAWAPP_DOMAIN env value or DOMAIN_DEFAULT."""
    return (os.getenv(ENV_DOMAIN_KEY) or DOMAIN_DEFAULT).strip().lower()
