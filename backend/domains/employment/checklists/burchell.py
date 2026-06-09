"""
Burchell-stage assessment — deterministic scaffold.
Refactored from Iterlaw burchell.engine.ts
"""
import re
from typing import List, Literal, TypedDict

class BurchellAssessment(TypedDict):
    genuine_belief: Literal["likely", "unclear", "weak"]
    reasonable_grounds: Literal["likely", "unclear", "weak"]
    reasonable_investigation: Literal["likely", "unclear", "weak"]
    notes: List[str]

def assess_burchell_from_text(text: str) -> BurchellAssessment:
    t = text.lower()
    notes = []

    no_investigation = bool(re.search(r"\b(no investigation|without investigation|no hearing|no disciplinary|skipped process)\b", t, re.IGNORECASE))
    some_process = bool(re.search(r"\b(investigation|hearing|disciplinary|minutes|meeting|warnings?)\b", t, re.IGNORECASE))

    investigation: Literal["likely", "unclear", "weak"] = "unclear"
    if no_investigation:
        investigation = "weak"
        notes.append("Narrative suggests absent or minimal investigation — Burchell 'reasonable investigation' harder for employer.")
    elif some_process:
        investigation = "likely"
        notes.append("Some procedural steps referenced — investigation quality still fact-specific.")
    else:
        notes.append("Investigation quality not clearly evidenced in free text.")

    vague_allegation = bool(re.search(r"\b(no evidence|unclear evidence|vague)\b", t, re.IGNORECASE))
    grounds: Literal["likely", "unclear", "weak"] = "weak" if vague_allegation else "unclear"
    if vague_allegation:
        notes.append("Weak or unclear factual basis may undermine reasonable grounds for belief.")

    belief: Literal["likely", "unclear", "weak"] = "weak" if (no_investigation and vague_allegation) else "unclear"

    return {
        "genuine_belief": belief,
        "reasonable_grounds": grounds,
        "reasonable_investigation": investigation,
        "notes": notes,
    }
