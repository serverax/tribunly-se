"""Feature Spec integration routes (Wave 1 scaffolding)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_knowledge_modules_route(client):
    with patch("backend.core.feature_spec_service.get_connection") as mock_conn:
        conn = mock_conn.return_value
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value = [
            ("unfair_dismissal", "Unfair dismissal", "production", 12),
        ]
        resp = client.get("/api/features/knowledge/modules")
    assert resp.status_code == 200
    body = resp.json()
    assert body["module_count"] >= 1
    assert "beta_scope_note" in body


def test_claim_assessment_anonymous(client):
    with patch("backend.core.feature_spec_service.tools.check_claim") as mock_check:
        mock_check.return_value = {
            "has_claim": True,
            "confidence": 0.7,
            "explanation": "Possible unfair dismissal indicators.",
            "signals": ["unfair_dismissal"],
            "preview": True,
        }
        resp = client.post(
            "/api/features/claim-assessment",
            json={"facts": "I was dismissed after three years"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_claim"] is True
    assert "strength_score" in data
    assert data.get("verification_badge") == "preview"


def test_document_decode_anonymous(client):
    with patch("backend.core.retrieve.hybrid_search", return_value=[]):
        resp = client.post(
            "/api/features/document-decode",
            json={"text": "Your employment is terminated effective immediately.", "doc_type": "letter"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["persisted"] is False
    assert isinstance(data["sections"], list)
    assert len(data["sections"]) >= 1


def test_strength_preview_route(client):
    with patch("backend.core.feature_spec_service.tools.check_claim") as mock_check:
        mock_check.return_value = {
            "has_claim": True,
            "confidence": 0.6,
            "explanation": "Signals present.",
            "signals": ["unfair_dismissal"],
        }
        resp = client.post(
            "/api/features/strength",
            json={"facts": "dismissed unfairly"},
        )
    assert resp.status_code == 200
    assert resp.json().get("full_rationale_gated") is True
