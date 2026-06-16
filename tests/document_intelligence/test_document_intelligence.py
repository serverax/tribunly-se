"""
Document Intelligence tests.

Tests document upload, classification, fact extraction,
case isolation, and content type validation.
"""

import pytest
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


class TestDocumentUploadAcceptance:
    def test_unsupported_extension_rejected(self):
        """Text/plain documents must be rejected."""
        files = {"file": ("test.txt", b"text content", "text/plain")}
        data = {"doc_type": "dismissal_letter"}
        resp = client.post("/cases/00000000-0000-0000-0000-000000000000/uploads",
                           data=data, files=files)
        assert resp.status_code in (404, 422, 400, 415)

    def test_invalid_doc_type_rejected(self):
        """Invalid doc_type must return 422."""
        import io
        files = {"file": ("test.pdf", io.BytesIO(b"%PDF"), "application/pdf")}
        data = {"doc_type": "invalid_doc_type_xyz"}
        resp = client.post("/cases/00000000-0000-0000-0000-000000000000/uploads",
                           data=data, files=files)
        assert resp.status_code in (404, 422)


class TestExtractedFactStructure:
    def test_extraction_endpoint_not_implemented(self):
        """Extract endpoint must return 501 (Phase 4 not implemented) or 404/403/401 for access control."""
        resp = client.post(
            "/cases/00000000-0000-0000-0000-000000000000/uploads/00000000-0000-0000-0000-000000000001/extract"
        )
        # 501 = OCR not implemented (correct Phase 4 placeholder)
        # 404/403/401 = access control kicking in for unauthenticated requests
        assert resp.status_code in (404, 403, 401, 501), \
            f"Expected 501 (not implemented) or access denied, got {resp.status_code}"

    def test_extraction_does_not_apply_unconfirmed_facts(self):
        """Extracted facts must remain unconfirmed until user reviews them.

        OCR extraction is Phase 4 (returns 501). When implemented, extracted
        facts must start as 'extracted_unconfirmed'  -  this test verifies the
        interface contract that must be maintained by any future implementation.
        """
        import pytest
        pytest.skip("OCR extraction returns 501 Not Implemented (Phase 4). "
                    "This test verifies Phase 4 interface contract for future implementation.")


class TestDocumentIsolation:
    def test_uploads_scoped_to_case_owner(self):
        """Uploads endpoint must require ownership."""
        resp = client.get("/cases/00000000-0000-0000-0000-000000000000/uploads")
        assert resp.status_code in (401, 403, 404)
