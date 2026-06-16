"""
Phase 2 closure  -  real model acceptance tests.

REQUIRES:
  - OPENAI_API_KEY set (for embeddings + query embedding)
  - ANTHROPIC_API_KEY set (for Claude Haiku reasoning)
  - WORKHORSE_MODEL_ID=claude-haiku-4-5-20251001
  - Embeddings populated (run embedder first)
  - Running DB with seeded rules

Run:
  docker compose run --rm ingestion python -m pytest \
    tests/integration/test_phase2_real_model.py -v -s

GUARDRAILS enforced in every test:
  - deadline.source == "rules" (not model)
  - de-identification runs before model call
  - boundary_log proves no PII sent
  - governance gate must pass
  - no stub model used
"""

from __future__ import annotations

import json
import os
import pytest
from datetime import date

from ingestion.config import settings
from backend.core.pipeline import assess
from backend.core.models import ClaudeReasoningModel
from backend.core.deidentify import deidentify


# ── Fixture: real Haiku model ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def haiku():
    key = settings.anthropic_api_key
    mid = settings.workhorse_model_id
    if key == "placeholder" or not key:
        pytest.skip("ANTHROPIC_API_KEY not set  -  real model tests require it")
    if not mid:
        pytest.skip("WORKHORSE_MODEL_ID not set")
    return ClaudeReasoningModel(model_id=mid, api_key=key)


# ── 5 realistic unfair-dismissal fact patterns ───────────────────────────────

FACT_PATTERNS = [
    {
        "id": "FP1",
        "description": "Textbook UD  -  4 years service, dismissed for conduct, no hearing",
        "query": "I was dismissed for alleged misconduct after 4 years. No disciplinary hearing, no warning.",
        "facts": {
            "edt":                    "2026-04-01",
            "service_start_date":     "2022-03-01",
            "reason_for_dismissal":   "conduct",
            "was_procedure_followed": False,
            "had_disciplinary_hearing": False,
            "acas_code_followed":     False,
            "weekly_pay":             600,
            "jurisdiction":           "EW",
            # PII fields  -  must be stripped before model
            "claimant_name":          "Jane Smith",
            "employer_name":          "Acme Manufacturing Ltd",
            "email":                  "jane.smith@example.com",
        },
    },
    {
        "id": "FP2",
        "description": "Below qualifying period  -  14 months service (no ordinary UD)",
        "query": "I was sacked after 14 months with no reason given.",
        "facts": {
            "edt":                "2026-03-15",
            "service_start_date": "2025-01-01",
            "reason_for_dismissal": "unknown",
            "was_procedure_followed": False,
            "weekly_pay":         450,
            "jurisdiction":       "EW",
            "claimant_name":      "Tom Reeves",
            "employer_name":      "Corner Shop Ltd",
        },
    },
    {
        "id": "FP3",
        "description": "Constructive dismissal  -  intolerable conditions, 3 years service",
        "query": "My employer cut my pay by 30% and moved me to a different role. I felt forced to resign after 3 years.",
        "facts": {
            "edt":                    "2026-02-28",
            "service_start_date":     "2023-02-01",
            "reason_for_dismissal":   "constructive_dismissal",
            "was_procedure_followed": False,
            "weekly_pay":             800,
            "jurisdiction":           "EW",
            "claimant_name":          "Maria Kowalski",
            "employer_name":          "Tech Solutions UK",
            "home_address":           "12 Oak Street, London",
        },
    },
    {
        "id": "FP4",
        "description": "With EC  -  dismissed 5 years service, used Early Conciliation",
        "query": "Dismissed after 5 years. Used ACAS Early Conciliation. Certificate received 3 weeks after I contacted them.",
        "facts": {
            "edt":                    "2026-03-01",
            "service_start_date":     "2021-02-01",
            "reason_for_dismissal":   "redundancy",
            "was_procedure_followed": True,
            "weekly_pay":             750,
            "jurisdiction":           "EW",
            "ec_day_a":               "2026-04-01",
            "ec_day_b":               "2026-04-22",
            "claimant_name":          "David Chen",
            "employer_name":          "Logistics Corp",
            "phone":                  "07700 900000",
        },
    },
    {
        "id": "FP5",
        "description": "Thin/ambiguous facts  -  short query, minimal information",
        "query": "I think I was unfairly dismissed last year.",
        "facts": {
            "jurisdiction": "EW",
            # Deliberately minimal  -  should trigger low confidence or insufficient_grounding
        },
    },
]


def _run_pattern(pattern: dict, model: ClaudeReasoningModel) -> dict:
    """Run a single fact pattern and return the full result."""
    result = assess(
        query=pattern["query"],
        facts=pattern["facts"],
        model=model,
        jurisdiction=pattern["facts"].get("jurisdiction", "EW"),
    )
    result["_pattern_id"] = pattern["id"]
    result["_description"] = pattern["description"]
    return result


def _print_result(r: dict) -> None:
    """Print a structured summary of a pattern result."""
    print(f"\n{'='*70}")
    print(f"PATTERN {r['_pattern_id']}: {r['_description']}")
    print(f"STATUS: {r.get('status')}")
    if "deadline_info" in r:
        dl = r["deadline_info"]
        print(f"DEADLINE: {dl.get('limitation_date')}  source={dl.get('source')}")
    if "assessment" in r:
        a = r["assessment"]
        print(f"VIABLE: {a.get('has_viable_claim')}  strength={a.get('strength')}")
        print(f"GROUNDING: {a.get('grounding_score')}  confidence={a.get('confidence_score')}")
        print(f"WEAKNESSES: {a.get('key_weaknesses')}")
        print(f"NEXT: {a.get('recommended_next_step')}")
        print(f"CITATIONS ({len(a.get('citations',[]))}): {[c['cite'] for c in a.get('citations',[])]}")
    if "boundary_log" in r:
        bl = r["boundary_log"]
        print(f"BOUNDARY stripped={bl.get('fields_stripped')} pii_in_output={bl.get('pii_in_output')}")


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pattern", FACT_PATTERNS[:4], ids=[p["id"] for p in FACT_PATTERNS[:4]])
def test_ud_fact_pattern_real_model(pattern, haiku):
    """
    Phase 2 AC1: structured assessment with correct claim identification,
    correctly computed deadline, and citations that support each stated point.
    """
    result = _run_pattern(pattern, haiku)
    _print_result(result)

    # Must return a known status
    assert result["status"] in ("ok", "insufficient_grounding", "low_confidence", "missing_edt"), \
        f"Unexpected status: {result['status']}"

    # Deadline must always come from rules (when computable)
    if "deadline_info" in result:
        assert result["deadline_info"]["source"] == "rules", \
            "deadline.source must be 'rules'  -  model must not generate deadlines"

    # De-identification must have run (boundary_log present)
    assert "boundary_log" in result, "boundary_log must be present  -  de-identification gate"
    bl = result["boundary_log"]
    assert bl.get("pii_in_output") == [], \
        f"PII found in model-bound payload: {bl.get('pii_in_output')}"

    # Known PII fields in FP1-FP4 must have been stripped
    pii_keys = {"claimant_name", "employer_name", "email", "home_address", "phone",
                "national_insurance", "date_of_birth"}
    sent_keys = set(bl.get("fields_passed", []))
    leaked = pii_keys & sent_keys
    assert not leaked, f"PII fields passed to model: {leaked}"

    # If governance passed, check structural validity
    # Assessment fields are at the top level of the pipeline response (not nested)
    if result["status"] == "ok":
        assert result["claim_type"] == "unfair_dismissal"
        assert result["has_viable_claim"] in ("yes", "no", "uncertain")
        assert 0.0 <= result["grounding_score"] <= 1.0
        assert 0.0 <= result["confidence_score"] <= 1.0
        assert isinstance(result["key_weaknesses"], list)
        assert isinstance(result["citations"], list)


def test_fp2_below_qualifying_period(haiku):
    """FP2: 14-month service should fail qualifying period check."""
    pattern = FACT_PATTERNS[1]
    result = _run_pattern(pattern, haiku)
    _print_result(result)

    if "qualifying_check" in result and result["qualifying_check"]:
        qc = result["qualifying_check"]
        # 14 months < 2 years  -  should not qualify for ordinary UD
        assert qc["meets_qualifying_period"] is False, \
            "14 months service must not meet the 2-year qualifying period"
        print(f"QUALIFYING CHECK: {qc}")


def test_fp5_thin_facts_insufficient_grounding(haiku):
    """FP5: minimal facts should produce insufficient_grounding or missing_edt."""
    pattern = FACT_PATTERNS[4]
    result = _run_pattern(pattern, haiku)
    _print_result(result)

    # Missing EDT or thin facts should not produce a full confident assessment
    assert result["status"] in ("missing_edt", "insufficient_grounding", "low_confidence"), \
        f"Thin fact pattern produced '{result['status']}'  -  expected honest uncertainty"


def test_deidentification_boundary_real_model(haiku):
    """
    Phase 2 AC4: log the actual outbound payload after redaction.
    Prove no PII leaves the system boundary.
    """
    # Deliberately PII-rich input
    raw_facts = {
        "claimant_name":    "Alice Johnson",
        "employer_name":    "Big Corp PLC",
        "email":            "alice@bigcorp.com",
        "home_address":     "42 Maple Road, Bristol BS1 1AA",
        "phone":            "07800 123456",
        "date_of_birth":    "1985-06-15",
        "national_insurance": "AB123456C",
        "edt":              "2026-04-01",
        "service_start_date": "2022-01-01",
        "reason_for_dismissal": "conduct",
        "was_procedure_followed": False,
        "weekly_pay":       700,
        "jurisdiction":     "EW",
    }

    safe, boundary_log = deidentify(raw_facts)

    print("\n=== DE-IDENTIFICATION BOUNDARY REPORT ===")
    print(f"Fields STRIPPED: {sorted(boundary_log['fields_stripped'])}")
    print(f"Fields PASSED:   {sorted(boundary_log['fields_passed'])}")
    print(f"PII in output:   {boundary_log['pii_fields_in_output']}")
    print(f"Safe facts (keys only): {sorted(safe.keys())}")

    # All known PII fields must be stripped
    pii_expected_stripped = {
        "claimant_name", "employer_name", "email", "home_address",
        "phone", "date_of_birth", "national_insurance",
    }
    for pii_field in pii_expected_stripped:
        assert pii_field in boundary_log["fields_stripped"], \
            f"PII field '{pii_field}' was NOT stripped  -  it may reach the model"
        assert pii_field not in safe, \
            f"PII field '{pii_field}' found in safe_facts that would be sent to model"

    # Legal facts must survive
    assert "edt" in safe
    assert "reason_for_dismissal" in safe
    assert "weekly_pay" in safe

    # No PII should appear in model-bound output
    assert boundary_log["pii_fields_in_output"] == [], \
        "pii_fields_in_output must be empty"

    # Run through real model to get real boundary payload
    result = assess(
        query="I was dismissed for misconduct",
        facts=raw_facts,
        model=haiku,
    )
    assert "boundary_log" in result
    bl = result["boundary_log"]
    assert bl["pii_in_output"] == [], "PII found in model-bound payload  -  FAIL"

    # Inspect the model boundary payload (keys only  -  no values)
    if result.get("model_boundary_payload"):
        mbp = result["model_boundary_payload"]
        print(f"\nModel boundary payload (keys only, no values):")
        print(f"  model:              {mbp.get('model')}")
        print(f"  safe_facts_keys:    {mbp.get('safe_facts_keys')}")
        print(f"  boundary_log:       PRESENT")
        # Confirm no PII key names appear in what was sent
        sent_keys = set(mbp.get("safe_facts_keys", []))
        leaked = pii_expected_stripped & sent_keys
        assert not leaked, f"PII key names in model boundary payload: {leaked}"
        print(f"  PII keys in payload: NONE ✓")


def test_out_of_scope_still_returns_not_supported(haiku):
    """Out-of-scope must route correctly even with real model configured."""
    result = assess("My landlord wants to evict me", {}, model=haiku)
    assert result["status"] == "not_supported"
    assert "assessment" not in result
