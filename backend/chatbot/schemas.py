from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


ChatMode = Literal["chat", "diagnosis", "document", "deadline", "handoff"]


class ChatMessageRequest(BaseModel):
    conversation_id: Optional[UUID] = None
    user_id: str = Field(..., min_length=1)
    case_id: Optional[UUID] = None
    message: str = Field(..., min_length=1)
    jurisdiction: str = "EW"
    mode: ChatMode = "chat"


class ChatMessageResponse(BaseModel):
    conversation_id: UUID
    case_id: Optional[UUID] = None
    answer: str
    claim_type: Optional[str] = None
    intent: str
    missing_facts: list[str]
    assessment: dict[str, Any]
    citations: list[dict[str, Any]]
    confidence_score: float
    grounding_score: float
    insufficient_grounding: bool
    next_actions: list[str]
    workflow_triggered: Optional[str] = None
    governance: dict[str, Any] = Field(default_factory=dict)
