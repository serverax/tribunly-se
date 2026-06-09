"""
backend.domains.employment — the UK employment-law domain.

This is the platform's first and only production-enabled legal domain. It owns
the employment-specific rules, checklists, templates, and workflow logic:

  - deadline.py                : limitation-date / qualifying-period rules
  - assess_logic.py            : deterministic assessment context
  - constructive_dismissal.py  : constructive-dismissal assessment
  - compliance.py              : ACAS / pre-claim compliance status
  - timeline.py, reminders.py  : matter timeline + urgency
  - checklists/                : Burchell, tribunal elements, evidence weight, ACAS
  - templates/                 : document template registry (TEMPLATES)

It is registered (enabled=True) in ``backend.domains.registry`` and owns the
matter types ``unfair_dismissal`` and ``unpaid_wages`` for jurisdictions EW & S.
The registry — not this package — is the single source of truth for whether the
domain is enabled and what scope it serves.
"""

DOMAIN = "employment"
