"""Architecture guardrails for domain plugin system v1."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.domains.constants import DOMAIN_DEFAULT
from backend.domains.loader import load_domain_pack
from backend.domains.registry import sync_registry_from_packs


_REPO = Path(__file__).resolve().parents[1]
_CORE_FILES = (
    _REPO / "backend" / "core" / "brain.py",
    _REPO / "backend" / "core" / "orchestrator.py",
    _REPO / "backend" / "core" / "control_plane" / "mother_controller.py",
)

_ALLOWED_EMPLOYMENT_PATTERNS = (
    re.compile(r"DOMAIN_DEFAULT"),
    re.compile(r"employment_law"),  # legal area label from classifier, not pack logic
    re.compile(r"backend\.domains\.employment\."),  # domain pack implementation imports
    re.compile(r"from backend\.domains\.employment"),
    re.compile(r"resolve_domain_for_matter"),
    re.compile(r"get_domain_plugin"),
    re.compile(r"#.*employment"),
    re.compile(r'"""[\s\S]*employment[\s\S]*"""'),
    re.compile(r"employment_uk"),  # retrieval tag from pack config
)


def _is_allowed_employment_line(line: str) -> bool:
    if "employment" not in line.lower():
        return True
    return any(p.search(line) for p in _ALLOWED_EMPLOYMENT_PATTERNS)


def test_core_orchestration_avoids_hardcoded_domain_literals():
    offenders: list[str] = []
    for path in _CORE_FILES:
        text = path.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if '"employment"' in stripped or "'employment'" in stripped:
                if DOMAIN_DEFAULT in stripped:
                    continue
                if not _is_allowed_employment_line(line):
                    offenders.append(f"{path.relative_to(_REPO)}:{idx}: {stripped}")
    assert offenders == [], "Hardcoded employment domain literals:\n" + "\n".join(offenders)


def test_immigration_pack_loads_without_registry_code_edit():
    sync_registry_from_packs(reload=True)
    pack = load_domain_pack("immigration")
    assert pack is not None
    assert pack.status.value == "stub"
    from backend.domains.registry import get_domain, is_domain_enabled

    spec = get_domain("immigration")
    assert spec["enabled"] is False
    assert is_domain_enabled("immigration") is False


def test_domain_default_is_employment():
    assert DOMAIN_DEFAULT == "employment"
