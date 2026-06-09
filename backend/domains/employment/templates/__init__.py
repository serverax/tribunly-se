"""
Employment domain — document template registry.

This is the by-domain template registry consumed via
``backend.domains.shared.templates.load_domain_templates("employment")``
(wired through the ``templates_module`` field of the employment DomainSpec in
``backend.domains.registry``).

Each entry maps a template key to:
  - label        : human-readable name
  - matter_types : which employment matter types the template applies to
  - generator    : dotted import path to the REAL generator function

The generators currently live in ``backend.core.documents`` (see the
"Core decoupling backlog" in the Subagent 6 report — physically relocating the
generator bodies into this package is tracked future work). They are referenced
here by dotted path rather than imported eagerly, so loading the registry does
not pull heavy document dependencies (python-docx) at import time, and so a
caller resolves the callable only when it actually generates a document.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable, Dict

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "particulars_of_claim": {
        "label": "Particulars of Claim",
        "matter_types": ["unfair_dismissal"],
        "generator": "backend.core.documents.generate_particulars_of_claim",
    },
    "schedule_of_loss": {
        "label": "Schedule of Loss",
        "matter_types": ["unfair_dismissal"],
        "generator": "backend.core.documents.generate_schedule_of_loss",
    },
    "letter_before_action": {
        "label": "Letter Before Action",
        "matter_types": ["unfair_dismissal", "unpaid_wages"],
        "generator": "backend.core.documents.generate_letter_before_action",
    },
    "et1_support_notes_wages": {
        "label": "ET1 Support Notes (Unpaid Wages)",
        "matter_types": ["unpaid_wages"],
        "generator": "backend.core.documents.generate_et1_support_notes_wages",
    },
}


def resolve_generator(template_key: str) -> Callable[..., Any]:
    """Import and return the generator callable for ``template_key``.

    Raises KeyError for an unknown key (fail closed — never fabricate a doc).
    """
    entry = TEMPLATES[template_key]
    module_path, _, func_name = entry["generator"].rpartition(".")
    module = importlib.import_module(module_path)
    return getattr(module, func_name)
