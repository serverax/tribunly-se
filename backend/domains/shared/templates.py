"""
By-domain template loader.

Resolves a domain's document-template registry dynamically from its DomainSpec,
so the document layer never hardcodes "which templates belong to which domain".
A domain exposes templates by declaring a ``templates_module`` in its DomainSpec;
that module must expose a ``TEMPLATES`` mapping of:

    { template_key: { "label": str,
                      "matter_types": list[str],
                      "generator": Callable | None } }

Placeholder/disabled domains declare no templates_module and resolve to an empty
registry — proving template isolation between domains.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict

from backend.domains.shared.errors import (
    UnsupportedDomainError,
    DomainDisabledError,
)


def load_domain_templates(domain: str, *, require_enabled: bool = True) -> Dict[str, Any]:
    """Return the TEMPLATES registry for ``domain``.

    Fail-closed:
      - unknown domain                -> UnsupportedDomainError
      - disabled domain (require_enabled) -> DomainDisabledError
      - domain has no templates_module    -> {} (empty, isolated)
    """
    # Imported lazily to avoid a shared<->registry import cycle.
    from backend.domains.registry import get_domain, is_domain_enabled

    spec = get_domain(domain)  # raises UnsupportedDomainError if unknown
    if require_enabled and not is_domain_enabled(domain):
        raise DomainDisabledError(domain)

    module_path = spec.get("templates_module")
    if not module_path:
        return {}

    module = importlib.import_module(module_path)
    templates = getattr(module, "TEMPLATES", None)
    if not isinstance(templates, dict):
        return {}
    return dict(templates)


def template_for(domain: str, template_key: str) -> Dict[str, Any]:
    """Return a single template entry for ``domain``/``template_key``.

    Raises KeyError if the template is not declared by the domain.
    """
    templates = load_domain_templates(domain)
    if template_key not in templates:
        raise KeyError(
            f"Template {template_key!r} is not declared by domain {domain!r}."
        )
    return templates[template_key]
