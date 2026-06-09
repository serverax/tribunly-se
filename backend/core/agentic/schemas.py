"""
Strict Pydantic schemas for the 4-agent architecture (the "schema wall").

Every agent input/output is validated here BEFORE it can affect the DB, UI,
documents, or user response (AC-003). Rules:
  * extra keys are forbidden (model_config extra="forbid")
  * enums are strict
  * confidence/grounding scores in [0,1]; viability in [0,100]
  * dates are ISO-8601 (YYYY-MM-DD) or null where allowed
  * conversational / markdown-fenced JSON is rejected (AC-004) by
    ``strict_json_parse_no_wrappers`` — output is never silently repaired
"""

from __future__ import annotations

import json
import re
from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.core.agentic.errors import AgentOutputError

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── shared enums ──────────────────────────────────────────────────────────────
class AgentName(str, Enum):
    AEE = "AEE"
    ART = "ART"
    SEA = "SEA"
    CITATION_GUARD = "CITATION_GUARD"


class Jurisdiction(str, Enum):
    EW = "EW"
    S = "S"
    NI = "NI"
    UNKNOWN = "UNKNOWN"


class SourceType(str, Enum):
    manual_text = "manual_text"
    email = "email"
    whatsapp = "whatsapp"
    pdf_ocr = "pdf_ocr"
    document_upload = "document_upload"


class DateStatus(str, Enum):
    exact = "exact"
    ambiguous = "ambiguous"
    missing = "missing"
    relative_requires_confirmation = "relative_requires_confirmation"


class EvidenceType(str, Enum):
    dismissal = "dismissal"
    grievance = "grievance"
    disciplinary = "disciplinary"
    contract = "contract"
    pay = "pay"
    sickness = "sickness"
    discrimination = "discrimination"
    acas = "acas"
    other = "other"


class PIIType(str, Enum):
    person = "person"
    employer = "employer"
    phone = "phone"
    email = "email"
    address = "address"
    financial = "financial"
    medical = "medical"
    other = "other"


class ClaimType(str, Enum):
    unfair_dismissal = "unfair_dismissal"
    constructive_dismissal = "constructive_dismissal"
    discrimination = "discrimination"
    none = "none"


class ClaimScope(str, Enum):
    unfair_dismissal = "unfair_dismissal"
    constructive_dismissal = "constructive_dismissal"
    discrimination = "discrimination"
    unknown = "unknown"


class Strength(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    uncertain = "uncertain"


class LimitationStatus(str, Enum):
    in_time = "in_time"
    near_deadline = "near_deadline"
    out_of_time = "out_of_time"
    unknown = "unknown"


class RecommendedNextStep(str, Enum):
    free_diagnosis_only = "free_diagnosis_only"
    prepare_documents = "prepare_documents"
    seek_solicitor = "seek_solicitor"
    not_supported = "not_supported"
    need_more_facts = "need_more_facts"


class DocumentType(str, Enum):
    particulars_of_claim = "particulars_of_claim"
    schedule_of_loss = "schedule_of_loss"
    grievance_letter = "grievance_letter"
    chronology = "chronology"
    evidence_checklist = "evidence_checklist"


class _Strict(BaseModel):
    """Base: forbid extra keys, validate on assignment."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


def _iso_or_none(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    if not isinstance(v, str) or not _ISO_DATE.match(v):
        raise ValueError("date must be ISO-8601 YYYY-MM-DD or null")
    date.fromisoformat(v)  # raises on invalid calendar date
    return v


def _iso_required(v: str) -> str:
    if not isinstance(v, str) or not _ISO_DATE.match(v):
        raise ValueError("date must be ISO-8601 YYYY-MM-DD")
    date.fromisoformat(v)
    return v


# ── AEE ───────────────────────────────────────────────────────────────────────
class AEEInput(_Strict):
    case_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    current_date: str
    raw_text: str = Field(min_length=1)
    source_type: SourceType
    jurisdiction: Jurisdiction

    @field_validator("current_date")
    @classmethod
    def _cd(cls, v): return _iso_required(v)


class AEEEvent(_Strict):
    date: Optional[str] = None
    date_status: DateStatus
    event_summary: str = Field(min_length=1)
    evidence_type: EvidenceType
    source_quote: str
    pii_scrubbed: bool
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("date")
    @classmethod
    def _d(cls, v): return _iso_or_none(v)


class PIIRedaction(_Strict):
    type: PIIType
    replacement: str = Field(min_length=1)


class AEEOutput(_Strict):
    timeline: list[AEEEvent]
    missing_critical_dates: bool
    pii_redactions: list[PIIRedaction]
    requires_user_confirmation: bool


# ── ART ───────────────────────────────────────────────────────────────────────
class ARTInput(_Strict):
    case_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    jurisdiction: Jurisdiction
    confirmed_timeline: list[dict]
    retrieved_authorities: list[dict]
    exact_rules: list[dict]
    claim_scope: ClaimScope
    user_confirmed_facts_only: bool


class ARTOutput(_Strict):
    claim_type: list[ClaimType]
    viability_score_percentage: int = Field(ge=0, le=100)
    strength: Strength
    statutory_citations_used: list[str]
    case_law_citations_used: list[str]
    acas_citations_used: list[str]
    key_weaknesses: list[str]
    affirmation_risk_detected: bool
    repudiatory_breach_detected: bool
    causation_assessed: bool
    limitation_status: LimitationStatus
    recommended_next_step: RecommendedNextStep
    grounding_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    insufficient_grounding: bool


# ── SEA ───────────────────────────────────────────────────────────────────────
class SEAInput(_Strict):
    case_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    document_type: DocumentType
    validated_assessment: dict
    confirmed_facts: dict
    approved_citations: list[str]
    template_id: str
    boundary_notice_required: bool


class SEAOutput(_Strict):
    document_type: DocumentType
    markdown: str = Field(min_length=1)
    citations_used: list[str]
    boundary_notice_present: bool
    generated_from_assessment_id: str = Field(min_length=1)
    requires_guard_review: bool


# ── Citation & Safety Guard ───────────────────────────────────────────────────
class CitationGuardInput(_Strict):
    case_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    draft_document: str = Field(min_length=1)
    assessment: dict
    verified_citations: list[str]
    legal_boundary_rules: list[str]


class CitationGuardOutput(_Strict):
    safety_check_passed: bool
    failed_citations: list[str]
    unsupported_legal_assertions: list[str]
    reserved_activity_flags: list[str]
    boundary_notice_present: bool
    reason_for_failure: str


# ── audit records (AC-010) ────────────────────────────────────────────────────
class AgentRunRecord(_Strict):
    trace_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    agent_name: AgentName
    model_name: str
    model_route: str
    input_schema_version: str
    output_schema_version: str
    started_at: str
    completed_at: Optional[str] = None
    status: str
    validation_passed: bool
    grounding_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    escalated: bool = False
    failure_reason: Optional[str] = None


class AgentValidationFailure(_Strict):
    trace_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    agent_name: AgentName
    raw_output_excerpt: str
    failure_reason: str


class AgentEscalationRecord(_Strict):
    trace_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    agent_name: AgentName
    reason: str
    grounding_score: float = Field(ge=0.0, le=1.0)
    pii_scrub_passed: bool


SCHEMA_VERSION = "1.0"

# map agent -> output schema, used by the adapter for validation
OUTPUT_SCHEMAS: dict[AgentName, type[_Strict]] = {
    AgentName.AEE: AEEOutput,
    AgentName.ART: ARTOutput,
    AgentName.SEA: SEAOutput,
    AgentName.CITATION_GUARD: CitationGuardOutput,
}


def strict_json_parse_no_wrappers(content: str) -> dict:
    """Parse model output as a bare JSON object. Reject markdown fences,
    conversational prefixes/suffixes, and non-object JSON (AC-004).
    Never silently repairs."""
    if content is None:
        raise AgentOutputError("empty model output")
    s = content.strip()
    if "```" in s:
        raise AgentOutputError("markdown-fenced output is not accepted")
    if not (s.startswith("{") and s.endswith("}")):
        raise AgentOutputError("conversational wrapper or non-JSON output rejected")
    try:
        obj = json.loads(s)
    except Exception as exc:
        raise AgentOutputError(f"invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise AgentOutputError("top-level JSON must be an object")
    return obj
