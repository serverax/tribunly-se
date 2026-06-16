"""Language-neutral assessment types shared across locale modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


SUPPORTED_LOCALES = frozenset({"en", "ar"})
FUTURE_LOCALES = frozenset({"ur", "fr", "hi"})


@dataclass
class LanguageNeutralAssessment:
    """Structured legal output before locale-specific phrasing."""

    status: str
    claim_type: str
    jurisdiction: str
    strength: str = "uncertain"
    has_viable_claim: Optional[bool] = None
    reasoning_summary: str = ""
    key_weaknesses: list[str] = field(default_factory=list)
    employer_arguments: list[str] = field(default_factory=list)
    recommended_next_step: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    rule_keys: list[str] = field(default_factory=list)
    deadline: Optional[dict[str, Any]] = None
    grounding_score: Optional[float] = None
    confidence_score: Optional[float] = None
    trace_id: str = ""

    @classmethod
    def from_pipeline_dict(cls, payload: dict[str, Any]) -> "LanguageNeutralAssessment":
        citations = payload.get("citations") or []
        rule_keys: list[str] = []
        for c in citations:
            rk = c.get("rule_key")
            if rk:
                rule_keys.append(str(rk))
        for r in payload.get("rules") or []:
            rk = r.get("rule_key")
            if rk and rk not in rule_keys:
                rule_keys.append(str(rk))

        return cls(
            status=str(payload.get("status") or "unknown"),
            claim_type=str(payload.get("claim_type") or "unfair_dismissal"),
            jurisdiction=str(payload.get("jurisdiction") or "EW"),
            strength=str(payload.get("strength") or "uncertain"),
            has_viable_claim=payload.get("has_viable_claim"),
            reasoning_summary=str(payload.get("reasoning_summary") or payload.get("summary") or ""),
            key_weaknesses=list(payload.get("key_weaknesses") or []),
            employer_arguments=list(payload.get("employer_arguments") or []),
            recommended_next_step=str(payload.get("recommended_next_step") or ""),
            citations=citations,
            rule_keys=rule_keys,
            deadline=payload.get("deadline"),
            grounding_score=payload.get("grounding_score"),
            confidence_score=payload.get("confidence_score"),
            trace_id=str(payload.get("trace_id") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "claim_type": self.claim_type,
            "jurisdiction": self.jurisdiction,
            "strength": self.strength,
            "has_viable_claim": self.has_viable_claim,
            "reasoning_summary": self.reasoning_summary,
            "key_weaknesses": self.key_weaknesses,
            "employer_arguments": self.employer_arguments,
            "recommended_next_step": self.recommended_next_step,
            "citations": self.citations,
            "rule_keys": self.rule_keys,
            "deadline": self.deadline,
            "grounding_score": self.grounding_score,
            "confidence_score": self.confidence_score,
            "trace_id": self.trace_id,
        }


@dataclass
class RenderContext:
    """Locale render context (no translation pipeline)."""

    locale: str
    dir: str = "ltr"
    font_stack: str = ""
    llm_phrasing_enabled: bool = True

    @classmethod
    def for_locale(cls, locale: str) -> "RenderContext":
        loc = locale if locale in SUPPORTED_LOCALES else "en"
        if loc == "ar":
            return cls(
                locale=loc,
                dir="rtl",
                font_stack='"Noto Naskh Arabic", "Segoe UI", Tahoma, sans-serif',
            )
        return cls(
            locale=loc,
            dir="ltr",
            font_stack='"Inter", system-ui, sans-serif',
        )


@dataclass
class RenderedAssessment:
    """Native-language presentation over neutral core."""

    locale: str
    dir: str
    reasoning_summary: str
    key_weaknesses: list[str]
    employer_arguments: list[str]
    recommended_next_step: str
    strength_label: str
    headline: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "locale": self.locale,
            "dir": self.dir,
            "reasoning_summary": self.reasoning_summary,
            "key_weaknesses": self.key_weaknesses,
            "employer_arguments": self.employer_arguments,
            "recommended_next_step": self.recommended_next_step,
            "strength_label": self.strength_label,
            "headline": self.headline,
        }
