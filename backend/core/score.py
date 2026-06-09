"""
Stage 4 — Grounding and confidence scoring.

Grounding score: fraction of legal claims in the assessment that trace to a
citation in the citations list. Every legal assertion must map to a retrieved
source. Unsupported assertions lower the score.

Confidence score: model-reported + heuristic modifiers.
  - retrieval quality: number and similarity of returned authorities
  - fact completeness: are the key fields (EDT, service start, weekly pay) present?
  - source agreement: if multiple sources returned, do they converge?

Thresholds are intentionally conservative and tuned empirically as the regression
set grows. Starting values chosen to pass most well-grounded assessments and
fail sparse ones.
"""

from __future__ import annotations

from shared.schemas import RetrievalBundle, StructuredAssessment

# Minimum grounding score to proceed through governance
GROUNDING_THRESHOLD = 0.3
# Minimum confidence score to proceed through governance
CONFIDENCE_THRESHOLD = 0.3

# Required fact fields for a complete unfair dismissal assessment
_REQUIRED_FACTS = {"edt", "effective_date_of_termination", "dismissal_date"}
_USEFUL_FACTS = {"service_start_date", "weekly_pay", "age", "reason_for_dismissal"}


def score(
    assessment: StructuredAssessment,
    bundle: RetrievalBundle,
    safe_facts: dict,
) -> StructuredAssessment:
    """
    Compute grounding and confidence scores and attach them to the assessment.
    Returns the assessment with scores set.
    """
    grounding = _compute_grounding(assessment, bundle)
    confidence = _compute_confidence(assessment, bundle, safe_facts)

    # Pydantic v2: return a new instance with updated scores
    return assessment.model_copy(update={
        "grounding_score": grounding,
        "confidence_score": confidence,
    })


def _compute_grounding(
    assessment: StructuredAssessment,
    bundle: RetrievalBundle,
) -> float:
    """
    Grounding score: fraction of key claims backed by a citation.

    Simple heuristic for Phase 2:
    - If insufficient_grounding=True: 0.0
    - If no citations: 0.0
    - If citations exist: base score of 0.5 + 0.1 per citation up to 1.0
    - If rules were retrieved: +0.2 (deterministic authority is strong grounding)

    This is intentionally simple and will be refined as the regression set grows.
    """
    if assessment.insufficient_grounding:
        return 0.0

    citation_count = len(assessment.citations)
    rules_count = len(bundle.exact_rules)

    if citation_count == 0 and rules_count == 0:
        return 0.0

    score = 0.0
    if rules_count > 0:
        score += 0.3   # rules are strong, deterministic grounding
    if citation_count > 0:
        score += 0.3   # at least one semantic citation
        score += min(0.4, citation_count * 0.1)   # additional per citation

    return round(min(score, 1.0), 2)


def _compute_confidence(
    assessment: StructuredAssessment,
    bundle: RetrievalBundle,
    safe_facts: dict,
) -> float:
    """
    Confidence score: model-reported + heuristic modifiers.

    For Phase 2 stub model: confidence is heuristic-only (no model-reported value).
    """
    if assessment.insufficient_grounding:
        return 0.0

    score = 0.0

    # Rules retrieved: deterministic facts available
    if bundle.exact_rules:
        score += 0.3

    # Semantic authorities retrieved
    authority_count = len(bundle.authorities)
    if authority_count > 0:
        score += min(0.3, authority_count * 0.1)

    # Key facts present
    fact_keys = {k.lower() for k in safe_facts}
    has_edt = bool(fact_keys & _REQUIRED_FACTS)
    useful_count = len(fact_keys & _USEFUL_FACTS)

    if has_edt:
        score += 0.2
    score += min(0.2, useful_count * 0.05)

    return round(min(score, 1.0), 2)


def below_threshold(assessment: StructuredAssessment) -> tuple[bool, str]:
    """
    Check whether either score falls below the governance threshold.
    Returns (failed, reason) — called by the governance gate.
    """
    if assessment.grounding_score < GROUNDING_THRESHOLD:
        return True, (
            f"Grounding score {assessment.grounding_score:.2f} below threshold "
            f"{GROUNDING_THRESHOLD}. Insufficient cited authority."
        )
    if assessment.confidence_score < CONFIDENCE_THRESHOLD:
        return True, (
            f"Confidence score {assessment.confidence_score:.2f} below threshold "
            f"{CONFIDENCE_THRESHOLD}. Fact pattern too sparse or ambiguous."
        )
    return False, ""
