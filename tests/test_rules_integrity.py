"""Behavioural tests: rules table is the legal-correctness source (cited, dated, verified)."""
from __future__ import annotations

import pytest

from ingestion.db import get_connection

REQUIRED_KEYS = [
    "unfair_dismissal.time_limit_months",
    "unfair_dismissal.early_conciliation_required",
    "unfair_dismissal.qualifying_period",
    "unfair_dismissal.compensatory_cap_amount",
    "unfair_dismissal.compensatory_cap_weeks_pay",
    "unfair_dismissal.weeks_pay_cap_amount",
    "unfair_dismissal.basic_award_formula",
    "unfair_dismissal.basic_award_min_automatic",
    "unfair_dismissal.acas_code_adjustment_percent",
    "unfair_dismissal.not_reasonably_practicable_extension",
]
ALLOWED_VERIFICATION = {"verified", "case_law_verified", "prospective", "unverified", "mismatch", "blocked"}


@pytest.fixture(scope="module")
def cur():
    conn = get_connection()
    c = conn.cursor()
    yield c
    c.close()
    conn.close()


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_required_gb_rule_present(cur, key):
    cur.execute("SELECT count(*) FROM rules WHERE rule_key=%s AND jurisdiction_code='GB'", (key,))
    assert cur.fetchone()[0] >= 1, f"missing required GB rule {key}"


def test_current_rules_fully_cited(cur):
    cur.execute(
        "SELECT count(*) FROM rules WHERE is_current=true AND ("
        "authority_ref IS NULL OR authority_ref='' OR authority_url IS NULL OR authority_url='' "
        "OR effective_from IS NULL OR last_verified_at IS NULL OR jurisdiction_code IS NULL)"
    )
    assert cur.fetchone()[0] == 0


def test_verification_status_in_allowed_set(cur):
    cur.execute("SELECT DISTINCT verification_status FROM rules")
    vals = {r[0] for r in cur.fetchall()}
    assert vals.issubset(ALLOWED_VERIFICATION), f"invalid verification_status values: {vals - ALLOWED_VERIFICATION}"


def test_caps_tied_to_official_uksi(cur):
    for key in ("unfair_dismissal.weeks_pay_cap_amount", "unfair_dismissal.compensatory_cap_amount"):
        cur.execute(
            "SELECT count(*) FROM rules WHERE rule_key=%s AND authority_url ILIKE %s AND effective_from IS NOT NULL",
            (key, "%legislation.gov.uk/uksi/%"),
        )
        assert cur.fetchone()[0] >= 1, f"{key} not tied to official UKSI source"


def test_caps_effective_dated_history(cur):
    cur.execute("SELECT count(*) FROM rules WHERE rule_key='unfair_dismissal.weeks_pay_cap_amount'")
    assert cur.fetchone()[0] >= 3, "week's pay cap must have multiple effective-dated rows (backdated cases)"
