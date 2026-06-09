from __future__ import annotations


def compose_answer(
    *,
    intent: str,
    claim_type: str | None,
    missing_facts: list[str],
    assessment: dict,
    citations: list[dict],
    insufficient_grounding: bool,
) -> tuple[str, list[str], str | None]:
    if missing_facts:
        facts = ", ".join(missing_facts)
        return (
            f"I need more facts before giving a stronger assessment. Please provide: {facts}.",
            ["ask_missing_questions"],
            None,
        )

    if insufficient_grounding:
        return (
            "I cannot answer confidently from the current lawapp UK employment-law sources. "
            "The safe next step is to add more facts or request solicitor handoff.",
            ["ask_missing_questions", "solicitor_handoff"],
            "handoff",
        )

    if intent == "deadline":
        return (
            "This needs a deterministic deadline calculation from the rules table, including ACAS dates if relevant.",
            ["calculate_deadline"],
            "deadline",
        )

    if intent == "value":
        return (
            "This needs a deterministic value calculation from rules-table caps, bands, service length, pay, and losses.",
            ["calculate_value"],
            "value",
        )

    if intent == "document":
        return (
            "Documents are payment-gated. lawapp must verify payment before generating full self-help draft documents.",
            ["check_payment", "prepare_documents"],
            "document",
        )

    viable = assessment.get("viable_claim")
    if viable is True:
        answer = (
            f"Based on the facts supplied, this may be a {claim_type} issue. "
            "The assessment is not legal advice and should be checked against the cited sources. "
            "Next step: calculate the deadline, preserve evidence, and prepare documents only after payment is verified."
        )
        return answer, ["calculate_deadline", "prepare_documents", "upload_evidence"], "diagnosis"

    if viable is False:
        return (
            f"Based on the facts supplied, this does not currently look like a viable {claim_type} claim. "
            "The key weaknesses should be reviewed, and solicitor handoff may be appropriate if facts are complex.",
            ["review_weaknesses", "solicitor_handoff"],
            "diagnosis",
        )

    return (
        "I can give a cited general explanation, but I need more personal facts before assessing your case.",
        ["ask_missing_questions", "save_case"],
        None,
    )
