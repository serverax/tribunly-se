"""Focused tests for the 5 critical beta blockers (2026-06-11 beta QA).

1. Day-one / automatic-unfair rights detection on short service
2. Deadline-passed / urgency warnings on /assess
3. Deterministic-first response timing (no model wait)
4. Pricing consistency (homepage vs checkout)
5. Future / impossible / malformed date rejection (field-level)
"""
from __future__ import annotations

import pathlib
import re
import time
from datetime import date, timedelta

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)
ROOT = pathlib.Path(__file__).resolve().parent.parent


def _assess(facts: dict, query: str = "Assessment request", use_model: bool = False) -> dict:
    r = client.post("/assess", json={"query": query, "facts": facts,
                                     "jurisdiction": "EW", "use_model": use_model})
    assert r.status_code == 200, r.text
    return r.json()


def _ud_facts(**kw) -> dict:
    base = {"jurisdiction": "EW", "acas_not_started": True,
            "reason_for_dismissal": "conduct", "was_procedure_followed": False,
            "weekly_pay": 600}
    base.update(kw)
    return base


# ── 1. Day-one rights detection ───────────────────────────────────────────────

def test_pregnancy_short_service_not_told_no_claim():
    """13 months service + maternity mention must NOT return viable=no."""
    edt = (date.today() - timedelta(days=20)).isoformat()
    start = (date.today() - timedelta(days=420)).isoformat()
    d = _assess(_ud_facts(edt=edt, service_start_date=start, reason_for_dismissal="other"),
                "I was dismissed days after announcing my maternity leave.")
    assert d["status"] == "ok", d
    assert d.get("has_viable_claim") != "no", \
        "pregnancy/maternity claimant wrongly told 'no claim' on short service"
    assert d.get("day_one_exception_possible") is True
    assert d["day_one_exception"]["authority"] == "ERA 1996 s.99"
    joined = " ".join(d.get("key_weaknesses", []))
    assert "day-one exception" in joined.lower()
    assert "do not be discouraged" in joined.lower()


def test_whistleblowing_short_service_not_told_no_claim():
    edt = (date.today() - timedelta(days=15)).isoformat()
    start = (date.today() - timedelta(days=300)).isoformat()
    d = _assess(_ud_facts(edt=edt, service_start_date=start, reason_for_dismissal="other"),
                "I reported safety breaches to the HSE and was dismissed two weeks later.")
    assert d.get("has_viable_claim") != "no"
    assert d.get("day_one_exception_possible") is True


def test_plain_short_service_still_says_no():
    """No day-one indicators: the honest 'no' verdict must be unchanged."""
    edt = (date.today() - timedelta(days=20)).isoformat()
    start = (date.today() - timedelta(days=420)).isoformat()
    d = _assess(_ud_facts(edt=edt, service_start_date=start),
                "Sacked after a row about my timekeeping.")
    assert d.get("has_viable_claim") == "no"
    assert d.get("day_one_exception_possible") is False


# ── 2. Deadline-passed / urgency warnings ────────────────────────────────────

def test_expired_deadline_flagged():
    edt = (date.today() - timedelta(days=150)).isoformat()   # deadline long past
    start = (date.today() - timedelta(days=2000)).isoformat()
    d = _assess(_ud_facts(edt=edt, service_start_date=start),
                "Dismissed months ago, only now looking into a claim.")
    di = d["deadline_info"]
    assert di["deadline_passed"] is True
    assert di["urgency_level"] == "expired"
    assert "PASSED" in di["deadline_warning"]
    assert di["days_remaining"] < 0


def test_near_deadline_critical():
    # deadline = edt + 3 months - 1 day; choose edt so ~7 days remain
    edt = (date.today() - timedelta(days=83)).isoformat()
    start = (date.today() - timedelta(days=2000)).isoformat()
    d = _assess(_ud_facts(edt=edt, service_start_date=start), "Recently dismissed.")
    di = d["deadline_info"]
    assert di["deadline_passed"] is False
    assert di["urgency_level"] in ("critical", "urgent"), di
    assert di["deadline_warning"]


def test_fresh_claim_normal_urgency():
    edt = (date.today() - timedelta(days=10)).isoformat()
    start = (date.today() - timedelta(days=2000)).isoformat()
    d = _assess(_ud_facts(edt=edt, service_start_date=start), "Dismissed last week.")
    di = d["deadline_info"]
    assert di["deadline_passed"] is False
    assert di["urgency_level"] == "normal"


# ── 3. Deterministic-first timing ─────────────────────────────────────────────

def test_deterministic_lane_is_fast():
    """use_model=False (the intake default) must answer in seconds, not minutes."""
    edt = (date.today() - timedelta(days=30)).isoformat()
    start = (date.today() - timedelta(days=2000)).isoformat()
    t0 = time.monotonic()
    d = _assess(_ud_facts(edt=edt, service_start_date=start), "Dismissed with no hearing.")
    elapsed = time.monotonic() - t0
    assert d["status"] == "ok"
    assert elapsed < 30, f"deterministic lane took {elapsed:.1f}s"


def test_intake_form_uses_deterministic_lane():
    html = (ROOT / "client/public/pages/intake.html").read_text(encoding="utf-8")
    assert "use_model: false" in html, "intake must not block users on the model lane"


# ── 5. Date validation ────────────────────────────────────────────────────────

def test_future_dismissal_date_rejected():
    edt = (date.today() + timedelta(days=200)).isoformat()
    d = _assess(_ud_facts(edt=edt, service_start_date="2020-01-01"), "I was dismissed.")
    assert d["status"] == "invalid_date"
    assert "edt" in d["field_errors"]
    assert "future" in d["field_errors"]["edt"].lower()


def test_start_after_dismissal_rejected():
    d = _assess(_ud_facts(edt="2024-01-01", service_start_date="2026-01-01"),
                "I was dismissed.")
    assert d["status"] == "invalid_date"
    assert "service_start_date" in d["field_errors"]


def test_malformed_dates_field_level_error():
    d = _assess(_ud_facts(edt="15/05/2026", service_start_date="2020-01-01"),
                "I was dismissed.")
    assert d["status"] == "invalid_date", d
    assert "edt" in d.get("field_errors", {})
    # must NOT be reported as out-of-scope
    assert d["status"] != "not_supported"

    d2 = _assess(_ud_facts(edt="2026-01-10", service_start_date="banana"),
                 "I was dismissed.")
    assert d2["status"] == "invalid_date"
    assert "service_start_date" in d2.get("field_errors", {})


# ── 4. Pricing consistency ────────────────────────────────────────────────────

def test_pricing_consistent_across_surfaces():
    """One price everywhere: homepage, assessment page, payment routes."""
    prices = set()
    for rel in ("client/public/index.html", "client/public/pages/assessment.html"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        prices.update(re.findall(r"£(\d+(?:\.\d{2})?)", text))
    prices.discard("0")  # the free tier
    assert prices == {"29.99"}, f"inconsistent prices in UI: {prices}"

    pay = (ROOT / "backend/api/payment_routes.py").read_text(encoding="utf-8")
    assert "2999" in pay, "checkout amount (pence) must match the advertised £29.99"
