"""Architecture gate: single Brain runtime; no LangGraph bypass paths."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo_py_files() -> list[Path]:
    skip_dirs = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
    }
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*.py"):
        if any(part in skip_dirs for part in path.parts):
            continue
        files.append(path)
    return files


def test_brain_module_exists_and_exports_run_brain():
    brain_path = REPO_ROOT / "backend" / "core" / "brain.py"
    assert brain_path.is_file(), "backend/core/brain.py must exist as the single reasoning runtime"
    from backend.core.brain import run_brain, BRAIN_STEPS

    assert callable(run_brain)
    assert len(BRAIN_STEPS) == 19


@pytest.mark.parametrize(
    "forbidden_path",
    [
        REPO_ROOT / "backend" / "ai",
        REPO_ROOT / "backend" / "core" / "langgraph",
        REPO_ROOT / "backend" / "api" / "legal_reason_routes.py",
        REPO_ROOT / "tests" / "test_langgraph_legal_reason.py",
        REPO_ROOT / "tests" / "test_legal_reason_api.py",
    ],
)
def test_langgraph_artifacts_absent(forbidden_path: Path):
    assert not forbidden_path.exists(), f"Forbidden LangGraph artifact present: {forbidden_path}"


def test_main_does_not_register_legal_reason_router():
    main_src = (REPO_ROOT / "backend" / "api" / "main.py").read_text(encoding="utf-8")
    assert "legal_reason_routes" not in main_src
    assert "/api/v1/legal/reason" not in main_src
    assert "/api/legal/reason" not in main_src
    assert "langgraph" not in main_src.lower()


def test_assess_route_delegates_to_brain_runtime():
    """POST /assess must reach Brain (via MotherController), not LangGraph."""
    main_src = (REPO_ROOT / "backend" / "api" / "main.py").read_text(encoding="utf-8")
    assert '@app.post("/assess")' in main_src
    assert "MotherController" in main_src

    mother_src = (
        REPO_ROOT / "backend" / "core" / "control_plane" / "mother_controller.py"
    ).read_text(encoding="utf-8")
    assert "from backend.core.brain import orchestrator" in mother_src


def test_pyproject_has_no_langgraph_dependency():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    assert "langgraph" not in pyproject
    assert "langchain-core" not in pyproject


def test_dockerfile_has_no_langgraph_dependency():
    dockerfile_path = REPO_ROOT / "Dockerfile"
    if not dockerfile_path.exists():
        pytest.skip("Dockerfile not mounted in container — checked at build time")
    dockerfile = dockerfile_path.read_text(encoding="utf-8").lower()
    assert "langgraph" not in dockerfile
    assert "langchain-core" not in dockerfile


def test_no_langgraph_imports_in_backend():
    backend_root = REPO_ROOT / "backend"
    offenders: list[str] = []
    for path in backend_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "langgraph" in text.lower() or "backend.ai.graph" in text or "backend.core.langgraph" in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"LangGraph references in backend: {offenders}"


def test_no_legal_reason_route_strings_in_backend_api():
    api_root = REPO_ROOT / "backend" / "api"
    hits: list[str] = []
    for path in api_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "legal/reason" in text or "legal_reason_routes" in text:
            hits.append(str(path.relative_to(REPO_ROOT)))
    assert not hits, f"legal/reason route references in backend/api: {hits}"


def test_brain_docstring_declares_single_entry_guardrail():
    brain_path = REPO_ROOT / "backend" / "core" / "brain.py"
    tree = ast.parse(brain_path.read_text(encoding="utf-8"))
    doc = ast.get_docstring(tree) or ""
    assert "ONLY authorised entry" in doc or "ONLY authorized entry" in doc
    assert "Brain" in doc
