"""
Ingestion-only write guard for core legal knowledge tables.

GUARDRAIL (Rule 3): Only ingestion pipelines and migrations may INSERT/UPDATE:
  - rules
  - legislation
  - case_law_documents / case_law_chunks
  - knowledge.legal_source, knowledge.provision
  - corpus_chunks (via ingestion embed path)

Allowed application writers:
  - ingestion/db.py (upsert_rule, upsert_legislation, ...)
  - ingestion/* job modules
  - db/migrations/*

Brain, pipeline, and API layers are read-only for these tables.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

# Functions that perform direct knowledge-table writes (ingestion layer only).
INGESTION_WRITE_FUNCTIONS = frozenset({
    "upsert_rule",
    "upsert_legislation",
    "upsert_acas_guidance",
    "upsert_corpus_chunk",
    "insert_case_law_document",
})

# Runtime modules that must never call ingestion write helpers.
BRAIN_PATH_MODULES = (
    "backend.core.brain",
    "backend.core.pipeline",
    "backend.core.legal_truth_validator",
    "backend.core.knowledge_proposer",
)

_FORBIDDEN_SQL_PATTERNS = (
    "INSERT INTO rules",
    "UPDATE rules",
    "INSERT INTO legislation",
    "UPDATE legislation",
    "INSERT INTO case_law",
    "INSERT INTO knowledge.provision",
    "INSERT INTO knowledge.legal_source",
)


def _module_imports_forbidden(name: str) -> list[str]:
    """Return forbidden ingestion write symbols imported by module."""
    try:
        mod = importlib.import_module(name)
        source_path = getattr(mod, "__file__", None)
        if not source_path:
            return []
        tree = ast.parse(Path(source_path).read_text(encoding="utf-8"))
    except Exception:
        return []

    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if "ingestion.db" in node.module or node.module.endswith("ingestion.db"):
                for alias in node.names:
                    if alias.name in INGESTION_WRITE_FUNCTIONS:
                        hits.append(f"{name} imports {alias.name} from {node.module}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "ingestion.db":
                    hits.append(f"{name} imports ingestion.db")
    return hits


def assert_brain_path_cannot_write_knowledge() -> None:
    """
    Test helper: brain/pipeline path must not import ingestion write functions.

    Raises AssertionError if a forbidden import is detected.
    """
    violations: list[str] = []
    for mod_name in BRAIN_PATH_MODULES:
        violations.extend(_module_imports_forbidden(mod_name))
    if violations:
        raise AssertionError(
            "Brain path must not import ingestion write functions: "
            + "; ".join(violations)
        )


def scan_module_for_direct_sql_writes(module_name: str) -> list[str]:
    """Detect raw SQL write patterns in a module source (static scan)."""
    try:
        mod = importlib.import_module(module_name)
        source_path = getattr(mod, "__file__", None)
        if not source_path:
            return []
        text = Path(source_path).read_text(encoding="utf-8")
    except Exception:
        return []
    if module_name.startswith("ingestion."):
        return []
    hits = []
    for pattern in _FORBIDDEN_SQL_PATTERNS:
        if pattern in text:
            hits.append(f"{module_name} contains {pattern!r}")
    return hits
