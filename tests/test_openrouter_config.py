"""
OpenRouter optional-provider safety tests (Phase 3 config mandate).

Proves: the key is read from the environment; is never returned/logged (only a
bool surfaces); a missing key does NOT crash (graceful local/stub/fail-closed);
.env is gitignored; .env.example carries only a blank placeholder; and no real
OpenRouter key is hardcoded anywhere in the repo.
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.core.agentic import litellm_adapter as A

_REPO = Path(__file__).resolve().parents[1]
_REAL_KEY_PREFIX = "sk-or-v1-"


def test_key_loaded_from_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-fakeloadtest")
    assert A.is_openrouter_configured() is True


def test_missing_key_does_not_crash(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    # must not raise  -  graceful, returns False
    assert A.is_openrouter_configured() is False


def test_placeholder_treated_as_unconfigured(monkeypatch):
    for placeholder in ("", "placeholder", "dummy_test_key", "changeme"):
        monkeypatch.setenv("OPENROUTER_API_KEY", placeholder)
        assert A.is_openrouter_configured() is False


def test_returns_bool_never_the_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-fakevalue123")
    result = A.is_openrouter_configured()
    assert isinstance(result, bool)


def test_key_is_never_logged(monkeypatch, caplog):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-secretloggingcheck")
    with caplog.at_level(logging.DEBUG):
        A.is_openrouter_configured()
    assert "sk-or-v1-secretloggingcheck" not in caplog.text


def test_env_is_gitignored():
    gitignore = (_REPO / ".gitignore").read_text(encoding="utf-8", errors="replace")
    lines = {ln.strip() for ln in gitignore.splitlines()}
    assert ".env" in lines, ".env must be gitignored"


def test_env_example_has_blank_placeholder_only():
    example = (_REPO / ".env.example").read_text(encoding="utf-8", errors="replace")
    found = [ln for ln in example.splitlines() if ln.strip().startswith("OPENROUTER_API_KEY=")]
    assert found, ".env.example must declare OPENROUTER_API_KEY="
    for ln in found:
        value = ln.split("=", 1)[1].strip()
        assert value == "", f".env.example must keep OPENROUTER_API_KEY blank, got {value!r}"
        assert _REAL_KEY_PREFIX not in ln


def test_no_real_openrouter_key_hardcoded_in_repo():
    # Match a REAL key (prefix + long hex) so short test fakes don't trip it,
    # and scan only source/config dirs (fast; skips .git/.venv/caches and .env).
    import re
    real_key = re.compile(r"sk-or-v1-[0-9a-fA-F]{20,}")
    scan_dirs = ["backend", "client", "config", "db", "scripts", "ingestion", ".github"]
    candidates = []
    for d in scan_dirs:
        p = _REPO / d
        if p.exists():
            candidates += [f for f in p.rglob("*") if f.is_file()]
    candidates += [f for f in _REPO.glob("*") if f.is_file()]   # root-level files
    offenders = []
    for path in candidates:
        if "__pycache__" in path.parts or "node_modules" in path.parts:
            continue
        if path.name.startswith(".env"):   # local secrets file is gitignored, excluded
            continue
        if path.suffix.lower() in {".pyc", ".wasm", ".png", ".jpg", ".jpeg", ".ico", ".onnx", ".bin"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if real_key.search(text):
            offenders.append(str(path.relative_to(_REPO)))
    assert not offenders, f"real OpenRouter key found in tracked files: {offenders}"
