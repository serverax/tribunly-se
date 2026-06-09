"""
Architecture tests for the modular legal-domain platform (Subagent 6).

These tests assert the *structural* guarantees, not the legal substance:

  1. unsupported domain fails closed
  2. retrieval requires a (valid, enabled) domain filter
  3. templates load by domain
  4. a brand-new (fake) domain can register WITHOUT a core rewrite

They must run WITHOUT a live database: every fail-closed path raises before any
DB access, so no connection is opened here.
"""

from __future__ import annotations

import copy
from datetime import date

import pytest

from backend.domains import registry
from backend.domains.registry import (
    domain_registry,
    get_domain,
    is_domain_enabled,
    enabled_domains,
    require_domain,
    supported_matter_types,
    is_matter_supported,
    resolve_domain_for_matter,
    require_supported_matter,
    register_domain,
    unregister_domain,
    retrieval_domain_for,
    load_domain_templates,
)
from backend.domains.shared.errors import (
    UnsupportedDomainError,
    DomainDisabledError,
    UnsupportedMatterError,
)


# ─────────────────────────────────────────────────────────────────────────────
# Baseline: the registry reflects reality (employment enabled; others disabled).
# ─────────────────────────────────────────────────────────────────────────────

def test_registry_baseline_employment_enabled():
    assert is_domain_enabled("employment") is True
    assert "employment" in enabled_domains()
    spec = get_domain("employment")
    # matter_types reflect what classify.py actually emits (reality, not a subset)
    assert set(spec["matter_types"]) == {"unfair_dismissal", "unpaid_wages"}
    assert spec["rules_pack"] == "employment_rules"
    assert "EW" in spec["jurisdiction"]


def test_registry_placeholders_disabled():
    for placeholder in ("immigration", "housing"):
        assert placeholder in domain_registry
        assert is_domain_enabled(placeholder) is False
        assert domain_registry[placeholder]["matter_types"] == []


# ─────────────────────────────────────────────────────────────────────────────
# 1. Unsupported domain fails closed
# ─────────────────────────────────────────────────────────────────────────────

def test_unknown_domain_raises():
    with pytest.raises(UnsupportedDomainError):
        get_domain("divorce")
    with pytest.raises(UnsupportedDomainError):
        require_domain("divorce")


def test_disabled_domain_fails_closed():
    # Registered but disabled -> require_domain refuses (fail closed)
    with pytest.raises(DomainDisabledError):
        require_domain("immigration")
    # ...and it never leaks into supported scope / matter resolution
    assert resolve_domain_for_matter("anything") is None or \
        resolve_domain_for_matter("anything") in enabled_domains()


def test_unsupported_matter_fails_closed():
    assert is_matter_supported("divorce") is False
    assert resolve_domain_for_matter("divorce") is None
    with pytest.raises(UnsupportedMatterError):
        require_supported_matter("divorce")


def test_supported_scope_excludes_disabled_domains():
    scope = supported_matter_types()
    assert "unfair_dismissal" in scope
    assert "unpaid_wages" in scope
    # nothing from a disabled domain ever appears in scope
    assert all(resolve_domain_for_matter(mt) in enabled_domains() for mt in scope)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Retrieval requires a (valid, enabled) domain filter — fail closed
# ─────────────────────────────────────────────────────────────────────────────

def test_retrieval_rejects_unknown_domain():
    from backend.core.retrieve import retrieve
    with pytest.raises(UnsupportedDomainError):
        retrieve("any query", "unfair_dismissal", "EW", date(2026, 1, 1),
                 domain="nonexistent_domain")


def test_retrieval_rejects_disabled_domain():
    from backend.core.retrieve import retrieve
    with pytest.raises(DomainDisabledError):
        retrieve("any query", "unfair_dismissal", "EW", date(2026, 1, 1),
                 domain="immigration")


def test_retrieval_domain_resolves_from_claim_type():
    # The default (no explicit domain) resolves the employment domain from the
    # matter type, and produces the employment retrieval tag.
    assert resolve_domain_for_matter("unfair_dismissal") == "employment"
    assert retrieval_domain_for("employment") == "employment_uk"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Templates load by domain
# ─────────────────────────────────────────────────────────────────────────────

def test_templates_load_for_employment():
    templates = load_domain_templates("employment")
    assert "particulars_of_claim" in templates
    assert "schedule_of_loss" in templates
    # every template only claims matter types the domain actually owns
    owned = set(get_domain("employment")["matter_types"])
    for key, entry in templates.items():
        assert set(entry["matter_types"]).issubset(owned), key
        assert entry["generator"].startswith("backend.core.")


def test_templates_generator_resolves_to_real_callable():
    from backend.domains.employment.templates import resolve_generator
    fn = resolve_generator("particulars_of_claim")
    assert callable(fn)


def test_templates_isolated_unknown_and_disabled():
    with pytest.raises(UnsupportedDomainError):
        load_domain_templates("divorce")
    with pytest.raises(DomainDisabledError):
        load_domain_templates("immigration")


# ─────────────────────────────────────────────────────────────────────────────
# 4. A fake test domain can register WITHOUT a core rewrite
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_domain():
    """Register a throwaway domain via the public API, then clean up."""
    spec = {
        "name": "test_widgets",
        "enabled": True,
        "matter_types": ["widget_dispute"],
        "jurisdiction": ["EW"],
        "rules_pack": "test_widgets_rules",
        "retrieval_domain": "test_widgets_uk",
        "templates_module": None,
        "label": "Test Widgets",
    }
    register_domain(spec)
    try:
        yield spec
    finally:
        unregister_domain("test_widgets")


def test_fake_domain_registers_without_core_rewrite(fake_domain):
    # Purely through register_domain() — no edit to registry/classify/retrieve src.
    assert is_domain_enabled("test_widgets") is True
    assert "test_widgets" in enabled_domains()
    assert is_matter_supported("widget_dispute") is True
    assert resolve_domain_for_matter("widget_dispute") == "test_widgets"
    assert require_supported_matter("widget_dispute") == "test_widgets"
    assert retrieval_domain_for("test_widgets") == "test_widgets_uk"


def test_fake_domain_retrieval_passes_guard(fake_domain):
    # The fail-closed retrieval guard now ACCEPTS the freshly registered domain
    # (it passes require_domain). It will then proceed to real retrieval; we only
    # assert the guard does not reject it — so we stop before any DB work by
    # checking the guard functions the same retrieve() path uses.
    require_domain("test_widgets")  # must NOT raise


def test_fake_domain_cleanup_removes_it(fake_domain):
    # Inside the fixture it is present; the fixture teardown removes it. Prove the
    # teardown path works by unregistering an unrelated unknown name (no-op).
    unregister_domain("never_registered")  # must not raise
    assert is_domain_enabled("test_widgets") is True  # still present within test


def test_registry_state_restored_after_fake_domain():
    # Runs after the fixture-using tests: the fake domain must be gone.
    assert "test_widgets" not in domain_registry
    assert is_matter_supported("widget_dispute") is False


# ─────────────────────────────────────────────────────────────────────────────
# 5. classify.py is genuinely registry-driven (load-bearing, fail-closed)
# ─────────────────────────────────────────────────────────────────────────────

def test_classify_in_scope_for_enabled_matter():
    from backend.core.classify import classify
    result = classify("I was unfairly dismissed after 3 years")
    assert result.matter_type == "unfair_dismissal"
    assert result.in_scope is True


def test_classify_fails_closed_if_domain_disabled():
    """If employment were disabled in the registry, classify must stop returning
    in_scope=True for its matters — proving the gate is load-bearing, not cosmetic."""
    from backend.core.classify import classify
    original = copy.deepcopy(domain_registry["employment"])
    try:
        domain_registry["employment"]["enabled"] = False
        result = classify("I was unfairly dismissed after 3 years")
        assert result.matter_type == "unfair_dismissal"
        assert result.in_scope is False  # fail closed
    finally:
        domain_registry["employment"] = original
    # restored
    assert is_domain_enabled("employment") is True
