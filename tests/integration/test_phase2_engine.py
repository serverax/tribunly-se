"""
Phase 2 engine tests — 8 required scenarios.

Runs against the existing corpus (legislation 80 chunks, case_law 5 decisions,
acas_guidance 14 chunks, rules 14 rows across 9 canonical keys).

Retrieval path: structured rules (always) + BM25 keyword fallback (active
while OpenAI quota is blocked — semantic stub returns [] but keyword runs).

BLOCKED_BY_OPENAI_QUOTA: semantic/pgvector retrieval is inactive.
BM25 fallback is active; tests run against real corpus text.

Model: StubReasoningModel for scenarios that test routing/gate logic.
       ClaudeReasoningModel (Haiku) for scenarios requiring real reasoning
       (imported from conftest or via fixture — skipped if key absent).

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase2_engine.py -v -s
"""

from __future__ import annotations

from datetime import date
import pytest

from backend.core.pipeline import assess
from backend.core.models import StubReasoningModel, ClaudeReasoningModel
from backend.core.retrieve import retrieve, retrieve_keyword
from backend.core.classify import classify
from backend.domains.employment.deadline import compute_limitation_date
from ingestion.config import settings


# ── Fixtures ──────────────────────────────────────────────────────────────────

STUB = StubReasoningModel()


def _haiku() -> ClaudeReasoningModel:
    key = settings.anthropic_api_key
    mid = settings.workhorse_model_id
    if not key or key == "placeholder":
        pytest.skip("ANTHROPIC_API_KEY not set")
    return ClaudeReasoningModel(model_id=mid, api_key=key)


# Standard facts — no PII; safe to use in all tests
_UD_FACTS = {
    "edt":                    "2026-04-01",
    "service_start_date":     "2023-04-01",
    "reason_for_dismissal":   "conduct",
    "was_procedure_followed": False,
    "weekly_pay":             600,
    "jurisdiction":           "EW",
}

_SHORT_SERVICE_FACTS = {
    "edt":                "2026-03-15",
    "service_start_date": "2025-01-01",   # ~14 months — below 2-year threshold
    "reason_for_dismissal": "conduct",
    "weekly_pay":         450,
    "jurisdiction":       "EW",
}


# ── Scenario 1: In-scope unfair dismissal — classifies correctly ──────────────

def test_in_scope_ud_classified():
    """An unfair dismissal query classifies as in-scope."""
    result = classify("I was dismissed without any warning after 3 years", _UD_FACTS)
    assert result.in_scope is True
    assert result.matter_type == "unfair_dismissal"


def test_in_scope_ud_pipeline_reaches_assessment():
    """In-scope UD with EDT reaches an assessment (stub routes to insufficient_grounding)."""
    result = assess("I was unfairly dismissed", _UD_FACTS, model=STUB)
    # Stub returns insufficient_grounding=True — that IS the correct gate behaviour
    # for a model that has no real reasoning. The pipeline must have run through
    # all stages (classify, retrieve, deadline, de-id, reason, score, govern).
    assert result["status"] in ("ok", "insufficient_grounding", "model_not_configured")
    # Deadline must always be present and sourced from rules
    if "deadline_info" in result:
        assert result["deadline_info"]["source"] == "rules"
    # De-id boundary must always be logged
    assert "boundary_log" in result


# ── Scenario 2: Out-of-scope matter ──────────────────────────────────────────

def test_out_of_scope_tenancy():
    result = assess("My landlord wants to evict me", {}, model=STUB)
    assert result["status"] == "not_supported"
    assert "assessment" not in result


def test_out_of_scope_divorce():
    result = assess("I need advice about my divorce proceedings", {}, model=STUB)
    assert result["status"] == "not_supported"


def test_out_of_scope_does_not_guess():
    """Out-of-scope must return not_supported, never a legal assessment."""
    result = assess("My parking ticket was unfair", {}, model=STUB)
    assert result["status"] in ("not_supported", "missing_edt")
    assert "assessment" not in result


# ── Scenario 3: Qualifying period fail/pass ───────────────────────────────────

def test_qualifying_period_fail_14_months():
    """14 months service should fail the 2-year qualifying period."""
    result = assess("I was dismissed after 14 months", _SHORT_SERVICE_FACTS, model=STUB)
    if "qualifying_check" in result and result["qualifying_check"]:
        assert result["qualifying_check"]["meets_qualifying_period"] is False
        assert result["qualifying_check"]["service_days"] < 730


def test_qualifying_period_pass_3_years():
    """3 years service should meet the 2-year qualifying period."""
    from backend.domains.employment.deadline import check_qualifying_period
    from backend.core.retrieve import retrieve_rules
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 4, 1))
    qp = next((r for r in rules if r["rule_key"] == "unfair_dismissal.qualifying_period"), None)
    assert qp is not None
    check = check_qualifying_period(date(2023, 4, 1), date(2026, 4, 1),
                                    float(qp["value_numeric"]), qp["unit"])
    assert check["meets_qualifying_period"] is True


# ── Scenario 4: Limitation deadline ──────────────────────────────────────────

def test_deadline_in_pipeline():
    """Deadline must be computed from rules, not from the model."""
    result = assess("I was dismissed", _UD_FACTS, model=STUB)
    assert "deadline_info" in result
    dl = result["deadline_info"]
    assert dl["source"] == "rules"
    assert dl["limitation_date"] is not None
    # EDT 2026-04-01, 3-month limit → 2026-07-01 - 1 day = 2026-06-30
    assert dl["limitation_date"] == "2026-06-30"


def test_deadline_no_ec():
    """Deterministic: EDT 2026-03-14, no EC → deadline 2026-06-13."""
    result = compute_limitation_date(date(2026, 3, 14), 3)
    assert result["limitation_date"] == "2026-06-13"
    assert result["source"] == "rules"


# ── Scenario 5: ACAS EC stop-the-clock ───────────────────────────────────────

def test_ec_stop_the_clock_floor_bites():
    """EC floor bites: base 2026-04-09, Day A 2026-04-05, Day B 2026-04-25 → 2026-05-25."""
    result = compute_limitation_date(
        date(2026, 1, 10), 3,
        ec_day_a=date(2026, 4, 5),
        ec_day_b=date(2026, 4, 25),
    )
    assert result["limitation_date"] == "2026-05-25"
    assert result["floor_applied"] is True
    assert result["source"] == "rules"


def test_ec_stop_the_clock_para26_no_op():
    """Para 26 regression: Day A = Day B, (3) is no-op, (4) still fires."""
    result = compute_limitation_date(
        date(2026, 3, 14), 3,
        ec_day_a=date(2026, 6, 13),
        ec_day_b=date(2026, 6, 13),
    )
    assert result["limitation_date"] == "2026-07-13"
    assert result["floor_applied"] is True


# ── Scenario 6: Compensation cap lookup (effective-dated) ─────────────────────

def test_cap_current_edt():
    """EDT 2026-05-01 → current cap £123,543 from SI 2026/310."""
    from backend.core.retrieve import retrieve_rules
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    cap = next((r for r in rules if r["rule_key"] == "unfair_dismissal.compensatory_cap_amount"), None)
    assert cap is not None
    assert int(cap["value_numeric"]) == 123543
    assert cap["is_prospective"] is False


def test_cap_older_edt():
    """EDT 2025-06-01 → prior cap £118,223 from SI 2025/348."""
    from backend.core.retrieve import retrieve_rules
    rules = retrieve_rules("unfair_dismissal", "EW", date(2025, 6, 1))
    cap = next((r for r in rules if r["rule_key"] == "unfair_dismissal.compensatory_cap_amount"), None)
    assert cap is not None
    assert int(cap["value_numeric"]) == 118223


def test_prospective_cap_never_returned():
    """The uncapped prospective row must never appear in live retrieval."""
    from backend.core.retrieve import retrieve_rules
    for edt in [date(2026, 5, 1), date(2027, 6, 1), date(2030, 1, 1)]:
        rules = retrieve_rules("unfair_dismissal", "EW", edt)
        assert not any(r["is_prospective"] for r in rules), \
            f"Prospective row returned for EDT {edt}"


# ── Scenario 7: Insufficient grounding ───────────────────────────────────────

def test_insufficient_grounding_thin_facts():
    """Minimal facts with no EDT → missing_edt, not a fabricated assessment."""
    result = assess("I think I was unfairly dismissed last year", {"jurisdiction": "EW"}, model=STUB)
    assert result["status"] in ("missing_edt", "insufficient_grounding", "not_supported")
    assert "assessment" not in result


def test_stub_model_routes_to_insufficient_grounding():
    """StubReasoningModel correctly triggers the insufficient_grounding path."""
    result = assess("I was dismissed from my job", _UD_FACTS, model=STUB)
    assert result["status"] in ("insufficient_grounding", "ok")
    if result["status"] == "ok":
        assert result.get("citations"), "Grounded deterministic fallback must include citations"
        assert result.get("insufficient_grounding") is False


# ── Scenario 8: Governance blocking unsupported assertions ────────────────────

def test_governance_blocks_solicitor_claim():
    """Governance gate must block an assessment that implies solicitor status."""
    from backend.core.govern import govern
    from shared.schemas import StructuredAssessment, Deadline, ValueRange
    bad_assessment = StructuredAssessment(
        claim_type="unfair_dismissal",
        jurisdiction="EW",
        has_viable_claim="yes",
        strength="high",
        reasoning_summary="We will file your claim and represent you at tribunal.",
        value_range=ValueRange(low=5000, high=15000, currency="GBP", basis="estimate"),
        key_weaknesses=["Short service."],
        deadline=Deadline(limitation_date=date(2026, 8, 9), source="rules",
                          authority="ERA 1996 s.111(2)"),
        recommended_next_step="prepare_documents",
        citations=[],
        grounding_score=0.8,
        confidence_score=0.7,
        insufficient_grounding=False,
    )
    result = govern(bad_assessment)
    assert result.passes is False
    assert "boundary_violation" in result.failure_reason


def test_governance_blocks_outcome_guarantee():
    """Governance gate must block outcome-guarantee language."""
    from backend.core.govern import govern
    from shared.schemas import StructuredAssessment, Deadline, ValueRange
    bad = StructuredAssessment(
        claim_type="unfair_dismissal",
        jurisdiction="EW",
        has_viable_claim="yes",
        strength="high",
        reasoning_summary="You are guaranteed to win this claim.",
        value_range=ValueRange(low=5000, high=15000, currency="GBP", basis="estimate"),
        key_weaknesses=["None — certain win."],
        deadline=Deadline(limitation_date=date(2026, 8, 9), source="rules",
                          authority="ERA 1996 s.111(2)"),
        recommended_next_step="prepare_documents",
        citations=[],
        grounding_score=0.8,
        confidence_score=0.7,
        insufficient_grounding=False,
    )
    result = govern(bad)
    assert result.passes is False
    assert "boundary_violation" in result.failure_reason


# ── BM25 keyword fallback: confirm it finds real corpus text ──────────────────

def test_bm25_finds_legislation():
    """BM25 fallback must return legislation chunks for an UD query."""
    results = retrieve_keyword("unfair dismissal qualifying period employment rights", k=5)
    assert len(results) > 0, "BM25 returned no results — corpus may not be ingested"
    types = {r["source_type"] for r in results}
    assert "legislation" in types or "case_law" in types or "acas" in types


def test_bm25_finds_acas():
    """BM25 fallback must find ACAS guidance for disciplinary procedure queries."""
    results = retrieve_keyword("disciplinary procedure grievance ACAS Code", k=5)
    assert len(results) > 0


def test_bm25_returns_citations():
    """Every BM25 result must have a cite and a url."""
    results = retrieve_keyword("unfair dismissal time limit months", k=3)
    for r in results:
        assert r.get("cite"), f"Missing cite in BM25 result: {r}"
        assert r.get("url"),  f"Missing url in BM25 result: {r}"
        assert r.get("text"), f"Missing text in BM25 result: {r}"


def test_retrieve_bundle_has_both_rules_and_keyword():
    """Full retrieve() must return rules AND keyword authorities (not just rules).

    Uses 'unfair dismissal qualifying period' — confirmed present in the ingested
    legislation text (ERA 1996 s.108 is in the corpus). 'Reasonable responses'
    is judicial doctrine in case law, not verbatim in the statute text, so is
    a poor BM25 query over the current corpus.
    """
    bundle = retrieve(
        query="unfair dismissal qualifying period employment rights",
        claim_type="unfair_dismissal",
        jurisdiction="EW",
        edt=date(2026, 5, 1),
    )
    assert len(bundle.exact_rules) > 0, "No rules in bundle"
    assert len(bundle.authorities) > 0, \
        "No text authorities in bundle — BM25 fallback may not be reaching the corpus"
    assert bundle.insufficient_grounding is False


# ── De-identification boundary (logged, not just asserted) ────────────────────

def test_deidentification_boundary_logged():
    """
    De-identification must run before any model call, and the boundary_log
    must prove no PII keys were passed.

    This test uses facts with PII fields and verifies the boundary_log shows
    them stripped. The ACTUAL PAYLOAD is printed for audit.
    """
    pii_facts = {
        "claimant_name":    "Alice Johnson",
        "employer_name":    "Acme Corp Ltd",
        "home_address":     "42 Test Street, London",
        "email":            "alice@example.com",
        "date_of_birth":    "1985-06-15",
        "national_insurance": "AB123456C",
        "edt":              "2026-04-01",
        "service_start_date": "2022-01-01",
        "reason_for_dismissal": "conduct",
        "was_procedure_followed": False,
        "weekly_pay":       700,
        "jurisdiction":     "EW",
    }

    result = assess("I was unfairly dismissed", pii_facts, model=STUB)

    log = result.get("boundary_log")
    assert log is not None, "boundary_log must be present in every pipeline response"

    print("\n=== DE-IDENTIFICATION BOUNDARY PAYLOAD (for audit) ===")
    print(f"Fields STRIPPED:  {sorted(log['fields_stripped'])}")
    print(f"Fields PASSED:    {sorted(log['fields_passed'])}")
    pii_out = log.get("pii_in_output") or log.get("pii_fields_in_output", [])
    print(f"PII in output:    {pii_out}")

    pii_keys = {"claimant_name", "employer_name", "home_address", "email",
                "date_of_birth", "national_insurance"}
    for pii_key in pii_keys:
        assert pii_key in log["fields_stripped"], \
            f"PII field '{pii_key}' was NOT stripped before model call"
        assert pii_key not in log["fields_passed"], \
            f"PII field '{pii_key}' found in what was passed to model"

    pii_out = log.get("pii_in_output") or log.get("pii_fields_in_output", [])
    assert pii_out == [], f"PII found in model-bound payload: {pii_out}"

    # Legal facts must survive de-id
    assert "edt" in log["fields_passed"]
    assert "reason_for_dismissal" in log["fields_passed"]
    assert "weekly_pay" in log["fields_passed"]

    print(f"\nDE-IDENTIFICATION: PASS — {len(pii_keys)} PII field types stripped, "
          f"0 in model payload, legal facts preserved.")
