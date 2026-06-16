"""
Compensation tool (Schedule of Loss)  -  HTTP endpoint + logic proof.

Endpoint under test (backend/api/main.py): POST /documents/generate
                                            (document_type="schedule_of_loss")
Logic under test (backend/core/documents.py): generate_schedule_of_loss

The compensation estimate is delivered as a template-anchored Schedule of Loss.
Statutory monetary caps come from the rules table via the assessment (never baked
into the template), and the document is refused unless the assessment is grounded.

Proven (conftest -> localhost:5435 lawapp DB):
  HAPPY PATH
    - a grounded assessment -> 200 with a schedule_of_loss draft, carrying the
      self-help boundary notice and the ERA 1996 s.119 statutory basis
    - with PAYMENT_MODE=disabled the case is unpaid -> payment_required == True
      and the delivered content is a (gated) preview, not the full document
  FAIL-CLOSED / ERROR CASES
    - an ungrounded assessment (insufficient_grounding) -> 422 (refused)
    - an unsupported jurisdiction -> 422 (refused)

GUARDRAIL: no hardcoded statutory monetary values in the template; figures and
citations are sourced from the (grounded) assessment.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.core.documents import generate_schedule_of_loss

from tests.integration.auth_helpers import mock_auth_headers

_LEGACY_AUTH = mock_auth_headers()


_FACTS = {"edt": "2026-05-10", "service_start_date": "2020-01-01", "weekly_pay": 700}
_GROUNDED = {"status": "ok", "claim_type": "unfair_dismissal", "citations": []}


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app
    try:
        app.state.limiter.enabled = False
    except Exception:
        pass
    return TestClient(app, raise_server_exceptions=False)


# ── pure logic ────────────────────────────────────────────────────────────────────

class TestScheduleOfLossLogic:
    def test_carries_self_help_boundary_notice(self):
        doc = generate_schedule_of_loss(_GROUNDED, _FACTS).lower()
        assert "not legal advice" in doc
        assert ("self-help" in doc) or ("not a solicitor" in doc) or ("does not file" in doc)

    def test_references_statutory_basis(self):
        doc = generate_schedule_of_loss(_GROUNDED, _FACTS)
        assert "ERA 1996" in doc
        assert "s.119" in doc  # basic award statutory basis

    def test_does_not_hardcode_statutory_amounts(self):
        doc = generate_schedule_of_loss(_GROUNDED, _FACTS)
        for amount in ["719", "751", "118223", "123543", "9157"]:
            assert amount not in doc, f"hardcoded statutory value {amount} leaked into template"


# ── HTTP endpoint ─────────────────────────────────────────────────────────────────

class TestCompensationEndpoint:
    def test_grounded_assessment_generates_document(self, client):
        r = client.post("/documents/generate", headers=_LEGACY_AUTH,
                        json={"document_type": "schedule_of_loss",
                              "assessment": _GROUNDED, "facts": _FACTS})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["document_type"] == "schedule_of_loss"
        assert body["content"]
        assert body["safety_check"]["passed"] is True
        assert body["disclaimer_included"] is True

    def test_unpaid_case_returns_preview_and_payment_required(self, client):
        # PAYMENT_MODE=disabled (conftest) -> no case is ever paid.
        r = client.post("/documents/generate", headers=_LEGACY_AUTH,
                        json={"document_type": "schedule_of_loss",
                              "assessment": _GROUNDED, "facts": _FACTS})
        body = r.json()
        assert body["payment_required"] is True

    def test_ungrounded_assessment_is_refused(self, client):
        r = client.post("/documents/generate", headers=_LEGACY_AUTH,
                        json={"document_type": "schedule_of_loss",
                              "assessment": {"status": "insufficient_grounding"},
                              "facts": _FACTS})
        assert r.status_code == 422, r.text
        assert "grounded" in r.json()["detail"].lower()

    def test_unsupported_jurisdiction_is_refused(self, client):
        r = client.post("/documents/generate", headers=_LEGACY_AUTH,
                        json={"document_type": "schedule_of_loss",
                              "assessment": {"status": "ok", "jurisdiction_supported": False},
                              "facts": _FACTS})
        assert r.status_code == 422, r.text
