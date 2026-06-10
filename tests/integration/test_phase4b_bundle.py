"""
Phase 4B — Premium tribunal bundle integration tests.

Tests:
  Bundle preview:
   1.  Preview endpoint returns all four component previews
   2.  Preview always requires payment_required=True (no token needed to preview)
   3.  Preview content is truncated (shorter than full)

  Premium access gate:
   4.  Full bundle without paid case state → payment_required=True, content truncated
   5.  Full bundle with DB-backed paid case state → payment_required=False, full content

  Component content:
   6.  Witness statement generated with employment dates
   7.  Chronology generated with EDT
   8.  Chronology does NOT invent missing dates (shows placeholder)
   9.  Evidence checklist generated with expected categories
  10.  ET1 support notes generated
  11.  ET1 notes do NOT say "we will file" or "we will submit"

  Confirmed facts:
  12.  Bundle uses confirmed corrected facts (non-placeholder)
  13.  Bundle does NOT use extracted_unconfirmed facts
  14.  Bundle does NOT use rejected facts

  Metadata:
  15.  Bundle metadata saved after premium generate
  16.  GET /cases/{id}/bundle shows generated components

  Safety:
  17.  Legal boundary notice in every component
  18.  No prohibited phrases in any component

  Saved-case integration:
  19.  Saved-case page still loads with bundle section
  20.  GET /cases/{id}/bundle returns 404 for unknown case

  Regressions:
  21.  Phase 4A upload still works
  22.  Phase 3C document generation still works
  23.  Phase 3D consent still enforced
  24.  Static routes still serve
  25.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase4b_bundle.py -v -s
"""

from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.bundle import (
    get_confirmed_facts, generate_witness_statement,
    generate_chronology, generate_et1_support_notes, BUNDLE_COMPONENTS,
)
from backend.core.documents import safety_check
from tests.integration.extraction_helpers import seed_extracted_facts
from tests.integration.payment_helpers import mark_case_paid

client = TestClient(app, raise_server_exceptions=True)

_MOCK_PDF = b"%PDF-1.0\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"

_ASSESSMENT = {
    "status": "ok", "claim_type": "unfair_dismissal", "has_viable_claim": "yes",
    "strength": "medium",
    "reasoning_summary": "3 years service, dismissed for conduct, no procedure followed.",
    "key_weaknesses": ["Employer may argue conduct was serious."],
    "employer_arguments": [],
    "deadline_info": {"limitation_date": "2026-06-30", "source": "rules", "authority": "ERA 1996 s.111(2)", "ec_applied": False},
    "value_range": {"low": 1800, "high": 31200, "currency": "GBP", "basis": "From rules."},
    "recommended_next_step": "prepare_documents",
    "citations": [{"cite": "ERA 1996 s.94", "url": "https://legislation.gov.uk/ukpga/1996/18/section/94"}],
    "grounding_score": 0.85, "confidence_score": 0.75, "insufficient_grounding": False,
    "boundary_log": {"fields_passed": ["edt"], "fields_stripped": [], "pii_in_output": []},
}

_KEY_DATES = {
    "edt": "2026-04-01",
    "deadline_date": "2026-06-30",
    "employment_start_date": "2023-04-01",
}


def _make_case(key_dates=None) -> str:
    resp = client.post("/cases", json={
        "claim_type": "unfair_dismissal", "jurisdiction": "EW",
        "assessment": _ASSESSMENT,
        "key_dates": key_dates or _KEY_DATES,
    })
    assert resp.status_code == 201
    return resp.json()["case_id"]


def _make_paid_case(key_dates=None) -> str:
    case_id = _make_case(key_dates=key_dates)
    mark_case_paid(case_id)
    return case_id


# ── 1-3. Bundle preview ────────────────────────────────────────────────────────

def test_preview_returns_all_four_components():
    case_id = _make_case()
    resp = client.post(f"/cases/{case_id}/bundle/preview")
    assert resp.status_code == 200
    data = resp.json()
    assert "components" in data
    for comp in BUNDLE_COMPONENTS:
        assert comp in data["components"], f"Missing component: {comp}"


def test_preview_payment_required_true():
    case_id = _make_case()
    resp = client.post(f"/cases/{case_id}/bundle/preview")
    assert resp.json()["payment_required"] is True


def test_preview_content_is_truncated():
    case_id = _make_case()
    preview_resp = client.post(f"/cases/{case_id}/bundle/preview")
    mark_case_paid(case_id)
    full_resp    = client.post(f"/cases/{case_id}/bundle/generate", json={})
    preview_ws = preview_resp.json()["components"]["witness_statement"]
    full_ws    = full_resp.json()["components"]["witness_statement"]
    assert len(preview_ws) < len(full_ws), "Preview must be shorter than full document"
    assert "PREVIEW ENDS HERE" in preview_ws or "requires payment" in preview_ws.lower()


# ── 4-5. Premium access gate ──────────────────────────────────────────────────

def test_full_bundle_without_token_returns_payment_required():
    case_id = _make_case()
    resp = client.post(f"/cases/{case_id}/bundle/generate", json={})
    assert resp.status_code == 200
    assert resp.json()["payment_required"] is True


def test_full_bundle_with_paid_case_returns_full_content():
    case_id = _make_paid_case()
    resp = client.post(f"/cases/{case_id}/bundle/generate", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["payment_required"] is False
    for comp in BUNDLE_COMPONENTS:
        assert comp in data["components"]
        assert "PREVIEW ENDS HERE" not in data["components"][comp]


# ── 6-11. Component content ───────────────────────────────────────────────────

def test_witness_statement_contains_employment_dates():
    resp = client.post(f"/cases/{_make_paid_case()}/bundle/generate", json={})
    ws = resp.json()["components"]["witness_statement"]
    assert "April 2026" in ws or "2026-04-01" in ws    # EDT
    assert "2023" in ws                                 # start year


def test_chronology_contains_edt():
    resp = client.post(f"/cases/{_make_paid_case()}/bundle/generate", json={})
    chron = resp.json()["components"]["chronology"]
    assert "April 2026" in chron or "2026-04-01" in chron


def test_chronology_does_not_invent_missing_dates():
    """Missing employment_start_date must show placeholder, not an invented date."""
    case_id = _make_paid_case(key_dates={"edt": "2026-04-01", "deadline_date": "2026-06-30"})
    resp = client.post(f"/cases/{case_id}/bundle/generate", json={})
    chron = resp.json()["components"]["chronology"]
    # Should say NOT CONFIRMED, not invent a date
    assert "NOT CONFIRMED" in chron or "NOT PROVIDED" in chron, \
        "Missing start date must show 'NOT CONFIRMED' placeholder, not an invented date"


def test_evidence_checklist_contains_expected_categories():
    resp = client.post(f"/cases/{_make_paid_case()}/bundle/generate", json={})
    checklist = resp.json()["components"]["evidence_checklist"].lower()
    for term in ["employment contract", "dismissal letter", "payslip", "acas"]:
        assert term in checklist, f"Expected '{term}' in evidence checklist"


def test_et1_support_notes_generated():
    resp = client.post(f"/cases/{_make_paid_case()}/bundle/generate", json={})
    et1 = resp.json()["components"]["et1_support_notes"]
    assert "ET1" in et1 or "et1" in et1.lower()
    assert "Unfair Dismissal" in et1 or "unfair dismissal" in et1.lower()
    assert "2026-06-30" in et1 or "June 2026" in et1   # deadline


def test_et1_notes_do_not_say_we_will_file():
    resp = client.post(f"/cases/{_make_paid_case()}/bundle/generate", json={})
    et1 = resp.json()["components"]["et1_support_notes"].lower()
    assert "we will file" not in et1
    assert "we will submit" not in et1
    assert "we will represent" not in et1


# ── 12-14. Confirmed facts handling ──────────────────────────────────────────

def _make_case_with_confirmed_upload(corrected_edt="2026-03-15") -> tuple[str, str]:
    """Create a case, upload a doc, extract, correct edt_candidate, return (case_id, upload_id)."""
    case_id = _make_case()
    upload_resp = client.post(
        f"/cases/{case_id}/uploads",
        data={"doc_type": "dismissal_letter"},
        files={"file": ("dl.pdf", io.BytesIO(_MOCK_PDF), "application/pdf")},
    )
    upload_id = upload_resp.json()["upload_id"]
    client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")
    seed_extracted_facts(upload_id, {
        "edt_candidate": {"status": "extracted_unconfirmed", "value": "2026-04-01"},
    })
    # Correct edt_candidate to a real date
    client.patch(
        f"/cases/{case_id}/uploads/{upload_id}/facts",
        json={"facts": {"edt_candidate": {"status": "user_corrected", "value": corrected_edt}}},
    )
    mark_case_paid(case_id)
    return case_id, upload_id


def test_bundle_uses_confirmed_corrected_facts():
    """Corrected edt_candidate should appear in confirmed_facts_used."""
    case_id, _ = _make_case_with_confirmed_upload("2026-03-15")
    resp = client.post(f"/cases/{case_id}/bundle/generate", json={})
    data = resp.json()
    assert "edt_candidate" in data["confirmed_facts_used"]


def test_bundle_does_not_use_unconfirmed_facts():
    """Placeholder values from unconfirmed extraction must not appear in bundle."""
    case_id = _make_case()
    # Upload and extract but do NOT confirm (all remain extracted_unconfirmed)
    upload_resp = client.post(
        f"/cases/{case_id}/uploads",
        data={"doc_type": "dismissal_letter"},
        files={"file": ("dl.pdf", io.BytesIO(_MOCK_PDF), "application/pdf")},
    )
    upload_id = upload_resp.json()["upload_id"]
    client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")
    seed_extracted_facts(upload_id, {
        "edt_candidate": {"status": "extracted_unconfirmed", "value": "[Extracted from uploaded document]"},
    })
    # Don't confirm anything

    mark_case_paid(case_id)
    resp = client.post(f"/cases/{case_id}/bundle/generate", json={})
    # Placeholder text must not appear in bundle content
    for comp, content in resp.json()["components"].items():
        assert "[Extracted from" not in content, \
            f"Unconfirmed placeholder found in {comp}"


def test_bundle_does_not_use_rejected_facts():
    """Rejected facts must not appear in bundle or confirmed_facts_used."""
    case_id = _make_case()
    upload_resp = client.post(
        f"/cases/{case_id}/uploads",
        data={"doc_type": "employment_contract"},
        files={"file": ("c.pdf", io.BytesIO(_MOCK_PDF), "application/pdf")},
    )
    upload_id = upload_resp.json()["upload_id"]
    client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")
    seeded_facts = {
        "edt_candidate": {"status": "extracted_unconfirmed", "value": "2026-03-15"},
        "employer_name": {"status": "extracted_unconfirmed", "value": "Example Ltd"},
    }
    seed_extracted_facts(upload_id, seeded_facts)
    facts_to_reject = {field: {"status": "rejected"} for field in seeded_facts}
    client.patch(f"/cases/{case_id}/uploads/{upload_id}/facts", json={"facts": facts_to_reject})

    mark_case_paid(case_id)
    resp = client.post(f"/cases/{case_id}/bundle/generate", json={})
    assert resp.json()["confirmed_facts_used"] == [], \
        "No confirmed facts expected when all rejected"


# ── 15-16. Metadata ───────────────────────────────────────────────────────────

def test_bundle_metadata_saved_after_premium_generate():
    case_id = _make_paid_case()
    client.post(f"/cases/{case_id}/bundle/generate", json={})
    status_resp = client.get(f"/cases/{case_id}/bundle")
    assert status_resp.status_code == 200
    assert status_resp.json()["bundle_generated"] is True


def test_bundle_status_lists_all_components():
    case_id = _make_paid_case()
    client.post(f"/cases/{case_id}/bundle/generate", json={})
    resp = client.get(f"/cases/{case_id}/bundle")
    component_names = [c["component"] for c in resp.json()["bundle_components"]]
    for comp in BUNDLE_COMPONENTS:
        assert comp in component_names, f"Missing bundle component in metadata: {comp}"


# ── 17-18. Safety ─────────────────────────────────────────────────────────────

_PROHIBITED = [
    "we will file", "we will submit", "we will represent",
    "guaranteed outcome", "you will win", "as your solicitor",
]

def test_legal_boundary_notice_in_every_component():
    resp = client.post(f"/cases/{_make_paid_case()}/bundle/generate", json={})
    for comp, content in resp.json()["components"].items():
        assert "NOT legal advice" in content or "not legal advice" in content.lower(), \
            f"Legal boundary missing from {comp}"
        assert "not a solicitor or law firm" in content.lower(), \
            f"Solicitor disclaimer missing from {comp}"


def test_no_prohibited_phrases_in_bundle():
    resp = client.post(f"/cases/{_make_paid_case()}/bundle/generate", json={})
    for comp, content in resp.json()["components"].items():
        lower = content.lower()
        for phrase in _PROHIBITED:
            assert phrase.lower() not in lower, \
                f"Prohibited phrase '{phrase}' found in {comp}"


def test_safety_check_passes_for_all_components():
    case_id = _make_case()
    from backend.core.bundle import generate_full_bundle, get_confirmed_facts
    components = generate_full_bundle(_ASSESSMENT, _KEY_DATES, {}, [])
    for name, content in components.items():
        result = safety_check(content)
        assert result["passed"] is True, f"Safety check failed for {name}: {result['violations']}"


# ── 19-20. Saved-case integration ────────────────────────────────────────────

def test_saved_case_page_still_loads():
    resp = client.get("/pages/saved_case.html")
    assert resp.status_code == 200
    content = resp.text
    assert "Not a law firm" in content
    assert "not legal advice" in content.lower()


def test_bundle_status_404_unknown_case():
    resp = client.get("/cases/00000000-0000-0000-0000-000000000000/bundle")
    assert resp.status_code == 404


# ── 21-25. Regressions ────────────────────────────────────────────────────────

def test_phase4a_upload_regression():
    case_id = _make_case()
    resp = client.post(
        f"/cases/{case_id}/uploads",
        data={"doc_type": "payslip"},
        files={"file": ("p.pdf", io.BytesIO(_MOCK_PDF), "application/pdf")},
    )
    assert resp.status_code == 201


def test_phase3c_document_generation_regression():
    case_id = _make_paid_case()
    resp = client.post("/documents/generate", json={
        "document_type": "schedule_of_loss", "assessment": _ASSESSMENT,
        "facts": {"edt": "2026-04-01", "service_start_date": "2023-04-01", "jurisdiction": "EW"},
        "case_id": case_id,
    })
    assert resp.status_code == 200
    assert resp.json()["safety_check"]["passed"] is True


def test_phase3d_consent_regression():
    resp = client.post("/handoff/leads", json={
        "trigger_reason": "seek_solicitor", "name": "T", "email": "t@t.invalid",
        "consent_given": False,
    })
    assert resp.status_code == 422


def test_static_routes_regression():
    for path in ["/", "/pages/intake.html", "/pages/assessment.html", "/pages/saved_case.html"]:
        assert client.get(path).status_code == 200, f"{path} failed"


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
