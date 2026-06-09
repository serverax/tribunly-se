from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from backend.chatbot.controller import handle_chat_message
from backend.chatbot.schemas import ChatMessageRequest, ChatMessageResponse

router = APIRouter(prefix="/api/chat", tags=["controlled-chatbot"])


@router.post("/message", response_model=ChatMessageResponse)
def chat_message(req: ChatMessageRequest) -> ChatMessageResponse:
    return handle_chat_message(req)


@router.post("/stream")
def chat_stream(req: ChatMessageRequest) -> dict:
    response = handle_chat_message(req)
    return {
        "streaming": False,
        "reason": "Streaming disabled until every chatbot proof gate passes.",
        "response": response.model_dump(mode="json"),
    }


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: UUID, user_id: str) -> dict:
    from ingestion.db import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, message, intent, claim_type, pipeline_state, metadata, created_at
                FROM conversation_events
                WHERE conversation_id = %s::uuid AND user_id = %s
                ORDER BY created_at ASC
                """,
                (str(conversation_id), user_id),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return {
        "conversation_id": str(conversation_id),
        "events": [
            {
                "role": row[0],
                "message": row[1],
                "intent": row[2],
                "claim_type": row[3],
                "pipeline_state": row[4],
                "metadata": row[5],
                "created_at": row[6].isoformat(),
            }
            for row in rows
        ],
    }


@router.post("/conversations/{conversation_id}/save-to-case")
def save_to_case(conversation_id: UUID) -> dict:
    raise HTTPException(status_code=501, detail="save-to-case requires case-service integration proof before enablement.")


@router.post("/continue-workflow")
def continue_workflow(req: ChatMessageRequest) -> ChatMessageResponse:
    return handle_chat_message(req)


@router.post("/missing-facts")
def missing_facts(req: ChatMessageRequest) -> dict:
    from backend.chatbot.claim_type_router import route_claim_type
    from backend.chatbot.fact_extractor import extract_facts
    from backend.chatbot.missing_facts import missing_facts_for

    claim_type = route_claim_type(req.message)
    facts = extract_facts(req.message)
    return {
        "claim_type": claim_type,
        "facts_detected": facts,
        "missing_facts": missing_facts_for(claim_type, facts),
    }


@router.post("/feedback")
def feedback() -> dict:
    raise HTTPException(status_code=501, detail="feedback persistence requires audit schema proof before enablement.")
