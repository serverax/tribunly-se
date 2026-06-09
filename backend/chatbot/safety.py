from __future__ import annotations


_BANNED_PHRASES = (
    "you will win",
    "guaranteed",
    "we will file your claim",
    "lawapp will represent you",
)


def govern_answer(answer: str, citations: list[dict], grounding_score: float, confidence_score: float) -> dict:
    failures: list[str] = []
    lower = answer.lower()
    for phrase in _BANNED_PHRASES:
        if phrase in lower:
            failures.append(f"banned_phrase:{phrase}")
    if not citations:
        failures.append("missing_citations")
    if grounding_score < 0.5:
        failures.append("weak_grounding")
    if confidence_score < 0.5:
        failures.append("low_confidence")
    return {
        "pass": not failures,
        "failures": failures,
        "grounding_score": grounding_score,
        "confidence_score": confidence_score,
    }
