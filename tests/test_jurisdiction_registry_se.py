from __future__ import annotations

from backend.core.orchestrator import Orchestrator
from backend.core.retrieve import juris_codes
from backend.domains.registry import jurisdiction_supported, supported_jurisdictions


def test_se_is_not_allowed_by_default(monkeypatch):
    monkeypatch.delenv("LAWAPP_ENABLE_SE", raising=False)
    assert "SE" not in supported_jurisdictions()
    assert jurisdiction_supported("SE") is False
    assert juris_codes("SE") == ("__none__",)


def test_se_is_allowed_when_flag_on(monkeypatch):
    monkeypatch.setenv("LAWAPP_ENABLE_SE", "true")
    assert "SE" in supported_jurisdictions()
    assert jurisdiction_supported("SE") is True
    assert juris_codes("SE") == ("SE",)


def test_orchestrator_jurisdiction_sanitizer_uses_registry(monkeypatch):
    orch = Orchestrator()

    monkeypatch.delenv("LAWAPP_ENABLE_SE", raising=False)
    off = orch.classify("I was dismissed", {"jurisdiction": "SE"})
    assert off["jurisdiction"] == "EW"

    monkeypatch.setenv("LAWAPP_ENABLE_SE", "true")
    on = orch.classify("I was dismissed", {"jurisdiction": "SE"})
    assert on["jurisdiction"] == "SE"
