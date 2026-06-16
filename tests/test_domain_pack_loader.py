"""Tests for domain pack loader and disk-backed pack discovery."""

from __future__ import annotations

import pytest

from backend.domains.loader import get_domain_pack, list_domain_packs, load_domain_pack, pack_codes
from backend.domains.pack_contract import PackStatus
from backend.domains.registry import sync_registry_from_packs


def test_pack_codes_include_employment_and_stubs():
    codes = pack_codes()
    assert "employment" in codes
    for stub in ("immigration", "housing", "benefits", "debt"):
        assert stub in codes


def test_employment_pack_loads_production_config():
    pack = load_domain_pack("employment")
    assert pack is not None
    assert pack.module_code == "employment"
    assert pack.enabled is True
    assert pack.status == PackStatus.PRODUCTION
    assert pack.retrieval_domain == "employment_uk"
    assert "unfair_dismissal" in pack.enabled_modules


def test_immigration_stub_pack_loads_without_core_changes():
    pack = load_domain_pack("immigration")
    assert pack is not None
    assert pack.enabled is False
    assert pack.status == PackStatus.STUB
    assert pack.enabled_modules == []
    assert pack.is_operational is False


def test_registry_syncs_from_packs():
    sync_registry_from_packs(reload=True)
    from backend.domains.registry import domain_registry, is_domain_enabled

    assert is_domain_enabled("employment")
    assert is_domain_enabled("immigration") is False
    assert set(domain_registry["employment"]["matter_types"]) == set(
        get_domain_pack("employment").enabled_modules
    )


def test_unknown_pack_returns_none():
    assert get_domain_pack("nonexistent_domain_xyz") is None


def test_list_domain_packs_sorted():
    packs = list_domain_packs(reload=True)
    assert len(packs) >= 5
    titles = {p.module_code for p in packs}
    assert "employment" in titles
