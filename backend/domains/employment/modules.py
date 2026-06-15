"""Server-side UK employment-law module catalogue.

This is the product scope target, not a production-support claim. A module is
production-supported only when it has DB-backed rules/sources, workflow proof,
templates where relevant, and tests. Until then it must fail closed.
"""

from __future__ import annotations

from typing import TypedDict


class EmploymentModule(TypedDict):
    key: str
    label: str
    status: str
    db_backed_required: bool


REQUIRED_EMPLOYMENT_MODULES: tuple[EmploymentModule, ...] = (
    {"key": "unfair_dismissal", "label": "Unfair dismissal", "status": "production", "db_backed_required": True},
    {"key": "unpaid_wages", "label": "Unpaid wages / unlawful deduction", "status": "production", "db_backed_required": True},
    {"key": "constructive_dismissal", "label": "Constructive dismissal", "status": "partial", "db_backed_required": True},
    {"key": "wrongful_dismissal", "label": "Wrongful dismissal / notice pay", "status": "production", "db_backed_required": True},
    {"key": "redundancy", "label": "Redundancy rights and pay", "status": "production", "db_backed_required": True},
    {"key": "discrimination", "label": "Discrimination", "status": "partial", "db_backed_required": True},
    {"key": "pregnancy_maternity_discrimination", "label": "Pregnancy and maternity discrimination", "status": "partial", "db_backed_required": True},
    {"key": "equal_pay", "label": "Equal pay", "status": "partial", "db_backed_required": True},
    {"key": "whistleblowing", "label": "Whistleblowing detriment/dismissal", "status": "partial", "db_backed_required": True},
    {"key": "health_and_safety", "label": "Health and safety detriment/dismissal", "status": "partial", "db_backed_required": True},
    {"key": "trade_union_rights", "label": "Trade union rights", "status": "partial", "db_backed_required": True},
    {"key": "flexible_working", "label": "Flexible working", "status": "production", "db_backed_required": True},
    {"key": "maternity_rights", "label": "Maternity rights", "status": "partial", "db_backed_required": True},
    {"key": "paternity_rights", "label": "Paternity rights", "status": "partial", "db_backed_required": True},
    {"key": "parental_leave", "label": "Parental leave", "status": "partial", "db_backed_required": True},
    {"key": "shared_parental_leave", "label": "Shared parental leave", "status": "partial", "db_backed_required": True},
    {"key": "holiday_pay", "label": "Holiday pay and annual leave", "status": "production", "db_backed_required": True},
    {"key": "working_time", "label": "Working time and rest breaks", "status": "production", "db_backed_required": True},
    {"key": "national_minimum_wage", "label": "National Minimum Wage", "status": "partial", "db_backed_required": True},
    {"key": "part_time_workers", "label": "Part-time worker rights", "status": "production", "db_backed_required": True},
    {"key": "fixed_term_workers", "label": "Fixed-term worker rights", "status": "production", "db_backed_required": True},
    {"key": "agency_workers", "label": "Agency worker rights", "status": "production", "db_backed_required": True},
    {"key": "tupe", "label": "TUPE transfers", "status": "partial", "db_backed_required": True},
    {"key": "employment_contracts", "label": "Employment contracts / written particulars", "status": "production", "db_backed_required": True},
)


PRODUCTION_EMPLOYMENT_MODULES: tuple[str, ...] = tuple(
    module["key"] for module in REQUIRED_EMPLOYMENT_MODULES if module["status"] == "production"
)

# Permanent product scope cut (Track B): partial modules remain DB-catalogued for future
# work but are explicitly NOT covered in the current 11-topic product surface.
SCOPE_CUT_MODULES: tuple[str, ...] = tuple(
    module["key"] for module in REQUIRED_EMPLOYMENT_MODULES if module["status"] == "partial"
)

SCOPE_CUT_MESSAGE = (
    "This employment topic is not covered in the current LawApp product scope. "
    "It is catalogued for future development but has no verified end-to-end workflow, "
    "legal-accuracy bar, or document templates yet."
)


def module_keys() -> list[str]:
    return [module["key"] for module in REQUIRED_EMPLOYMENT_MODULES]


def production_module_keys() -> list[str]:
    return list(PRODUCTION_EMPLOYMENT_MODULES)


def module_coverage() -> dict:
    total = len(REQUIRED_EMPLOYMENT_MODULES)
    production = len(PRODUCTION_EMPLOYMENT_MODULES)
    scope_cut = len(SCOPE_CUT_MODULES)
    return {
        "required_total": total,
        "production_total": production,
        "scope_cut_total": scope_cut,
        "remaining_total": total - production,
        "modules": list(REQUIRED_EMPLOYMENT_MODULES),
        "scope_cut_modules": list(SCOPE_CUT_MODULES),
    }


def is_scope_cut(module_key: str) -> bool:
    return module_key in SCOPE_CUT_MODULES
