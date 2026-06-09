"""Typed errors for the 4-agent architecture. All fail closed."""

from __future__ import annotations


class AgenticError(Exception):
    """Base class for all agentic failures."""


class PolicyViolation(AgenticError):
    """A routing/escalation policy was violated (e.g. cloud route not allowed)."""


class PIIBoundaryViolation(AgenticError):
    """Raw PII would have crossed a boundary it is not permitted to cross
    (logs / traces / cache / cloud). Always fail closed."""


class AgentOutputError(AgenticError):
    """Model output failed strict JSON / schema validation."""


class GroundingError(AgenticError):
    """Insufficient retrieval/rules grounding to proceed safely."""
