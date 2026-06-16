"""Arabic native language engine (RTL, formal legal tone)."""

from __future__ import annotations

from typing import Any

from backend.language_engine.ar import formatter, prompts
from backend.language_engine.base_interface import LanguageEngine, RenderedAssessment


class ArabicLanguageEngine(LanguageEngine):
    locale = "ar"
    direction = "rtl"

    @property
    def system_prompt(self) -> str:
        return prompts.SYSTEM_PROMPT

    def render(self, assessment_core: dict[str, Any]) -> RenderedAssessment:
        data = formatter.format_assessment(assessment_core)
        return RenderedAssessment(
            locale=self.locale,
            direction=self.direction,
            headline=data["headline"],
            reasoning_summary=data["reasoning_summary"],
            key_weaknesses=data["key_weaknesses"],
            employer_arguments=data["employer_arguments"],
            recommended_next_step=data["recommended_next_step"],
            recommended_next_step_label=data["recommended_next_step_label"],
            strength_label=data["strength_label"],
            viability_label=data["viability_label"],
            disclaimer=data["disclaimer"],
            formatted=data["formatted"],
            prompts_used=["ar.system", "ar.unfair_dismissal", "ar.explanation_style"],
        )
