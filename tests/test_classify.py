"""
Tests for the classification module.

No DB, no model, no network. Pure keyword rules.
Covers: in-scope UD, out-of-scope, intent detection, ambiguous.
"""

from backend.core.classify import classify


# ── In-scope unfair dismissal ─────────────────────────────────────────────────

def test_clear_ud_dismissed():
    r = classify("I was dismissed from my job last week")
    assert r.in_scope is True
    assert r.matter_type == "unfair_dismissal"
    assert r.intent == "diagnosis"

def test_clear_ud_sacked():
    r = classify("I got sacked without any warning or process")
    assert r.in_scope is True
    assert r.matter_type == "unfair_dismissal"

def test_clear_ud_constructive():
    r = classify("My employer made my life so difficult I had to resign  -  constructive dismissal")
    assert r.in_scope is True
    assert r.matter_type == "unfair_dismissal"

def test_ud_with_facts_dict():
    r = classify("employment ended", {"reason_for_dismissal": "conduct", "edt": "2026-05-01"})
    assert r.in_scope is True
    assert r.matter_type == "unfair_dismissal"

def test_deadline_intent():
    r = classify("I was dismissed  -  what's my deadline to claim?")
    assert r.in_scope is True
    assert r.matter_type == "unfair_dismissal"
    assert r.intent == "deadline_check"

def test_document_intent():
    r = classify("I need to prepare particulars of claim for my dismissal")
    assert r.in_scope is True
    assert r.matter_type == "unfair_dismissal"
    assert r.intent == "document"


# ── Out-of-scope ──────────────────────────────────────────────────────────────

def test_oos_tenancy():
    r = classify("My landlord wants to evict me  -  can they do this?")
    assert r.in_scope is False

def test_oos_divorce():
    r = classify("I want to divorce my husband and need help with custody")
    assert r.in_scope is False

def test_oos_criminal():
    r = classify("I got arrested for speeding  -  what are my rights?")
    assert r.in_scope is False

def test_oos_immigration():
    r = classify("My visa has expired and I need advice on immigration")
    assert r.in_scope is False

def test_oos_tax():
    r = classify("I have a problem with my tax return and HMRC")
    assert r.in_scope is False

def test_oos_returns_not_supported_type():
    r = classify("I want to return a faulty TV I bought last month")
    assert r.in_scope is False
    # Must not guess at UD
    assert r.matter_type != "unfair_dismissal"


# ── Mixed signals (OOS + UD)  -  UD should win ─────────────────────────────────

def test_mixed_ud_wins_over_oos():
    # Both tenancy and dismissal mentioned  -  UD keywords present, should be in-scope
    r = classify("I was dismissed from my job and now I can't pay my rent")
    assert r.in_scope is True
    assert r.matter_type == "unfair_dismissal"


# ── Ambiguous ─────────────────────────────────────────────────────────────────

def test_ambiguous_returns_not_in_scope():
    # Generic query with no domain signals  -  should not guess in_scope=True.
    # Phase 8B: Stage B ML model may return "out_of_scope" when configured;
    # without a model key, returns "ambiguous". Both are correct rejections.
    r = classify("I need some legal advice please")
    assert r.in_scope is False
    assert r.matter_type in ("ambiguous", "out_of_scope")
