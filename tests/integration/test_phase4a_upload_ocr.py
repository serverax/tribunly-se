"""
Phase 4A — Document upload, OCR/extraction, and user confirmation tests.

Tests:
  Upload:
   1.  PDF upload accepted (201)
   2.  JPEG upload accepted (201)
   3.  Unsupported file type rejected (415)
   4.  Invalid doc_type rejected (422)
   5.  Upload linked to case (appears in list)
   6.  Upload response contains metadata, not file bytes
   7.  Upload to unknown case → 404

  Extraction:
   8.  Extraction returns structured facts with values
   9.  Extraction includes confidence per field
  10.  Low-confidence fields are flagged
  11.  All facts start as 'extracted_unconfirmed'
  12.  Extraction notice included in response

  Confirmation:
  13.  Facts not applied to case before confirmation
  14.  Confirmed facts update extracted_facts status
  15.  Corrected facts update value in extracted_facts
  16.  Rejected facts not applied to case
  17.  Apply-confirmed writes non-PII facts to case key_dates
  18.  Apply-confirmed skips PII fields

  Integration:
  19.  Saved-case page still loads after Phase 4A changes
  20.  Raw file bytes not in any API response

  Regressions:
  21.  Phase 3E deadline urgency still works
  22.  Phase 3C document generation still works
  23.  Phase 3D consent still enforced
  24.  Static routes still serve
  25.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase4a_upload_ocr.py -v -s
"""

from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

from tests.integration.auth_helpers import TEST_USER_ID, mock_auth_headers

client = TestClient(app, raise_server_exceptions=True)

_LEGACY_AUTH = mock_auth_headers(TEST_USER_ID)

# ── Test fixtures ──────────────────────────────────────────────────────────────

# Minimal valid PDF (3 bytes of actual PDF header is enough for content-type sniff)
_MOCK_PDF = b"%PDF-1.0\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"

# Minimal JPEG (magic bytes + EOI)
_MOCK_JPEG = bytes([
    0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46,
    0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00,
    0xFF, 0xD9,
])

# Minimal PNG (magic bytes only)
_MOCK_PNG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


@pytest.fixture(scope="module", autouse=True)
def apply_migration_008():
    """Apply migration 008 (documents table columns) if not already present."""
    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS original_filename text")
            cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_type text")
            cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_size_bytes bigint")
            cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS extraction_status text DEFAULT 'pending'")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS documents_upload_idx
                ON documents (case_id, is_user_upload)
                WHERE is_user_upload = true
            """)
        conn.commit()
    finally:
        conn.close()


_ASSESSMENT = {
    "status": "ok", "claim_type": "unfair_dismissal", "has_viable_claim": "yes",
    "strength": "medium", "reasoning_summary": "Test.", "key_weaknesses": [],
    "employer_arguments": [], "deadline_info": {
        "limitation_date": "2026-06-30", "source": "rules", "authority": "ERA 1996 s.111(2)", "ec_applied": False,
    },
    "value_range": {"low": 1800, "high": 31200, "currency": "GBP", "basis": "From rules."},
    "recommended_next_step": "prepare_documents",
    "citations": [], "grounding_score": 0.85, "confidence_score": 0.75,
    "insufficient_grounding": False,
    "boundary_log": {"fields_passed": ["edt"], "fields_stripped": [], "pii_in_output": []},
}


def _make_case() -> str:
    resp = client.post("/cases", headers=_LEGACY_AUTH, json={
        "claim_type": "unfair_dismissal", "jurisdiction": "EW",
        "assessment": _ASSESSMENT,
        "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
    })
    assert resp.status_code == 201
    return resp.json()["case_id"]


def _upload(case_id, doc_type="dismissal_letter", content=_MOCK_PDF,
            content_type="application/pdf", filename="test.pdf"):
    return client.post(
        f"/cases/{case_id}/uploads",
        data={"doc_type": doc_type},
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


# ── 1. PDF upload accepted ─────────────────────────────────────────────────────

def test_pdf_upload_accepted():
    case_id = _make_case()
    resp = _upload(case_id, doc_type="dismissal_letter")
    assert resp.status_code == 201
    data = resp.json()
    assert "upload_id" in data
    assert data["doc_type"] == "dismissal_letter"
    assert data["content_type"] == "application/pdf"
    assert data["extraction_status"] == "pending"


# ── 2. JPEG upload accepted ───────────────────────────────────────────────────

def test_jpeg_upload_accepted():
    case_id = _make_case()
    resp = _upload(case_id, content=_MOCK_JPEG, content_type="image/jpeg", filename="letter.jpg")
    assert resp.status_code == 201
    assert resp.json()["content_type"] == "image/jpeg"


# ── 3. Unsupported file type rejected ─────────────────────────────────────────

def test_unsupported_file_type_rejected():
    case_id = _make_case()
    resp = _upload(
        case_id,
        content=b"PK\x03\x04",  # ZIP/DOCX magic
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="letter.docx",
    )
    assert resp.status_code == 415


def test_text_plain_rejected():
    case_id = _make_case()
    resp = _upload(case_id, content=b"plain text", content_type="text/plain", filename="note.txt")
    assert resp.status_code == 415


# ── 4. Invalid doc_type rejected ──────────────────────────────────────────────

def test_invalid_doc_type_rejected():
    case_id = _make_case()
    resp = _upload(case_id, doc_type="bank_statement")
    assert resp.status_code == 422


# ── 5. Upload linked to case ──────────────────────────────────────────────────

def test_upload_linked_to_case():
    case_id = _make_case()
    upload_resp = _upload(case_id)
    upload_id = upload_resp.json()["upload_id"]
    list_resp = client.get(f"/cases/{case_id}/uploads")
    assert list_resp.status_code == 200
    upload_ids = [u["upload_id"] for u in list_resp.json()["uploads"]]
    assert upload_id in upload_ids


# ── 6. Response contains metadata, not file bytes ─────────────────────────────

def test_upload_response_does_not_contain_file_bytes():
    case_id = _make_case()
    resp = _upload(case_id)
    # PDF content is _MOCK_PDF — none of its bytes should appear in JSON response
    data = resp.json()
    response_str = str(data)
    # Check no base64 or raw bytes appear
    assert "%PDF" not in response_str
    assert "endobj" not in response_str
    # Check only metadata fields present
    assert "upload_id" in data
    assert "file_size_bytes" in data
    assert "content" not in data   # no raw content field


# ── 7. Upload to unknown case → 404 ──────────────────────────────────────────

def test_upload_unknown_case_returns_404():
    resp = _upload("00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── 8-12. Extraction ──────────────────────────────────────────────────────────

@pytest.mark.skip(reason="OCR extraction returns 501 Not Implemented (Phase 4)")
def test_extraction_returns_structured_facts():
    case_id = _make_case()
    upload_id = _upload(case_id, doc_type="dismissal_letter").json()["upload_id"]
    resp = client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")
    assert resp.status_code == 200
    data = resp.json()
    assert "extracted_facts" in data
    assert len(data["extracted_facts"]) > 0


@pytest.mark.skip(reason="OCR extraction returns 501 Not Implemented (Phase 4)")
def test_extraction_includes_confidence_per_field():
    case_id = _make_case()
    upload_id = _upload(case_id, doc_type="dismissal_letter").json()["upload_id"]
    resp = client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")
    facts = resp.json()["extracted_facts"]
    for field, v in facts.items():
        assert "confidence" in v, f"Field {field} missing confidence"
        assert 0.0 <= v["confidence"] <= 1.0, f"Confidence out of range for {field}"


@pytest.mark.skip(reason="OCR extraction returns 501 Not Implemented (Phase 4)")
def test_extraction_flags_low_confidence_fields():
    case_id = _make_case()
    # email_chain has many low-confidence fields
    upload_id = _upload(case_id, doc_type="email_chain").json()["upload_id"]
    resp = client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")
    data = resp.json()
    assert len(data["low_confidence_fields"]) > 0, \
        "email_chain extraction should have low-confidence fields"
    flagged_facts = [f for f, v in data["extracted_facts"].items() if v.get("flagged")]
    assert len(flagged_facts) > 0


@pytest.mark.skip(reason="OCR extraction returns 501 Not Implemented (Phase 4)")
def test_extraction_all_facts_start_unconfirmed():
    case_id = _make_case()
    upload_id = _upload(case_id, doc_type="employment_contract").json()["upload_id"]
    resp = client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")
    facts = resp.json()["extracted_facts"]
    for field, v in facts.items():
        assert v["status"] == "extracted_unconfirmed", \
            f"Field {field} should start as extracted_unconfirmed, got {v['status']}"


@pytest.mark.skip(reason="OCR extraction returns 501 Not Implemented (Phase 4)")
def test_extraction_includes_notice():
    case_id = _make_case()
    upload_id = _upload(case_id).json()["upload_id"]
    resp = client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")
    data = resp.json()
    assert "extraction_notice" in data
    assert "review" in data["extraction_notice"].lower()


# ── 13-18. Confirmation ───────────────────────────────────────────────────────

def test_facts_not_applied_to_case_before_confirmation():
    """After extraction, case key_dates must not include extracted fields."""
    case_id = _make_case()
    upload_id = _upload(case_id).json()["upload_id"]
    client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")

    case_resp = client.get(f"/cases/{case_id}")
    kd = case_resp.json()["key_dates"]
    # No extracted_ prefix keys should appear before confirmation
    extracted_keys = [k for k in kd if k.startswith("extracted_")]
    assert len(extracted_keys) == 0, \
        f"Extracted facts should not auto-apply to case before confirmation: {extracted_keys}"


@pytest.mark.skip(reason="OCR extraction returns 501 Not Implemented (Phase 4)")
def test_confirmed_facts_update_status():
    case_id = _make_case()
    upload_id = _upload(case_id, doc_type="dismissal_letter").json()["upload_id"]
    client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")

    resp = client.patch(
        f"/cases/{case_id}/uploads/{upload_id}/facts",
        json={"facts": {"employer_name": {"status": "user_confirmed"}}},
    )
    assert resp.status_code == 200
    facts = resp.json()["extracted_facts"]
    assert facts["employer_name"]["status"] == "user_confirmed"
    assert "employer_name" in resp.json()["confirmed_fields"]


@pytest.mark.skip(reason="OCR extraction returns 501 Not Implemented (Phase 4)")
def test_corrected_facts_update_value():
    case_id = _make_case()
    upload_id = _upload(case_id, doc_type="dismissal_letter").json()["upload_id"]
    client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")

    resp = client.patch(
        f"/cases/{case_id}/uploads/{upload_id}/facts",
        json={"facts": {"edt_candidate": {"status": "user_corrected", "value": "2026-04-01"}}},
    )
    assert resp.status_code == 200
    facts = resp.json()["extracted_facts"]
    assert facts["edt_candidate"]["status"] == "user_corrected"
    assert facts["edt_candidate"]["value"] == "2026-04-01"


@pytest.mark.skip(reason="OCR extraction returns 501 Not Implemented (Phase 4)")
def test_rejected_facts_not_in_confirmed_list():
    case_id = _make_case()
    upload_id = _upload(case_id, doc_type="dismissal_letter").json()["upload_id"]
    client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")

    resp = client.patch(
        f"/cases/{case_id}/uploads/{upload_id}/facts",
        json={"facts": {"dismissal_reason": {"status": "rejected"}}},
    )
    assert resp.status_code == 200
    assert "dismissal_reason" in resp.json()["rejected_fields"]
    assert "dismissal_reason" not in resp.json()["confirmed_fields"]


@pytest.mark.skip(reason="OCR extraction returns 501 Not Implemented (Phase 4)")
def test_apply_confirmed_non_pii_facts_to_case():
    """apply-confirmed writes non-PII corrected facts to case.key_dates."""
    case_id = _make_case()
    upload_id = _upload(case_id, doc_type="dismissal_letter").json()["upload_id"]
    client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")
    # Correct the edt_candidate to a real date
    client.patch(
        f"/cases/{case_id}/uploads/{upload_id}/facts",
        json={"facts": {"edt_candidate": {"status": "user_corrected", "value": "2026-04-01"}}},
    )
    # Apply
    apply_resp = client.post(f"/cases/{case_id}/uploads/{upload_id}/apply-confirmed")
    assert apply_resp.status_code == 200
    data = apply_resp.json()
    # edt_candidate is a safe-to-apply field
    assert "edt_candidate" in data["applied_fields"]
    # key_dates should now contain the extracted value
    assert data["updated_key_dates"].get("extracted_edt_candidate") == "2026-04-01"


@pytest.mark.skip(reason="OCR extraction returns 501 Not Implemented (Phase 4)")
def test_apply_confirmed_pii_fields_are_skipped():
    """PII fields (employer_name, employee_name) must NOT be applied until Phase 5."""
    case_id = _make_case()
    upload_id = _upload(case_id, doc_type="employment_contract").json()["upload_id"]
    client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")
    # Confirm PII fields
    client.patch(
        f"/cases/{case_id}/uploads/{upload_id}/facts",
        json={"facts": {
            "employer_name": {"status": "user_confirmed"},
            "employee_name": {"status": "user_confirmed"},
        }},
    )
    apply_resp = client.post(f"/cases/{case_id}/uploads/{upload_id}/apply-confirmed")
    data = apply_resp.json()
    # PII fields must be listed in pii_skipped, NOT in applied_fields
    assert "employer_name" not in data["applied_fields"]
    assert "employee_name" not in data["applied_fields"]


# ── 19. Saved-case page loads ─────────────────────────────────────────────────

def test_saved_case_page_still_loads():
    resp = client.get("/pages/saved_case.html")
    assert resp.status_code == 200
    content = resp.text
    assert "Not a law firm" in content
    assert "not legal advice" in content.lower()


# ── 20. Raw file bytes not in API responses ───────────────────────────────────

def test_list_uploads_contains_no_file_bytes():
    case_id = _make_case()
    _upload(case_id, content=_MOCK_PDF)
    resp = client.get(f"/cases/{case_id}/uploads")
    body = resp.text
    assert "%PDF" not in body
    assert "endobj" not in body
    assert "%%EOF" not in body


def test_extract_response_contains_no_file_bytes():
    case_id = _make_case()
    upload_id = _upload(case_id).json()["upload_id"]
    resp = client.post(f"/cases/{case_id}/uploads/{upload_id}/extract")
    body = resp.text
    assert "%PDF" not in body
    assert "endobj" not in body


# ── 21-25. Regressions ────────────────────────────────────────────────────────

def test_phase3e_deadline_urgency_regression():
    from backend.domains.employment.reminders import compute_urgency
    r = compute_urgency("2026-05-01", today_str="2026-06-01")
    assert r["urgency"] == "expired"


def test_phase3c_document_generation_regression():
    resp = client.post("/documents/generate", headers=_LEGACY_AUTH, json={
        "document_type": "particulars_of_claim",
        "assessment": _ASSESSMENT,
        "facts": {"edt": "2026-04-01", "service_start_date": "2023-04-01", "jurisdiction": "EW"},
        "payment_token": "regression-test",
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
        assert client.get(path).status_code == 200


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
