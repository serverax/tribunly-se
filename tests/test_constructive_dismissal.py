"""
Constructive dismissal engine tests (order Workflow B).

Proves the deterministic matrix:
  * strict JSON schema (all required keys, no free prose)
  * deterministic delay -> affirmation risk
  * high affirmation risk triggers human review
  * strong express breach + low delay + causation -> high viability
  * fails closed on missing facts / resignation-before-breach
  * statutory citations are DB-verified (ERA 1996 s.95) with source URLs
  * no "guaranteed win" language; legal-boundary notice present

Requires Postgres for the citation lookups.
"""

from __future__ import annotations

import pytest

from backend.domains.employment.constructive_dismissal import assess_constructive_dismissal

_REQUIRED_KEYS = {
    "claim_type", "claim_viability", "breach_type", "repudiatory_acts",
    "affirmation_risk", "causation_established", "evidence_gaps",
    "recommended_action", "grounding_score", "confidence_score",
    "key_weaknesses", "human_review_required", "citations", "legal_boundary", "status",
}


def _db_available() -> bool:
    try:
        from ingestion.db import get_connection
        c = get_connection(); c.close(); return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres not reachable")


def _strong_facts():
    return {
        "repudiatory_acts": [
            {"date": "2026-03-01", "event": "Unilateral 20% pay cut", "breach_kind": "express"},
            {"date": "2026-03-20", "event": "Failure to address grievance", "breach_kind": "implied_mtc"},
        ],
        "resignation_date": "2026-03-24",
        "pursuing_grievance": True,
        "resignation_letter_cites_breach": True,
    }


def test_schema_complete_and_json_only():
    r = assess_constructive_dismissal(_strong_facts())
    assert _REQUIRED_KEYS.issubset(r.keys())
    # strict structured types  -  no free prose blob
    assert isinstance(r["repudiatory_acts"], list)
    assert isinstance(r["affirmation_risk"], dict)
    assert set(r["affirmation_risk"].keys()) == {"delay_days", "risk_level", "mitigation"}


def test_strong_case_is_high_viability_and_draft_action():
    r = assess_constructive_dismissal(_strong_facts())
    assert r["status"] == "ok"
    assert r["claim_viability"] == "high"
    assert r["breach_type"] == "both"
    assert r["affirmation_risk"]["risk_level"] == "low"     # 4-day delay
    assert r["affirmation_risk"]["delay_days"] == 4
    assert r["causation_established"] is True
    assert r["recommended_action"] == "draft_et1_particulars"
    # last straw is the most recent act
    last = [a for a in r["repudiatory_acts"] if a["weight"] == "last_straw"]
    assert len(last) == 1 and last[0]["date"] == "2026-03-20"


def test_high_affirmation_delay_triggers_human_review():
    facts = _strong_facts()
    facts["resignation_date"] = "2026-06-01"   # ~73 days after last act
    facts["pursuing_grievance"] = False
    r = assess_constructive_dismissal(facts)
    assert r["affirmation_risk"]["risk_level"] == "high"
    assert r["claim_viability"] == "low"
    assert r["human_review_required"] is True
    assert r["recommended_action"] == "human_review"


def test_citations_are_db_verified_with_urls():
    r = assess_constructive_dismissal(_strong_facts())
    sects = {c["section_ref"] for c in r["citations"]}
    assert "95" in sects, "ERA 1996 s.95 (constructive dismissal) must be cited"
    assert all(c.get("url", "").startswith("http") for c in r["citations"])


def test_fail_closed_on_missing_facts():
    r = assess_constructive_dismissal({})  # no acts, no resignation
    assert r["status"] == "fail_closed"
    assert r["claim_viability"] == "zero"
    assert r["human_review_required"] is True
    assert "repudiatory_acts" in r["evidence_gaps"]


def test_fail_closed_resignation_before_breach():
    facts = _strong_facts()
    facts["resignation_date"] = "2026-01-01"  # before the acts
    r = assess_constructive_dismissal(facts)
    assert r["status"] == "fail_closed"
    assert r["reason"] == "resignation_before_breach"


def test_no_guaranteed_win_language_and_boundary_present():
    r = assess_constructive_dismissal(_strong_facts())
    blob = (str(r["key_weaknesses"]) + r["legal_boundary"]).lower()
    assert "not legal advice" in r["legal_boundary"].lower()
    assert "guarantee" in r["legal_boundary"].lower()  # explicitly disclaims guarantee
    for banned in ["guaranteed win", "you will win", "certain to win"]:
        assert banned not in blob
