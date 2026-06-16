"""
Fail-closed exception hierarchy for the domain layer.

Every guard in the modular-domain platform raises one of these rather than
silently degrading. Callers that cannot prove a domain/matter is supported
must NOT proceed  -  that is the core safety property (CLAUDE.md §9, §17:
fail closed; never guess in_scope=True).
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-layer failures."""


class UnsupportedDomainError(DomainError):
    """Raised when a domain key is not registered at all."""

    def __init__(self, domain: str):
        self.domain = domain
        super().__init__(f"Unsupported legal domain: {domain!r} is not registered.")


class DomainDisabledError(DomainError):
    """Raised when a domain exists but is not enabled for production use."""

    def __init__(self, domain: str):
        self.domain = domain
        super().__init__(
            f"Legal domain {domain!r} is registered but disabled "
            f"(enabled=False). It cannot serve requests."
        )


class UnsupportedMatterError(DomainError):
    """Raised when a matter type is not owned by any enabled domain."""

    def __init__(self, matter_type: str):
        self.matter_type = matter_type
        super().__init__(
            f"Matter type {matter_type!r} is not supported by any enabled domain."
        )
