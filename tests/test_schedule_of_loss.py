"""
Schedule of Loss generator tests (order Workflow D).

Proves the deterministic, template-anchored Schedule of Loss:
  * carries the self-help / not-legal-advice boundary notice
  * references the statutory basis (ERA 1996, s.119 basic award)
  * does NOT hardcode statutory monetary values (caps come from rules via the
    assessment value_range, not baked into the document text)
  * renders citations sourced from the assessment (with official URLs)
  * different assessment citations produce different output (figures/citations
    are sourced, not fixed)
"""

from __future__ import annotations

from backend.core.documents import generate_schedule_of_loss

_FACTS = {"edt": "2026-05-10", "service_start_date": "2020-01-01", "weekly_pay": 700}


def test_sol_has_self_help_boundary_notice():
    doc = generate_schedule_of_loss({"claim_type": "unfair_dismissal", "status": "ok"}, _FACTS)
    low = doc.lower()
    assert "not legal advice" in low
    assert ("self-help" in low) or ("does not file" in low) or ("not a solicitor" in low)


def test_sol_references_statutory_basis():
    doc = generate_schedule_of_loss({"status": "ok"}, _FACTS)
    assert "ERA 1996" in doc
    assert "s.119" in doc  # basic award statutory basis


def test_sol_does_not_hardcode_statutory_amounts():
    # Statutory caps (£719/£751 weekly cap, £118,223/£123,543 comp cap, £9,157
    # min award) must come from the rules table via the assessment value_range,
    # never baked into the document template.
    doc = generate_schedule_of_loss({"status": "ok"}, _FACTS)
    for amount in ["719", "751", "118223", "123543", "9157"]:
        assert amount not in doc, f"hardcoded statutory value {amount} found in SoL template"


def test_sol_renders_assessment_citations_with_urls():
    assessment = {
        "status": "ok",
        "citations": [
            {"cite": "ERA 1996 s.123",
             "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/123"}
        ],
    }
    doc = generate_schedule_of_loss(assessment, _FACTS)
    assert "ERA 1996 s.123" in doc
    assert "legislation.gov.uk" in doc


def test_sol_citations_are_sourced_not_fixed():
    a1 = {"status": "ok", "citations": [{"cite": "ERA 1996 s.119", "url": "u1"}]}
    a2 = {"status": "ok", "citations": [{"cite": "ERA 1996 s.123", "url": "u2"}]}
    d1 = generate_schedule_of_loss(a1, _FACTS)
    d2 = generate_schedule_of_loss(a2, _FACTS)
    assert d1 != d2
    assert "s.119" in d1 and "s.123" in d2
