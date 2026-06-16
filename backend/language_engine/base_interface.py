"""Language engine ABC: native rendering from language-neutral assessment core."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RenderedAssessment:
    """Locale-native presentation of a neutral assessment core."""

    locale: str
    direction: str  # "ltr" | "rtl"
    headline: str
    reasoning_summary: str
    key_weaknesses: list[str]
    employer_arguments: list[str]
    recommended_next_step: str
    recommended_next_step_label: str
    strength_label: str
    viability_label: str
    disclaimer: str
    formatted: dict[str, Any] = field(default_factory=dict)
    prompts_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "locale": self.locale,
            "direction": self.direction,
            "headline": self.headline,
            "reasoning_summary": self.reasoning_summary,
            "key_weaknesses": self.key_weaknesses,
            "employer_arguments": self.employer_arguments,
            "recommended_next_step": self.recommended_next_step,
            "recommended_next_step_label": self.recommended_next_step_label,
            "strength_label": self.strength_label,
            "viability_label": self.viability_label,
            "disclaimer": self.disclaimer,
            "formatted": self.formatted,
            "prompts_used": self.prompts_used,
        }


class LanguageEngine(ABC):
    """Renders language-neutral assessment cores in native legal phrasing."""

    locale: str = "en"
    direction: str = "ltr"

    @abstractmethod
    def render(self, assessment_core: dict[str, Any]) -> RenderedAssessment:
        """Produce native legal phrasing from neutral core (no translation pass)."""

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Native system prompt for this locale (documentation / LLM overlay)."""
