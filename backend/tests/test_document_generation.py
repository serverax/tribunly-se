"""
Test suite for document generation (post-payment).

Acceptance gates:
1. Document generated from assessment
2. All citations present in document
3. Disclaimer included
4. Document encrypted in storage
5. Download requires auth + ownership
6. Wrong user cannot download
"""

import pytest
import uuid
import json
from unittest.mock import Mock, patch
from pathlib import Path

from fastapi import HTTPException
from ingestion.db import get_connection


@pytest.fixture
def test_user_id():
    """Return a test user ID."""
    return str(uuid.uuid4())


@pytest.fixture
def test_case_id():
    """Return a test case ID."""
    return str(uuid.uuid4())


@pytest.fixture
def setup_test_user_and_case(test_user_id, test_case_id):
    """Create a test user and case in the database."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Create user
            cur.execute(
                "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s) "
                "ON CONFLICT (email) DO NOTHING",
                (test_user_id, f"test-{test_user_id}@example.com", "hash"),
            )
            # Create case with assessment
            assessment = {
                "has_viable_claim": True,
                "strength": "high",
                "claim_types": ["unfair_dismissal"],
                "key_weaknesses": ["lack of evidence"],
                "evidence_needed": ["employment contract"],
                "value_range": {"min": 5000, "max": 15000},
                "citations": [
                    {
                        "cite": "Employment Rights Act 1996 s.94",
                        "title": "Right to claim unfair dismissal",
                        "url": "https://legislation.gov.uk/ukpga/1996/18/section/94",
                    }
                ],
            }
            key_dates = {
                "employment_start": "2020-01-15",
                "dismissal_date": "2024-05-10",
                "notice_period": "one month",
            }
            cur.execute(
                """
                INSERT INTO cases (
                    id, user_id, case_title, claim_type, assessment,
                    key_dates, payment_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    test_case_id,
                    test_user_id,
                    "Test Case",
                    "unfair_dismissal",
                    json.dumps(assessment),
                    json.dumps(key_dates),
                    "paid",  # Mark as paid for document generation tests
                ),
            )
        conn.commit()
    finally:
        conn.close()
    yield test_user_id, test_case_id


# ── Test 1: Document generated from assessment ─────────────────────────────────

def test_generate_et1_document(setup_test_user_and_case, test_user_id, test_case_id):
    """Should generate ET1 support document from assessment."""
    from backend.api.document_routes import generate_document, GenerateDocumentRequest

    request = GenerateDocumentRequest(
        case_id=test_case_id,
        document_type="et1_support",
        confirmed_facts={"dismissal_reason": "redundancy"},
    )

    with patch("backend.api.document_routes.get_current_user") as mock_auth:
        mock_auth.return_value = test_user_id

        with patch("backend.api.document_routes.check_case_ownership"):
            with patch("backend.api.document_routes.is_case_paid") as mock_paid:
                mock_paid.return_value = True

                with patch("backend.api.document_routes.safety_check") as mock_safety:
                    mock_safety.return_value = {"passed": True, "violations": []}

                    response = generate_document(request, x_user_id=test_user_id)

    assert response.status == "generated"
    assert response.document_type == "et1_support"
    assert response.document_id is not None
    assert response.download_url == f"/api/documents/{response.document_id}"


def test_generate_particulars_document(setup_test_user_and_case, test_user_id, test_case_id):
    """Should generate Particulars of Claim document."""
    from backend.api.document_routes import generate_document, GenerateDocumentRequest

    request = GenerateDocumentRequest(
        case_id=test_case_id,
        document_type="particulars",
        confirmed_facts={},
    )

    with patch("backend.api.document_routes.get_current_user") as mock_auth:
        mock_auth.return_value = test_user_id

        with patch("backend.api.document_routes.check_case_ownership"):
            with patch("backend.api.document_routes.is_case_paid") as mock_paid:
                mock_paid.return_value = True

                with patch("backend.api.document_routes.safety_check") as mock_safety:
                    mock_safety.return_value = {"passed": True, "violations": []}

                    response = generate_document(request, x_user_id=test_user_id)

    assert response.status == "generated"
    assert response.document_type == "particulars"


# ── Test 2: All citations present in document ──────────────────────────────────

def test_document_includes_citations(setup_test_user_and_case, test_user_id, test_case_id):
    """Generated document should include all citations from assessment."""
    from backend.api.document_routes import _generate_et1_support

    case_data = {"case_id": test_case_id}
    assessment = {
        "claim_types": ["unfair_dismissal"],
        "strength": "high",
        "value_range": {"min": 5000, "max": 15000},
        "key_weaknesses": ["no evidence"],
        "evidence_needed": ["contract"],
        "citations": [
            {
                "cite": "ERA 1996 s.94",
                "title": "Right to claim",
                "url": "https://example.com",
            },
            {
                "cite": "Polkey v Dayton Services Ltd",
                "title": "Procedural fairness",
                "url": "https://example.com",
            },
        ],
    }
    facts = {"employment_start": "2020-01-15", "dismissal_date": "2024-05-10"}

    html = _generate_et1_support(case_data, assessment, facts)

    # Check both citations are present
    assert "ERA 1996 s.94" in html or "s.94" in html
    assert "Polkey" in html or "Procedural fairness" in html


# ── Test 3: Legal boundary disclaimer included ────────────────────────────────

def test_document_includes_disclaimer(setup_test_user_and_case, test_user_id, test_case_id):
    """All documents must include the legal boundary notice."""
    from backend.api.document_routes import _generate_et1_support
    from backend.core.documents import LEGAL_BOUNDARY_NOTICE

    case_data = {"case_id": test_case_id}
    assessment = {
        "claim_types": ["unfair_dismissal"],
        "strength": "high",
        "value_range": {"min": 0, "max": 0},
        "key_weaknesses": [],
        "evidence_needed": [],
        "citations": [],
    }
    facts = {}

    html = _generate_et1_support(case_data, assessment, facts)

    # Should contain the disclaimer (at least part of it)
    assert "self-help" in html.lower() or "SELF-HELP" in html
    assert "not" in html.lower() and "legal advice" in html.lower()


# ── Test 4: Document requires payment ──────────────────────────────────────────

def test_generate_document_requires_payment(setup_test_user_and_case, test_user_id, test_case_id):
    """Should fail if case is not paid."""
    from backend.api.document_routes import generate_document, GenerateDocumentRequest

    # Mark case as unpaid
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE cases SET payment_status = %s WHERE id = %s::uuid",
                ("unpaid", test_case_id),
            )
        conn.commit()
    finally:
        conn.close()

    request = GenerateDocumentRequest(case_id=test_case_id, document_type="et1_support")

    with patch("backend.api.document_routes.get_current_user") as mock_auth:
        mock_auth.return_value = test_user_id

        with patch("backend.api.document_routes.check_case_ownership"):
            with patch("backend.api.document_routes.is_case_paid") as mock_paid:
                mock_paid.return_value = False

                with pytest.raises(HTTPException) as exc_info:
                    generate_document(request, x_user_id=test_user_id)

    assert exc_info.value.status_code == 402  # Payment Required


# ── Test 5: Invalid document type rejected ────────────────────────────────────

def test_generate_document_invalid_type(setup_test_user_and_case, test_user_id, test_case_id):
    """Should reject invalid document types."""
    from backend.api.document_routes import generate_document, GenerateDocumentRequest

    request = GenerateDocumentRequest(
        case_id=test_case_id,
        document_type="invalid_type",
    )

    with patch("backend.api.document_routes.get_current_user") as mock_auth:
        mock_auth.return_value = test_user_id

        with patch("backend.api.document_routes.check_case_ownership"):
            with patch("backend.api.document_routes.is_case_paid") as mock_paid:
                mock_paid.return_value = True

                with pytest.raises(HTTPException) as exc_info:
                    generate_document(request, x_user_id=test_user_id)

    assert exc_info.value.status_code == 400


# ── Test 6: Download requires auth + ownership + payment ──────────────────────

def test_download_unauthorized():
    """Download should fail if user is not authenticated."""
    from backend.api.document_routes import download_document

    with patch("backend.api.document_routes.get_current_user") as mock_auth:
        mock_auth.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            download_document(str(uuid.uuid4()))

    assert exc_info.value.status_code == 401


def test_download_wrong_owner(setup_test_user_and_case, test_case_id):
    """Download should fail if user doesn't own the document."""
    from backend.api.document_routes import download_document

    # Create a document owned by a different user
    other_user = str(uuid.uuid4())
    document_id = str(uuid.uuid4())

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (id, email, password_hash)
                VALUES (%s, %s, %s) ON CONFLICT (email) DO NOTHING
                """,
                (other_user, f"other-{other_user}@example.com", "hash"),
            )
            cur.execute(
                """
                INSERT INTO documents (
                    id, case_id, user_id, doc_type, document_type, storage_ref
                ) VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s)
                """,
                (document_id, test_case_id, other_user, "et1_support", "et1_support", "/tmp/test.html"),
            )
        conn.commit()
    finally:
        conn.close()

    # Try to download as different user
    requesting_user = str(uuid.uuid4())

    with patch("backend.api.document_routes.get_current_user") as mock_auth:
        mock_auth.return_value = requesting_user

        with pytest.raises(HTTPException) as exc_info:
            download_document(document_id)

    assert exc_info.value.status_code == 403


def test_download_unpaid():
    """Download should fail if case is not paid."""
    from backend.api.document_routes import download_document

    user_id = str(uuid.uuid4())
    case_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())

    # Create case and document
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s)
                ON CONFLICT (email) DO NOTHING
                """,
                (user_id, f"test-{user_id}@example.com", "hash"),
            )
            cur.execute(
                """
                INSERT INTO cases (
                    id, user_id, case_title, claim_type, assessment, payment_status
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (case_id, user_id, "Test", "unfair_dismissal", "{}", "unpaid"),
            )
            cur.execute(
                """
                INSERT INTO documents (
                    id, case_id, user_id, doc_type, document_type, storage_ref
                ) VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s)
                """,
                (document_id, case_id, user_id, "et1_support", "et1_support", "/tmp/test.html"),
            )
        conn.commit()
    finally:
        conn.close()

    # Try to download
    with patch("backend.api.document_routes.get_current_user") as mock_auth:
        mock_auth.return_value = user_id

        with patch("backend.api.document_routes.is_case_paid") as mock_paid:
            mock_paid.return_value = False

            with pytest.raises(HTTPException) as exc_info:
                download_document(document_id)

    assert exc_info.value.status_code == 402


# ── Test 7: Safety check prevents prohibited phrases ──────────────────────────

def test_safety_check_fails_for_guarantees():
    """Document with outcome guarantees should fail safety check."""
    from backend.core.documents import safety_check

    bad_doc = "You will definitely win your case. We guarantee a successful outcome."
    result = safety_check(bad_doc)

    assert result["passed"] is False
    assert len(result["violations"]) > 0


def test_safety_check_fails_for_solicitor_claims():
    """Document claiming to be a solicitor should fail safety check."""
    from backend.core.documents import safety_check

    bad_doc = "We are your solicitors and will represent you in your claim."
    result = safety_check(bad_doc)

    assert result["passed"] is False


def test_safety_check_passes_for_valid_doc():
    """Properly disclaimed document should pass safety check."""
    from backend.core.documents import safety_check, LEGAL_BOUNDARY_NOTICE

    good_doc = f"{LEGAL_BOUNDARY_NOTICE}\nThis is a draft document for your review."
    result = safety_check(good_doc)

    assert result["passed"] is True


# ── Test 8: Case not found ────────────────────────────────────────────────────

def test_generate_document_case_not_found(test_user_id):
    """Should fail if case doesn't exist."""
    from backend.api.document_routes import generate_document, GenerateDocumentRequest

    request = GenerateDocumentRequest(case_id=str(uuid.uuid4()), document_type="et1_support")

    with patch("backend.api.document_routes.get_current_user") as mock_auth:
        mock_auth.return_value = test_user_id

        with patch("backend.api.document_routes.check_case_ownership"):
            with patch("backend.api.document_routes.is_case_paid") as mock_paid:
                mock_paid.return_value = True

                with pytest.raises(HTTPException) as exc_info:
                    generate_document(request, x_user_id=test_user_id)

    assert exc_info.value.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
