from __future__ import annotations


def detect_intent(message: str, mode: str = "chat") -> str:
    text = message.lower()
    if mode != "chat":
        return mode
    if any(word in text for word in ("deadline", "time limit", "acas", "day a", "day b")):
        return "deadline"
    if any(word in text for word in ("compensation", "worth", "value", "award", "loss")):
        return "value"
    if any(word in text for word in ("document", "letter", "schedule", "particulars", "et1")):
        return "document"
    if any(word in text for word in ("solicitor", "lawyer", "handoff", "refer")):
        return "handoff"
    if any(word in text for word in ("claim", "dismiss", "sacked", "fired", "not paid", "discriminat")):
        return "diagnosis"
    return "general_question"
