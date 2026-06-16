"""Language-neutral legal type codes shared across locale engines."""

from __future__ import annotations

from typing import Literal

ClaimType = Literal[
    "unfair_dismissal",
    "unpaid_wages",
    "discrimination",
    "redundancy",
    "wrongful_dismissal",
    "constructive_dismissal",
    "out_of_scope",
]

StrengthCode = Literal["low", "medium", "high", "uncertain"]
ViabilityCode = Literal["yes", "no", "uncertain"]
NextStepCode = Literal["free_diagnosis_only", "prepare_documents", "seek_solicitor"]

SUPPORTED_LOCALES = frozenset({"en", "ar"})
DEFAULT_LOCALE = "en"
