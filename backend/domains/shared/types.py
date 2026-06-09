"""
The DomainSpec contract.

A legal domain is described declaratively by a DomainSpec. The registry stores
one DomainSpec per domain. Anything the rest of the platform needs to know in
order to route, gate, retrieve, and document a matter is expressed here — so a
NEW domain can be added by registering a DomainSpec, with no edit to shared
core (CLAUDE.md §4: modular; new domains must not require a core rewrite).

DomainSpec is a TypedDict (not a class with behaviour) on purpose: it must be
trivially serialisable, declarable as a plain dict literal in registry.py, and
registrable at runtime by a brand-new domain (including a test domain).
"""

from __future__ import annotations

from typing import List, Optional, TypedDict


class DomainSpec(TypedDict, total=False):
    """Declarative description of one legal domain.

    Fields
    ------
    name:
        Stable machine key, e.g. "employment". Used everywhere as the domain id.
    enabled:
        True only when the domain is production-ready (real rules, corpus,
        templates, tests). Disabled domains fail closed.
    matter_types:
        Matter types this domain owns, e.g. ["unfair_dismissal", "unpaid_wages"].
        The union across enabled domains is the platform's supported scope.
    jurisdiction:
        Jurisdiction codes served, e.g. ["EW", "S"] (England & Wales, Scotland).
    rules_pack:
        Logical name of the rules pack / rules-table partition for this domain,
        e.g. "employment_rules". Used by retrieval/rule-engine scoping.
    retrieval_domain:
        Value written to the retrieval audit `domain` column and used to scope
        corpus retrieval, e.g. "employment_uk". Defaults to `name` when absent.
    templates_module:
        Importable module path exposing this domain's TEMPLATES registry,
        e.g. "backend.domains.employment.templates". Absent for placeholders.
    label:
        Human-readable name for UI / reports, e.g. "Employment (UK)".
    """

    name: str
    enabled: bool
    matter_types: List[str]
    jurisdiction: List[str]
    rules_pack: Optional[str]
    retrieval_domain: Optional[str]
    templates_module: Optional[str]
    label: Optional[str]
