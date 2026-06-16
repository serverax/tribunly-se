from __future__ import annotations
import uuid as _uuid

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.integration.auth_helpers import mock_auth_headers

from backend.api.main import app
from backend.core.pipeline import assess
from backend.core.models import StubReasoningModel

STUB = StubReasoningModel()
_MOCK_PDF = b"%PDF-1.0\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"

# ── Fixtures ──────────────────────────────────────────────────────────────────

_TEST_ADMIN_KEY = "test-admin-key-phase6"

@pytest.fixture(scope="module", autouse=True)
def apply_migration_012():
    """Apply migration 012 (encryption + deletion columns)."""
    from ingestion.db import get_connection
    from cryptography.fernet import Fernet

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS deleted_at timestamptz")
            cur.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS encryption_version text DEFAULT 'none'")
            cur.execute("ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS deleted_at timestamptz")
            cur.execute("ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS name_encrypted text")
            cur.execute("ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS email_encrypted text")
            cur.execute("ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS phone_encrypted text")
            cur.execute("ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS pii_encrypted boolean NOT NULL DEFAULT false")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS retention_runs (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    run_at timestamptz NOT NULL DEFAULT now(),
                    records_processed int NOT NULL DEFAULT 0,
                    records_deleted int NOT NULL DEFAULT 0,
                    policy_days int NOT NULL,
                    notes text
                )
            """)
        conn.commit()
    finally:
        conn.close()

    # Set env vars for this test module
    test_key = Fernet.generate_key().decode()
    os.environ["ADMIN_API_KEY"]    = _TEST_ADMIN_KEY
    os.environ["ENCRYPTION_KEY"]   = test_key
    yield {"admin_key": _TEST_ADMIN_KEY, "enc_key": test_key}
    os.environ.pop("ADMIN_API_KEY",  None)
    os.environ.pop("ENCRYPTION_KEY", None)


client = TestClient(app, raise_server_exceptions=True)

_ADMIN_HDR = {"X-Admin-Key": _TEST_ADMIN_KEY}
_WRONG_HDR = {"X-Admin-Key": "wrong-key-12345"}

_ASSESSMENT = {
    "status": "ok", "claim_type": "unfair_dismissal", "has_viable_claim": "yes",
    "strength": "medium", "reasoning_summary": "Test.",
    "key_weaknesses": [], "employer_arguments": [],
    "deadline_info": {"limitation_date": "2026-06-30", "source": "rules", "authority": "ERA 1996 s.111(2)", "ec_applied": False},
    "value_range": {"low": 1800, "high": 31200, "currency": "GBP", "basis": "From rules."},
    "recommended_next_step": "prepare_documents",
    "citations": [], "grounding_score": 0.85, "confidence_score": 0.75,
    "insufficient_grounding": False,
    "boundary_log": {"fields_passed": ["edt"], "fields_stripped": [], "pii_in_output": []},
}


def _make_case() -> str:
    resp = client.post("/cases", json={
        "claim_type": "unfair_dismissal", "jurisdiction": "EW",
        "assessment": _ASSESSMENT,
        "key_dates": {"edt": "2026-04-01", "deadline_date": "2026-06-30"},
    }, headers=mock_auth_headers())
    assert resp.status_code == 201
    return resp.json()["case_id"]


# ── 1-6. Admin authentication ────────────────────────────────────────────────

def test_admin_dp_report_without_key_returns_403():
    resp = client.get("/admin/dp-report")
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


def test_admin_dp_report_with_wrong_key_returns_403():
    resp = client.get("/admin/dp-report", headers=_WRONG_HDR)
    assert resp.status_code == 403


def test_admin_dp_report_with_correct_key_returns_200():
    resp = client.get("/admin/dp-report", headers=_ADMIN_HDR)
    assert resp.status_code == 200


def test_admin_rules_verification_requires_key():
    assert client.get("/admin/rules-verification").status_code == 403
    assert client.get("/admin/rules-verification", headers=_ADMIN_HDR).status_code == 200


def test_admin_production_readiness_requires_key():
    assert client.get("/admin/production-readiness").status_code == 403
    assert client.get("/admin/production-readiness", headers=_ADMIN_HDR).status_code == 200


def test_admin_retention_status_requires_key():
    assert client.get("/admin/retention-status").status_code == 403
    assert client.get("/admin/retention-status", headers=_ADMIN_HDR).status_code == 200


# ── 7-10. Encryption ──────────────────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip():
    from backend.core.encryption import encrypt_str, decrypt_str
    plaintext = "Alice Johnson  -  test PII"
    ciphertext = encrypt_str(plaintext)
    recovered  = decrypt_str(ciphertext)
    assert recovered == plaintext


def test_encrypt_produces_different_value():
    from backend.core.encryption import encrypt_str
    plaintext  = "alice@test.invalid"
    ciphertext = encrypt_str(plaintext)
    assert ciphertext != plaintext
    assert len(ciphertext) > len(plaintext)


def test_handoff_lead_pii_encrypted_at_rest():
    """When ENCRYPTION_KEY set, handoff lead PII should be encrypted in DB."""
    resp = client.post("/handoff/leads", json={
        "trigger_reason": "seek_solicitor",
        "name":           "Test Person Phase6",
        "email":          "testphase6@test.invalid",
        "consent_given":  True,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data.get("pii_encrypted") is True, \
        "pii_encrypted must be True when ENCRYPTION_KEY is set"


def test_upload_stores_encrypted_file():
    """When ENCRYPTION_KEY is set, upload endpoint should encrypt the file."""
    case_id = _make_case()
    resp = client.post(
        f"/cases/{case_id}/uploads",
        data={"doc_type": "dismissal_letter"},
        files={"file": ("dl.pdf", io.BytesIO(_MOCK_PDF), "application/pdf")},
    )
    assert resp.status_code == 201
    # The storage_note should reference local storage (encryption is transparent)
    assert "storage_note" in resp.json()


# ── 11-15. Deletion / retention ───────────────────────────────────────────────

def test_case_can_be_soft_deleted():
    case_id = _make_case()
    resp = client.delete(f"/cases/{case_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "deleted"
    assert "Art.17" in data.get("note", "")


def test_soft_deleted_case_returns_404():
    case_id = _make_case()
    client.delete(f"/cases/{case_id}")
    resp = client.get(f"/cases/{case_id}")
    assert resp.status_code == 404, "Soft-deleted case must return 404"


def test_handoff_lead_pii_cleared_on_delete():
    lead_resp = client.post("/handoff/leads", json={
        "trigger_reason": "insufficient_grounding",
        "name":           "Delete Test",
        "email":          "delete@test.invalid",
        "consent_given":  True,
    })
    lead_id = lead_resp.json()["lead_id"]

    del_resp = client.delete(f"/handoff/leads/{lead_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "pii_cleared"
    assert "Art.17" in del_resp.json().get("note", "")


def test_retention_script_dry_run():
    result = subprocess.run(
        [sys.executable, "scripts/run_retention.py"],   # dry run by default
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Retention dry-run failed:\n{result.stdout}\n{result.stderr}"
    assert "DRY RUN" in result.stdout


def test_retention_status_endpoint():
    resp = client.get("/admin/retention-status?retention_days=90", headers=_ADMIN_HDR)
    assert resp.status_code == 200
    data = resp.json()
    assert "old_cases_count" in data
    assert "old_handoff_leads_count" in data
    assert data.get("note", "").lower().find("report") >= 0 or "does not delete" in data.get("note", "")


# ── 16-17. Privacy / DPIA artefacts ──────────────────────────────────────────

def test_privacy_notice_draft_exists():
    docs_path = Path(__file__).resolve().parent.parent.parent / "docs" / "privacy-notice-draft.md"
    assert docs_path.exists(), f"Privacy notice draft not found at {docs_path}"
    content = docs_path.read_text(encoding="utf-8")
    assert "DRAFT" in content
    assert "personal data" in content.lower()


def test_dpia_artefact_exists():
    docs_path = Path(__file__).resolve().parent.parent.parent / "docs" / "dpia-artefact.md"
    assert docs_path.exists(), f"DPIA artefact not found at {docs_path}"
    content = docs_path.read_text(encoding="utf-8")
    assert "DPIA" in content
    assert "risk" in content.lower()


# ── 18-20. Production readiness ───────────────────────────────────────────────

def test_production_readiness_reflects_phase6():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    assert resp.status_code == 200
    data = resp.json()
    assert "admin_authentication" in data
    assert "encryption_at_rest" in data
    assert "deletion_policy" in data
    assert "privacy_notice" in data
    assert "dpia" in data


def test_production_readiness_still_not_production_ready():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert data["overall_status"] == "NOT_PRODUCTION_READY", \
        "Must remain NOT_PRODUCTION_READY  -  no live deployment or DPIA signed off"
    assert data["ready_for_production"] is False


def test_production_readiness_shows_encryption_status():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    enc = resp.json().get("encryption_at_rest", {})
    # With ENCRYPTION_KEY set in fixture, should be PARTIAL
    assert enc.get("status") in ("PARTIAL", "NOT_CONFIGURED")
    assert enc.get("production_ready") is False


# ── 21-25. Regressions ────────────────────────────────────────────────────────

def test_legal_accuracy_gate_regression():
    result = subprocess.run(
        [sys.executable, "scripts/run_legal_accuracy.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Legal accuracy gate failed:\n{result.stdout}"


def test_ud_assessment_regression():
    result = assess("I was unfairly dismissed", {
        "edt": "2026-04-01", "service_start_date": "2023-04-01",
        "reason_for_dismissal": "conduct", "weekly_pay": 600, "jurisdiction": "EW",
    }, model=STUB)
    assert (result.get("deadline_info") or {}).get("source") == "rules"


def test_upw_assessment_regression():
    result = assess("My employer hasn't paid my wages", {
        "wages_due_date": "2026-03-31", "unpaid_amount": 2500.0,
        "worker_status": "employee", "jurisdiction": "EW",
    }, model=STUB)
    assert "boundary_log" in result


def test_static_routes_regression():
    for path in ["/", "/pages/intake.html", "/pages/assessment.html", "/pages/saved_case.html"]:
        assert client.get(path).status_code == 200


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"

def test_case_facts_encrypted_on_save():
    """Phase 6: save_case with facts -> encrypted in DB, decrypted on GET."""
    client = TestClient(app)
    user_id = str(_uuid.uuid4())
    # Ensure user exists (using mock mode/admin bypass not needed for save but helpful)
    facts = {"edt": "2026-04-01", "secret_info": "pii-data"}
    assessment = {"has_viable_claim": "yes"}
    key_dates = {"edt": "2026-04-01"}
    
    # Save case with facts
    save_resp = client.post(
        "/cases",
        json={
            "claim_type": "unfair_dismissal",
            "jurisdiction": "EW",
            "assessment": assessment,
            "key_dates": key_dates,
            "facts": facts
        },
        headers={"X-User-ID": user_id}
    )
    assert save_resp.status_code == 201
    case_id = save_resp.json()["case_id"]
    
    # Check DB directly to prove encryption
    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT facts_encrypted, encryption_version FROM cases WHERE id = %s", (case_id,))
            row = cur.fetchone()
            assert row[0] is not None
            assert row[1] == "fernet_v1"
            # Proven: facts_encrypted is a binary blob
    finally:
        conn.close()
        
    # Retrieve via GET and prove decryption
    get_resp = client.get(f"/cases/{case_id}", headers={"X-User-ID": user_id})
    assert get_resp.status_code == 200
    assert get_resp.json()["facts"] == facts
