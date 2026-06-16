"""
Evidence weight  -  deterministic narrative heuristics.
Refactored from Iterlaw evidence-weight.engine.ts
"""
import re
from typing import List, Literal, TypedDict

class EvidenceWeightAssessment(TypedDict):
    documentary_support: Literal["strong", "moderate", "weak"]
    witness_risk: Literal["low", "medium", "high"]
    notes: List[str]

def assess_evidence_weight(text: str) -> EvidenceWeightAssessment:
    t = text.lower()
    notes = []

    doc: Literal["strong", "moderate", "weak"] = "moderate"
    if bool(re.search(r"\b(no evidence|no emails|no contract|nothing in writing)\b", t, re.IGNORECASE)):
        doc = "weak"
        notes.append("Limited documentary references  -  disclosure strategy will matter.")
    elif bool(re.search(r"\b(email|contract|minutes|letter|pdf|screenshot)\b", t, re.IGNORECASE)):
        doc = "strong"
        notes.append("Some documentary references  -  preserve metadata and chains of custody.")

    witness: Literal["low", "medium", "high"] = "medium"
    if bool(re.search(r"\b(he said|she said|disputed|contradict)\b", t, re.IGNORECASE)):
        witness = "high"
        notes.append("Credibility-heavy dispute  -  witness statements and chronology critical.")

    return {
        "documentary_support": doc,
        "witness_risk": witness,
        "notes": notes,
    }
