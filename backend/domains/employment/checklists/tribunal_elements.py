"""
Tribunal-level legal reasoning elements — deterministic scaffolds.
Refactored from Iterlaw tribunal-tests/*.ts
"""
from typing import Dict, List

ELEMENTS: Dict[str, List[str]] = {
    "unfair-dismissal": [
        "Qualifying service (usually two years) unless automatic unfair dismissal",
        "Potentially fair reason under s.98(1)–(2) ERA 1996",
        "Reasonableness of dismissal under s.98(4) including equity and substantial merits",
        "Procedural fairness and consistency with ACAS Code where applicable",
        "Reasonable investigation where misconduct alleged (Burchell principles)",
        "Sanction within band of reasonable responses",
    ],
    "discrimination": [
        "Protected characteristic",
        "Prohibited conduct (direct / indirect / harassment / victimisation as applicable)",
        "Comparator or pool where legally required",
        "Causation and less favourable / disparate impact analysis",
        "Employer justification for indirect discrimination (legitimate aim / proportionality)",
    ],
    "wages": [
        "Wages properly payable on the relevant occasion",
        "Deduction not authorised by statute or contract / consent",
        "Amount unlawfully deducted",
        "Time limits for complaint",
    ],
    "redundancy": [
        "Genuine redundancy situation",
        "Fair selection pool and criteria",
        "Consultation (individual and collective where triggered)",
        "Suitable alternative employment consideration",
        "Redundancy pay calculation and rebate where applicable",
    ],
}

TEST_IDS: Dict[str, str] = {
    "unfair-dismissal": "unfair-dismissal-era-1996",
    "discrimination": "discrimination-eqa-2010",
    "wages": "wages-era-1996",
    "redundancy": "redundancy-era-1996",
}

def get_elements_for_claim(claim_family: str) -> List[str]:
    return ELEMENTS.get(claim_family, ["Jurisdiction", "Merits", "Remedy", "Time limits"])

def get_test_id(claim_family: str) -> str:
    return TEST_IDS.get(claim_family, "generic-tribunal-test")
