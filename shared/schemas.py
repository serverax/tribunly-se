"""
Shared Pydantic schemas used by both the ingestion pipeline and the backend API.

The STRUCTURED ASSESSMENT OBJECT is the canonical output of the reasoning layer.
It is data, not prose  -  validated before display, scored, and rendered by the client.
Full spec: docs/04_RAG_REASONING_SPEC.md §4.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Citation(BaseModel):
    cite: str                        # e.g. "ERA 1996 s.111(2)"
    url: str                         # canonical source URL


class ValueRange(BaseModel):
    low: float
    high: float
    currency: str = "GBP"
    basis: str                       # e.g. "from rules + estimated loss"


class Deadline(BaseModel):
    limitation_date: Optional[date]
    source: Literal["rules"]         # GUARDRAIL: must always be "rules", never "model"
    authority: str                   # e.g. "ERA 1996 s.111(2)"
    is_prospective: bool = False     # True if the applicable rule is prospective


class StructuredAssessment(BaseModel):
    """
    Canonical output of the reasoning layer. Validated before display.
    Prose shown to the user is generated FROM this object, not by the model directly.
    """
    claim_type: str                  # e.g. "unfair_dismissal"
    jurisdiction: str = "EW"

    has_viable_claim: Literal["yes", "no", "uncertain"]
    strength: Literal["low", "medium", "high", "uncertain"]

    reasoning_summary: str = Field(
        ...,
        description="Plain-English summary, ≤150 words, no legal jargon",
        max_length=1500,
    )

    value_range: Optional[ValueRange]
    key_weaknesses: list[str]        # GUARDRAIL: must be non-empty for non-trivial cases
    employer_arguments: list[str] = Field(
        default_factory=list,
        description="What the employer may argue  -  deterministic from facts and reason",
    )

    deadline: Optional[Deadline]

    recommended_next_step: Literal[
        "free_diagnosis_only",
        "prepare_documents",
        "seek_solicitor",
    ]

    citations: list[Citation]        # every legal claim must have a citation

    # Scoring (set by the governance layer)
    grounding_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    insufficient_grounding: bool = False


class ClassificationResult(BaseModel):
    matter_type: str                 # e.g. "unfair_dismissal"
    intent: Literal["diagnosis", "document", "deadline_check"]
    in_scope: bool


class RetrievalBundle(BaseModel):
    """Output of the retrieval layer (Stage 2 in 04_RAG_REASONING_SPEC.md)."""
    exact_rules: list[dict]          # rows from the rules table
    authorities: list[dict]          # cited legislation/case_law/acas chunks
    insufficient_grounding: bool = False
