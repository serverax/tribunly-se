"""
PII boundary tests for the LiteLLM adapter (Phase 2, AC-007/008/013).

The adapter is the absolute chokepoint that runs BEFORE any OpenRouter call:
raw National Insurance numbers, UK postcodes/addresses, emails and phones are
SCRUBBED (replaced with placeholders, content preserved) so no raw PII can leave
the building; if scrubbing fails or any PII survives, the call FAILS CLOSED.
"""

from __future__ import annotations

import json

import pytest

from backend.core.agentic import litellm_adapter as A
from backend.core.agentic import pii as PII
from backend.core.agentic.errors import PIIBoundaryViolation, PolicyViolation
from backend.core.agentic.schemas import AEEOutput, AgentName

_CLOUD_ROUTE = "lawapp-reasoning-heavy"


def _dump(d):
    return json.dumps(d, ensure_ascii=False)


def test_ni_number_scrubbed_not_leaked():
    out = A._pii_chokepoint({"raw_text": "Employee NI AB123456C dismissed on 2026-05-10"})
    s = _dump(out)
    assert "AB123456C" not in s
    assert "[NINO_REDACTED]" in s
    assert "dismissed on 2026-05-10" in s   # non-PII content preserved


def test_postcode_address_scrubbed():
    out = A._pii_chokepoint({"raw_text": "I live at 12 Foo Street, Bradford BD1 1AB"})
    s = _dump(out)
    assert "BD1 1AB" not in s
    assert "[POSTCODE_REDACTED]" in s


def test_email_and_phone_scrubbed():
    out = A._pii_chokepoint({"raw_text": "email jane.doe@example.co.uk or call 07911123456"})
    s = _dump(out)
    assert "jane.doe@example.co.uk" not in s and "07911123456" not in s
    assert "[EMAIL_REDACTED]" in s and "[PHONE_REDACTED]" in s


def test_clean_payload_preserved():
    out = A._pii_chokepoint({"reason_for_dismissal": "conduct", "weekly_pay": 700})
    assert out["reason_for_dismissal"] == "conduct"
    assert out["weekly_pay"] == 700
    assert PII.residual_pii(out) is None


def test_fail_closed_if_scrubber_errors(monkeypatch):
    def _boom(_p):
        raise RuntimeError("scrubber down")
    monkeypatch.setattr(PII, "scrub_payload", _boom)
    with pytest.raises(PIIBoundaryViolation):
        A._pii_chokepoint({"raw_text": "anything"})


def test_fail_closed_if_pii_survives(monkeypatch):
    # Simulate a scrubber that fails to redact -> residual gate must fail closed.
    monkeypatch.setattr(PII, "scrub_payload", lambda p: p)
    with pytest.raises(PIIBoundaryViolation):
        A._pii_chokepoint({"raw_text": "NI AB123456C"})


def test_call_model_cloud_payload_is_scrubbed_before_send(monkeypatch):
    # call_model must scrub at the chokepoint; capture what would be sent and
    # prove no raw PII is present (the model itself is never reached here because
    # litellm import fails closed in the test image).
    captured = {}
    real = A._pii_chokepoint

    def _spy(p):
        out = real(p)
        captured["payload"] = out
        return out
    monkeypatch.setattr(A, "_pii_chokepoint", _spy)

    with pytest.raises((PolicyViolation, Exception)):
        A.call_model(
            agent_name=AgentName.AEE, model_route=_CLOUD_ROUTE,
            system_prompt="extract", payload={"raw_text": "AB123456C lives at BD1 1AB"},
            response_schema=AEEOutput, trace_id="11111111-1111-1111-1111-111111111111",
            case_id="case-1", allow_cloud=True,
        )
    s = _dump(captured["payload"])
    assert "AB123456C" not in s and "BD1 1AB" not in s   # nothing raw would be sent


def test_call_model_cloud_disabled_by_default():
    with pytest.raises(PolicyViolation):
        A.call_model(
            agent_name=AgentName.AEE, model_route=_CLOUD_ROUTE,
            system_prompt="x", payload={"reason_for_dismissal": "conduct"},
            response_schema=AEEOutput, trace_id="11111111-1111-1111-1111-111111111111",
            case_id="case-1", allow_cloud=False,
        )
