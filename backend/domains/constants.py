"""Platform-wide domain defaults (not domain-specific logic)."""

from __future__ import annotations

import os

# Single allowed default fallback when no domain is specified in request/env.
DOMAIN_DEFAULT: str = "employment"

ENV_DOMAIN_KEY = "LAWAPP_DOMAIN"
ENV_DEFAULT_JURISDICTION_KEY = "LAWAPP_DEFAULT_JURISDICTION"
VALID_DEFAULT_JURISDICTIONS = ("EW", "SC", "NI")


def _load_default_jurisdiction() -> str:
    raw = os.getenv(ENV_DEFAULT_JURISDICTION_KEY, "EW").strip().upper()
    if raw not in VALID_DEFAULT_JURISDICTIONS:
        raise RuntimeError(
            f"{ENV_DEFAULT_JURISDICTION_KEY} must be one of {list(VALID_DEFAULT_JURISDICTIONS)}; got {raw!r}"
        )
    return raw


DEFAULT_JURISDICTION: str = _load_default_jurisdiction()


def active_domain_from_env() -> str:
    """Return LAWAPP_DOMAIN env value or DOMAIN_DEFAULT."""
    return (os.getenv(ENV_DOMAIN_KEY) or DOMAIN_DEFAULT).strip().lower()
