"""
ACAS Code compliance  -  checklist-style deterministic scaffold.
Refactored from Iterlaw acas-code.engine.ts
"""
import re
from typing import List, Literal, TypedDict

class AcasComplianceAssessment(TypedDict):
    aligned_with_code: Literal["likely", "unclear", "unlikely"]
    procedural_gaps: List[str]

def assess_acas_code(text: str) -> AcasComplianceAssessment:
    t = text.lower()
    gaps = []

    if bool(re.search(r"\b(no hearing|no meeting|no warning|instant dismissal|summary dismissal)\b", t, re.IGNORECASE)):
        gaps.append("Potential failure to follow fair procedure / investigation before sanction.")
    
    if bool(re.search(r"\b(no right of appeal|no appeal)\b", t, re.IGNORECASE)):
        gaps.append("Appeal stage not evidenced  -  Code expects reasonable appeal where practicable.")

    unlikely = len(gaps) >= 2
    likely = len(gaps) == 0 and bool(re.search(r"\b(hearing|investigation|grievance|appeal)\b", t, re.IGNORECASE))

    return {
        "aligned_with_code": "unlikely" if unlikely else "likely" if likely else "unclear",
        "procedural_gaps": gaps,
    }
