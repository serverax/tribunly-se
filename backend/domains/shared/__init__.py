"""
backend.domains.shared  -  generic, domain-agnostic infrastructure.

This package MUST stay free of any single legal domain's substance
(no employment / immigration / housing rules, keywords, citations,
templates, or matter-type literals). It provides:

  - errors.py    : the fail-closed exception hierarchy
  - types.py     : the DomainSpec contract every domain registers under
  - templates.py : a by-domain template loader

The registry that wires concrete domains together lives one level up in
``backend.domains.registry`` so that ``shared`` itself never imports any
specific domain.
"""

from backend.domains.shared.errors import (
    DomainError,
    UnsupportedDomainError,
    DomainDisabledError,
    UnsupportedMatterError,
)
from backend.domains.shared.types import DomainSpec

__all__ = [
    "DomainError",
    "UnsupportedDomainError",
    "DomainDisabledError",
    "UnsupportedMatterError",
    "DomainSpec",
]
