"""Assert no third-party translation API is used in language layer."""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_PATTERNS = (
    "googletrans",
    "translate.googleapis",
    "deepl",
    "azure.cognitiveservices.speech.translation",
    "amazontranslate",
    "libretranslate",
)


def _py_files_under(root: Path):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def test_language_engine_has_no_translate_imports():
    root = Path(__file__).resolve().parents[1] / "backend" / "language_engine"
    hits: list[str] = []
    for path in _py_files_under(root):
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        for pat in FORBIDDEN_PATTERNS:
            if pat in lower:
                hits.append(f"{path}:{pat}")
    assert hits == [], f"translation API references found: {hits}"


def test_language_engine_modules_do_not_define_translate_functions():
    root = Path(__file__).resolve().parents[1] / "backend" / "language_engine"
    for path in _py_files_under(root):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and "translate" in node.name.lower():
                raise AssertionError(f"translate-like function in {path}: {node.name}")
