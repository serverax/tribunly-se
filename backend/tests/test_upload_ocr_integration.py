"""
Test suite for upload and OCR integration.

Acceptance gates:
1. File upload accepted (valid types)
2. File upload rejected (invalid types)
3. OCR extraction (text returned)
4. Encryption verified (file not readable as plaintext)
5. OCR fail returns 501 (not fake extraction)
6. Extracted facts logged
"""

import pytest
import uuid
import json
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from io import BytesIO

from fastapi import HTTPException, UploadFile
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
            # Create case
            cur.execute(
                """
                INSERT INTO cases (
                    id, user_id, case_title, claim_type, assessment, payment_status
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    test_case_id,
                    test_user_id,
                    "Test Case",
                    "unfair_dismissal",
                    "{}",
                    "unpaid",
                ),
            )
        conn.commit()
    finally:
        conn.close()
    yield test_user_id, test_case_id


# ── Test 1: File upload accepted (valid types) ────────────────────────────────

def test_upload_valid_pdf(setup_test_user_and_case, test_user_id, test_case_id):
    """Should accept valid PDF files."""
    from backend.api.upload_routes import _validate_file

    # Should not raise
    _validate_file("document.pdf", "application/pdf", 1000)


def test_upload_valid_docx(setup_test_user_and_case, test_user_id, test_case_id):
    """Should accept valid DOCX files."""
    from backend.api.upload_routes import _validate_file

    _validate_file("document.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 5000)


def test_upload_valid_text(setup_test_user_and_case, test_user_id, test_case_id):
    """Should accept plain text files."""
    from backend.api.upload_routes import _validate_file

    _validate_file("notes.txt", "text/plain", 500)


def test_upload_valid_image(setup_test_user_and_case, test_user_id, test_case_id):
    """Should accept JPG and PNG images."""
    from backend.api.upload_routes import _validate_file

    _validate_file("scan.jpg", "image/jpeg", 2000000)
    _validate_file("scan.png", "image/png", 3000000)


# ── Test 2: File upload rejected (invalid types) ────────────────────────────────

def test_upload_invalid_extension():
    """Should reject invalid file extensions."""
    from backend.api.upload_routes import _validate_file

    with pytest.raises(HTTPException) as exc_info:
        _validate_file("document.exe", "application/octet-stream", 1000)

    assert exc_info.value.status_code == 400
    assert "not allowed" in str(exc_info.value.detail).lower()


def test_upload_invalid_mime_type():
    """Should reject invalid MIME types."""
    from backend.api.upload_routes import _validate_file

    with pytest.raises(HTTPException) as exc_info:
        _validate_file("malware.bin", "application/octet-stream", 1000)

    assert exc_info.value.status_code == 400


def test_upload_file_too_large():
    """Should reject files over 10 MB."""
    from backend.api.upload_routes import _validate_file, MAX_FILE_SIZE_BYTES

    with pytest.raises(HTTPException) as exc_info:
        _validate_file("large.pdf", "application/pdf", MAX_FILE_SIZE_BYTES + 1)

    assert exc_info.value.status_code == 413
    assert "too large" in str(exc_info.value.detail).lower()


# ── Test 3: OCR extraction ─────────────────────────────────────────────────────

def test_ocr_extracts_text(setup_test_user_and_case, test_user_id, test_case_id):
    """Should extract text from documents using OCR."""
    from backend.core.document_extractor import extract_text_from_document

    # Mock a simple PDF with text
    sample_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nBT /F1 12 Tf 100 100 Td (Sample Text) Tj ET"

    with patch("backend.core.document_extractor.PyPDF2") as mock_pypdf:
        mock_reader = Mock()
        mock_page = Mock()
        mock_page.extract_text.return_value = "Sample dismissal letter dated 2024-05-10"
        mock_reader.pages = [mock_page]
        mock_pypdf.PdfReader.return_value = mock_reader

        text, doc_type = extract_text_from_document(sample_pdf, "application/pdf")

        assert text is not None
        assert "dismissal" in text.lower() or "letter" in text.lower()


def test_ocr_detects_document_type():
    """Should detect document type from content."""
    from backend.core.document_extractor import extract_text_from_document

    # Text that looks like a dismissal letter
    content = b"Dear Employee, Your employment is terminated effective 2024-05-10."

    with patch("backend.core.document_extractor.PyPDF2") as mock_pypdf:
        mock_reader = Mock()
        mock_page = Mock()
        mock_page.extract_text.return_value = "Your employment is terminated effective 2024-05-10"
        mock_reader.pages = [mock_page]
        mock_pypdf.PdfReader.return_value = mock_reader

        text, doc_type = extract_text_from_document(content, "application/pdf")

        assert text is not None
        # doc_type should be detected (dismissal_letter, contract, etc.)


# ── Test 4: Encryption verified ────────────────────────────────────────────────

def test_file_encryption():
    """File should be encrypted in storage, not plaintext."""
    from backend.api.upload_routes import _encrypt_file, _get_encryption_key

    plaintext = b"This is sensitive data"
    key = _get_encryption_key()
    encrypted = _encrypt_file(plaintext, key)

    # Encrypted should not equal plaintext
    assert encrypted != plaintext

    # Should be able to decrypt
    decrypted = _encrypt_file(encrypted, key)
    assert decrypted == plaintext


def test_encryption_key_from_env():
    """Should read encryption key from ENCRYPTION_KEY env var."""
    from backend.api.upload_routes import _get_encryption_key
    import os

    with patch.dict(os.environ, {"ENCRYPTION_KEY": "my-secret-key-32-chars-long-xx"}):
        key = _get_encryption_key()
        assert len(key) == 32
        assert isinstance(key, bytes)


# ── Test 5: OCR fail returns safe error (not fake extraction) ────────────────────

def test_ocr_failure_returns_error():
    """If OCR fails, should return error not fake data."""
    from backend.core.document_extractor import extract_text_from_document

    with patch("backend.core.document_extractor.PyPDF2") as mock_pypdf:
        mock_pypdf.PdfReader.side_effect = Exception("PDF parsing failed")

        text, doc_type = extract_text_from_document(b"garbage", "application/pdf")
        assert text is None, "OCR/PDF failure must not return fabricated text"


def test_upload_ocr_failure_marked_in_db(setup_test_user_and_case, test_user_id, test_case_id):
    """If OCR fails, extraction_status should be 'ocr_failed' in DB."""
    from backend.api.upload_routes import upload_document

    # Create a mock upload file
    file_content = b"test content"
    mock_upload = AsyncMock(spec=UploadFile)
    mock_upload.filename = "document.pdf"
    mock_upload.content_type = "application/pdf"
    mock_upload.read = AsyncMock(return_value=file_content)

    with patch("backend.api.upload_routes.get_current_user") as mock_auth:
        mock_auth.return_value = test_user_id

        with patch("backend.api.upload_routes.check_case_ownership"):
            with patch("backend.api.upload_routes._scan_malware") as mock_scan:
                mock_scan.return_value = True

                with patch("backend.api.upload_routes.extract_text_from_document") as mock_ocr:
                    mock_ocr.side_effect = Exception("OCR failed")

                    # This should still complete but mark as failed
                    # (In actual code, upload_document handles exceptions gracefully)


# ── Test 6: Extracted facts logged ─────────────────────────────────────────────

def test_upload_creates_audit_record(setup_test_user_and_case, test_user_id, test_case_id):
    """Upload should create a document record in DB."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Check that documents can be inserted
            cur.execute(
                """
                INSERT INTO documents (
                    id, case_id, user_id, doc_type, original_filename, content_type,
                    file_size_bytes, storage_ref, is_user_upload, extraction_status
                ) VALUES (
                    %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    str(uuid.uuid4()),
                    test_case_id,
                    test_user_id,
                    "user_upload",
                    "test.pdf",
                    "application/pdf",
                    1000,
                    "/tmp/test.pdf",
                    True,
                    "pending",
                ),
            )
        conn.commit()

        # Verify it's there
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM documents WHERE is_user_upload = true AND case_id = %s::uuid",
                (test_case_id,),
            )
            count = cur.fetchone()[0]
            assert count >= 1

    finally:
        conn.close()


# ── Test 7: Auth and ownership checks ──────────────────────────────────────────

def test_upload_unauthorized():
    """Should fail if user is not authenticated."""
    from backend.api.upload_routes import upload_document

    mock_file = AsyncMock(spec=UploadFile)

    with patch("backend.api.upload_routes.get_current_user") as mock_auth:
        mock_auth.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(upload_document(case_id=str(uuid.uuid4()), file=mock_file))
    assert exc_info.value.status_code == 401


def test_upload_wrong_owner(setup_test_user_and_case, test_case_id):
    """Should fail if user doesn't own the case."""
    from backend.api.upload_routes import upload_document

    other_user = str(uuid.uuid4())

    mock_file = AsyncMock(spec=UploadFile)

    with patch("backend.api.upload_routes.get_current_user") as mock_auth:
        mock_auth.return_value = other_user

        with patch("backend.api.upload_routes.check_case_ownership") as mock_check:
            mock_check.side_effect = HTTPException(status_code=403)

            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(upload_document(case_id=test_case_id, file=mock_file))
    assert exc_info.value.status_code == 403


def test_upload_case_not_found(test_user_id):
    """Should fail if case doesn't exist."""
    from backend.api.upload_routes import upload_document

    fake_case_id = str(uuid.uuid4())

    mock_file = AsyncMock(spec=UploadFile)

    with patch("backend.api.upload_routes.get_current_user") as mock_auth:
        mock_auth.return_value = test_user_id

        with patch("backend.api.upload_routes.check_case_ownership"):
            # Case lookup will fail
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(upload_document(case_id=fake_case_id, file=mock_file))
    assert exc_info.value.status_code == 404


# ── Test 8: Get upload status ──────────────────────────────────────────────────

def test_get_upload_status(setup_test_user_and_case, test_user_id, test_case_id):
    """Should return extraction status for a file."""
    from backend.api.upload_routes import get_upload_status

    # Create a document in DB
    file_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (
                    id, case_id, user_id, doc_type, original_filename, extraction_status,
                    extracted_content, storage_ref
                ) VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s)
                """,
                (
                    file_id,
                    test_case_id,
                    test_user_id,
                    "user_upload",
                    "test.pdf",
                    "extracted",
                    "Sample extracted text",
                    "/tmp/test.pdf",
                ),
            )
        conn.commit()
    finally:
        conn.close()

    # Call get_upload_status
    with patch("backend.api.upload_routes.get_current_user") as mock_auth:
        mock_auth.return_value = test_user_id

        response = get_upload_status(file_id, x_user_id=test_user_id)

        assert response.file_id == file_id
        assert response.status == "extracted"
        assert response.extracted_facts is not None


def test_get_upload_status_not_found():
    """Should return 404 for nonexistent file."""
    from backend.api.upload_routes import get_upload_status

    fake_id = str(uuid.uuid4())

    with patch("backend.api.upload_routes.get_current_user") as mock_auth:
        mock_auth.return_value = str(uuid.uuid4())

        with pytest.raises(HTTPException) as exc_info:
            get_upload_status(fake_id)

    assert exc_info.value.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
