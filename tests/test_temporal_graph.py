"""Temporal Graph RAG proof (Option 1): NetworkX hydrator + rules-sourced deadline.

  - events written + linked, hydrated into a NetworkX DiGraph with correct delta,
  - UK ET deadline = N months (from rules) less one day, computed deterministically,
  - app-level isolation: another user sees an empty graph.
"""
from __future__ import annotations

from datetime import date

import pytest


def _conn():
    from ingestion.db import get_connection
    return get_connection()


def _db_up():
    try:
        c = _conn(); c.close(); return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_up(), reason="UNPROVEN  -  DB not accessible")

UID = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"


def _cleanup():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM graph_edges WHERE user_id IN (%s::uuid,%s::uuid)", (UID, OTHER))
            cur.execute("DELETE FROM graph_nodes WHERE user_id IN (%s::uuid,%s::uuid)", (UID, OTHER))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def clean():
    _cleanup(); yield; _cleanup()


def test_hydrate_builds_digraph_with_delta():
    from backend.core.sovereign.graph_hydrator import add_event, link_events, hydrate_graph_from_db
    conn = _conn()
    try:
        n1 = add_event(conn, UID, "Suspension", "2025-11-14")
        n2 = add_event(conn, UID, "Probation_End", "2025-12-09")
        link_events(conn, UID, n1, n2, "next_event")
        G = hydrate_graph_from_db(conn, UID)
        assert G.number_of_nodes() == 2
        assert G.number_of_edges() == 1
        assert G[n1][n2]["delta"] == 25      # 14 Nov -> 9 Dec = 25 days
    finally:
        conn.close()


def test_deadline_is_months_from_rules_less_one_day():
    from backend.core.sovereign.graph_hydrator import compute_timeline_deadline
    conn = _conn()
    try:
        # today fixed so within_limit is deterministic
        res = compute_timeline_deadline(conn, date(2025, 10, 1), today=date(2025, 11, 1))
        assert res["status"] == "ok", res
        assert res["limit_months"] == 3                 # sourced from rules, not hardcoded
        assert res["deadline"] == "2025-12-31"          # 1 Oct + 3 months - 1 day
        assert res["within_limit"] is True
        assert res["days_remaining"] == 60
    finally:
        conn.close()


def test_app_level_isolation_other_user_sees_nothing():
    from backend.core.sovereign.graph_hydrator import add_event, hydrate_graph_from_db
    conn = _conn()
    try:
        add_event(conn, UID, "Suspension", "2025-11-14")
        G_other = hydrate_graph_from_db(conn, OTHER)
        assert G_other.number_of_nodes() == 0   # no cross-user leakage
    finally:
        conn.close()
