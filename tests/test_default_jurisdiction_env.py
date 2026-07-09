from __future__ import annotations

import importlib
import sys

import pytest


MODULE_NAME = "backend.domains.constants"


def _reload_constants(monkeypatch, jurisdiction: str):
    monkeypatch.setenv("LAWAPP_DEFAULT_JURISDICTION", jurisdiction)
    sys.modules.pop(MODULE_NAME, None)
    importlib.invalidate_caches()
    return importlib.import_module(MODULE_NAME)


def test_invalid_default_jurisdiction_raises(monkeypatch):
    monkeypatch.setenv("LAWAPP_DEFAULT_JURISDICTION", "XX")
    sys.modules.pop(MODULE_NAME, None)
    importlib.invalidate_caches()
    with pytest.raises(RuntimeError):
        importlib.import_module(MODULE_NAME)


def test_ew_imports_cleanly(monkeypatch):
    module = _reload_constants(monkeypatch, "EW")
    assert module.DEFAULT_JURISDICTION == "EW"
