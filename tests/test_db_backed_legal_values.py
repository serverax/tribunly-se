from datetime import date

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.models import StubReasoningModel
from shared.schemas import ClassificationResult, RetrievalBundle


client = TestClient(app)


def test_pipeline_fails_closed_when_time_limit_rule_missing(monkeypatch):
    from backend.core import pipeline

    monkeypatch.setattr(
        pipeline,
        "classify",
        lambda _query, _facts: ClassificationResult(
            matter_type="unfair_dismissal",
            intent="diagnosis",
            in_scope=True,
        ),
    )
    monkeypatch.setattr("backend.core.retrieve.jurisdiction_supported", lambda _jurisdiction: True)
    monkeypatch.setattr(
        pipeline,
        "retrieve",
        lambda *_args, **_kwargs: RetrievalBundle(
            exact_rules=[],
            authorities=[{"cite": "ERA 1996 s.94", "url": "https://example.invalid"}],
            insufficient_grounding=False,
        ),
    )

    result = pipeline.assess(
        "I was unfairly dismissed",
        {"edt": date(2026, 5, 1).isoformat(), "service_start_date": "2020-01-01"},
        model=StubReasoningModel(),
    )

    assert result["status"] == "insufficient_grounding"
    assert "unfair_dismissal.time_limit_months" in result["reason"]


def test_deadline_endpoint_fails_closed_when_time_limit_rule_missing(monkeypatch):
    monkeypatch.setattr("backend.core.retrieve.retrieve_rules", lambda *_args, **_kwargs: [])

    resp = client.post(
        "/api/deadline/calculate",
        json={"claim_type": "unfair_dismissal", "edt": "2026-05-01", "jurisdiction": "EW"},
    )

    assert resp.status_code == 422
    assert "time_limit_months" in resp.text
