"""
Trust scorer for retrieval candidates — Phase 3.
Refactored from Iterlaw trustScorer.ts
"""
from typing import Dict, List, TypedDict, Optional

class TrustScore(TypedDict):
    candidate_id: str
    score: int
    source_type: str
    reason_codes: List[str]

# Canonical scores
# 100: Primary legislation / statutory rules
# 95:  Official ACAS / GOV.UK guidance
# 90:  Official tribunal/case law
# 50:  Draft/AI output (if applicable)
SCORES: Dict[str, int] = {
    "rules":             100,
    "legislation":       100,
    "acas":              95,
    "official_guidance": 95,
    "case_law":          90,
}

DEFAULT_SCORE = 30

def score_authorities(authorities: List[dict], legal_mode: bool = True) -> List[dict]:
    """
    Apply trust scores to retrieval candidates.
    Updates the 'score' field in each authority dict.
    """
    for auth in authorities:
        source_type = auth.get("type", "unknown")
        reason_codes = [f"source_type:{source_type}"]
        
        score = SCORES.get(source_type, DEFAULT_SCORE)
        if source_type not in SCORES:
            reason_codes.append("unknown_source_using_default")
            
        # Optional: apply penalties for stale sources (Phase 4 freshness)
        if auth.get("is_stale"):
            score = max(0, score - 20)
            reason_codes.append("penalty_stale_source")

        auth["trust_score"] = score
        auth["trust_reasons"] = reason_codes
        
    # Sort by trust_score descending
    authorities.sort(key=lambda x: x.get("trust_score", 0), reverse=True)
    return authorities
