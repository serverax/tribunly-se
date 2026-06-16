"""Temporal Graph RAG  -  synchronous psycopg2 + NetworkX hydrator (Option 1).

Builds a chronological DiGraph of a user's case events from graph_nodes/graph_edges
(app-level isolation by user_id [+ workspace_id]) and computes UK Employment
Tribunal limitation deadlines deterministically.

IMPORTANT (no hardcoded legal values): the limitation period in MONTHS is read
from the rules table (unfair_dismissal.time_limit_months), not hardcoded. The
"less one day" arithmetic is deterministic code. The model never computes deadlines.
"""
from __future__ import annotations

import calendar
import json
from datetime import date, timedelta
from typing import Optional

import networkx as nx


def _get_conn():
    from ingestion.db import get_connection
    return get_connection()


# ── Graph writes ─────────────────────────────────────────────────────────────
def add_event(conn, user_id: str, event_label: str, asserted_date: str,
              workspace_id: Optional[str] = None, metadata: Optional[dict] = None) -> str:
    """Insert a timeline event node. Returns node_id (text)."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO graph_nodes (workspace_id, user_id, event_label, asserted_date, metadata)
               VALUES (%s, %s::uuid, %s, %s, %s::jsonb) RETURNING node_id::text""",
            (workspace_id, user_id, event_label, asserted_date, json.dumps(metadata or {})),
        )
        node_id = cur.fetchone()[0]
    conn.commit()
    return node_id


def link_events(conn, user_id: str, source_node_id: str, target_node_id: str,
                relationship_type: str = "next_event",
                workspace_id: Optional[str] = None) -> str:
    """Create a temporal edge with a pre-computed day delta. Returns edge_id (text)."""
    with conn.cursor() as cur:
        cur.execute("SELECT asserted_date FROM graph_nodes WHERE node_id=%s::uuid", (source_node_id,))
        s = cur.fetchone()
        cur.execute("SELECT asserted_date FROM graph_nodes WHERE node_id=%s::uuid", (target_node_id,))
        t = cur.fetchone()
        if not s or not t:
            raise ValueError("source/target node not found")
        delta = (t[0] - s[0]).days
        cur.execute(
            """INSERT INTO graph_edges
                 (workspace_id, user_id, source_node_id, target_node_id, relationship_type, calculated_delta_days)
               VALUES (%s, %s::uuid, %s::uuid, %s::uuid, %s, %s) RETURNING edge_id::text""",
            (workspace_id, user_id, source_node_id, target_node_id, relationship_type, delta),
        )
        edge_id = cur.fetchone()[0]
    conn.commit()
    return edge_id


# ── Graph hydration ──────────────────────────────────────────────────────────
def hydrate_graph_from_db(conn, user_id: str, workspace_id: Optional[str] = None) -> nx.DiGraph:
    """Reconstruct the user's temporal DiGraph (app-level isolation by user_id)."""
    G = nx.DiGraph()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT node_id::text, event_label, asserted_date, metadata
               FROM graph_nodes WHERE user_id=%s::uuid
                 AND (%s::uuid IS NULL OR workspace_id=%s::uuid)
               ORDER BY asserted_date""",
            (user_id, workspace_id, workspace_id),
        )
        for nid, label, ad, meta in cur.fetchall():
            G.add_node(nid, label=label, date=ad.isoformat() if ad else None,
                       **(meta if isinstance(meta, dict) else {}))
        cur.execute(
            """SELECT source_node_id::text, target_node_id::text, relationship_type, calculated_delta_days
               FROM graph_edges WHERE user_id=%s::uuid
                 AND (%s::uuid IS NULL OR workspace_id=%s::uuid)""",
            (user_id, workspace_id, workspace_id),
        )
        for src, tgt, rel, delta in cur.fetchall():
            G.add_edge(src, tgt, relation=rel, delta=delta)
    return G


# ── Deterministic UK tribunal deadline (months from rules; -1 day in code) ───
def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    mo = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, mo)[1])
    return date(y, mo, day)


def compute_timeline_deadline(conn, trigger_date: date, claim_type: str = "unfair_dismissal",
                              jurisdiction: str = "EW", today: Optional[date] = None) -> dict:
    """ET limitation: '<N> months less one day' from the trigger date, where N is the
    months value from the rules table (NOT hardcoded). Fails closed if the rule is absent."""
    from backend.core.retrieve import retrieve_rules
    rules = retrieve_rules(claim_type, jurisdiction, trigger_date)
    tl = next((r for r in rules if r.get("rule_key") == f"{claim_type}.time_limit_months"), None)
    if not tl or tl.get("value_numeric") is None:
        return {"status": "insufficient_grounding",
                "reason": "time_limit_months rule missing  -  fail closed (no hardcoded deadline)"}
    months = int(tl["value_numeric"])
    deadline = _add_months(trigger_date, months) - timedelta(days=1)  # "less one day"
    today = today or date.today()
    return {
        "status": "ok",
        "trigger_date": trigger_date.isoformat(),
        "limit_months": months,
        "months_authority": tl.get("authority_ref") or tl.get("rule_key"),
        "deadline": deadline.isoformat(),
        "within_limit": today <= deadline,
        "days_remaining": (deadline - today).days,
    }
