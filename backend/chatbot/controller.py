from __future__ import annotations

from uuid import uuid4

from backend.chatbot.answer_composer import compose_answer
from backend.chatbot.authority_builder import build_authority_bundle
from backend.chatbot.claim_type_router import route_claim_type
from backend.chatbot.fact_extractor import extract_facts
from backend.chatbot.intent_classifier import detect_intent
from backend.chatbot.memory import record_conversation_event
from backend.chatbot.missing_facts import missing_facts_for
from backend.chatbot.safety import govern_answer
from backend.chatbot.schemas import ChatMessageRequest, ChatMessageResponse


def handle_chat_message(req: ChatMessageRequest) -> ChatMessageResponse:
    conversation_id = req.conversation_id or uuid4()
    intent = detect_intent(req.message, req.mode)
    claim_type = route_claim_type(req.message)
    facts = extract_facts(req.message)
    missing = missing_facts_for(claim_type, facts) if intent in {"diagnosis", "deadline", "value"} else []

    record_conversation_event(
        conversation_id=conversation_id,
        user_id=req.user_id,
        case_id=req.case_id,
        role="user",
        message=req.message,
        intent=intent,
        claim_type=claim_type,
        pipeline_state="NEW_MESSAGE",
        metadata={"mode": req.mode, "jurisdiction": req.jurisdiction},
    )

    authority = build_authority_bundle(req.message, claim_type, facts)
    assessment: dict = {}
    confidence_score = float(authority.get("confidence_score") or 0.35)

    if intent == "diagnosis" and claim_type == "unfair_dismissal" and not missing and not authority["insufficient_grounding"]:
        from backend.core.employment_assessment import assess_case

        rules = {}
        for rule in authority.get("exact_rules", []):
            key = str(rule.get("rule_key") or "").replace("unfair_dismissal.", "")
            value = rule.get("value_numeric")
            if value is not None:
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    continue
                if key == "qualifying_period":
                    rules["qualifying_period_months"] = numeric * 12
                elif key == "basic_award_min_automatic":
                    rules["basic_award_min"] = numeric
                else:
                    rules[key] = numeric
        assessment = assess_case("unfair_dismissal", facts, rules)
        confidence_score = float(assessment.get("confidence_score", assessment.get("confidence", 0.5)))

    answer, next_actions, workflow = compose_answer(
        intent=intent,
        claim_type=claim_type,
        missing_facts=missing,
        assessment=assessment,
        citations=authority["citations"],
        insufficient_grounding=authority["insufficient_grounding"],
    )
    governance = govern_answer(
        answer,
        authority["citations"],
        float(authority["grounding_score"]),
        confidence_score,
    )
    if not governance["pass"]:
        answer = (
            "I cannot answer confidently from the currently retrieved UK employment-law sources. "
            "Please provide more facts or consider solicitor handoff."
        )
        next_actions = ["ask_missing_questions", "solicitor_handoff"]
        workflow = "handoff" if "weak_grounding" in governance["failures"] else workflow

    record_conversation_event(
        conversation_id=conversation_id,
        user_id=req.user_id,
        case_id=req.case_id,
        role="assistant",
        message=answer,
        intent=intent,
        claim_type=claim_type,
        pipeline_state="AUDITED",
        metadata={"governance": governance, "next_actions": next_actions},
    )

    return ChatMessageResponse(
        conversation_id=conversation_id,
        case_id=req.case_id,
        answer=answer,
        claim_type=claim_type,
        intent=intent,
        missing_facts=missing,
        assessment=assessment,
        citations=authority["citations"],
        confidence_score=confidence_score,
        grounding_score=float(authority["grounding_score"]),
        insufficient_grounding=authority["insufficient_grounding"] or not governance["pass"],
        next_actions=next_actions,
        workflow_triggered=workflow,
        governance=governance,
    )
