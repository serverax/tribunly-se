"""
SUBAGENT 8 — Database Engineer: auth database schema proof.

Runs against the live local Docker DB (tests/conftest.py points POSTGRES_* at
localhost:5435). Proves, with real SQL against real tables:

  * schema is correct      — all six required entities resolve
                             (users, user_identities, user_sessions, auth_events,
                              onboarding_profiles, conversion_events)
  * indexes work           — email / provider_id / session_id indexes exist AND
                             are actually chosen by the planner
  * migrations run cleanly — 050 is idempotent (re-runnable) and reversible
                             (up → down → up round-trips)
  * no duplicate prevention bypassed — duplicate email is rejected,
                             provider-account merge integrity holds, account
                             linking of multiple providers to one user works

Design notes:
  * user_sessions / user_identities / onboarding_profiles are canonical-name
    VIEWS over the WIRED base tables (auth_sessions / oauth_identities / users).
    Verifying them therefore verifies the real session/identity/onboarding store
    the auth service writes to — not a parallel copy.
  * conversion_events is owned by SUBAGENT 5 (migration 049); this suite verifies
    its existence + indexes because it is one of the six required entities.
  * Every test cleans up the rows it inserts (unique marker prefix), so the suite
    is safe to run repeatedly against the shared live DB.
"""

from __future__ import annotations

import os
import uuid

import psycopg2
import pytest

from ingestion.db import get_connection

# Test-row marker so a crashed run can be cleaned up deterministically.
_MARK = "authdbtest"

_MIG_DIR = os.path.join(os.path.dirname(__file__), "..", "db", "migrations")
_UP_050 = os.path.join(_MIG_DIR, "050_auth_canonical_views.sql")
_DOWN_050 = os.path.join(_MIG_DIR, "down", "050_auth_canonical_views.down.sql")
_UP_049 = os.path.join(_MIG_DIR, "049_conversion_funnel.sql")

_REQUIRED_ENTITIES = [
    "users",
    "user_identities",
    "user_sessions",
    "auth_events",
    "onboarding_profiles",
    "conversion_events",
]


def _run_sql_file(path: str) -> None:
    """Execute a whole .sql migration file against the live DB (its own txn)."""
    with open(path, "r", encoding="utf-8") as fh:
        sql = fh.read()
    conn = get_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


def _q(sql: str, params: tuple = (), *, fetch: str = "all"):
    conn = get_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if fetch == "one":
                return cur.fetchone()
            if fetch == "none":
                return None
            return cur.fetchall()
    finally:
        conn.close()


def _explain_index_forced(sql: str, params: tuple) -> str:
    """Return the EXPLAIN plan with seq scans disabled, in a SINGLE session.

    On a small table the planner correctly prefers a Seq Scan (cheaper than an
    index for a handful of rows) — that is healthy behaviour, not a missing
    index. Disabling enable_seqscan forces the planner to reveal whether a
    USABLE index exists for the predicate: if one does it picks an Index Scan,
    otherwise it falls back to Seq Scan. So 'Index Scan' here proves the index
    actually serves the lookup, independent of table size."""
    conn = get_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SET enable_seqscan = off")
            cur.execute("EXPLAIN " + sql, params)
            return "\n".join(r[0] for r in cur.fetchall())
    finally:
        conn.close()


@pytest.fixture(scope="module", autouse=True)
def _ensure_migrations_applied():
    """Apply 049 (conversion_events dependency) + 050 (auth views) before the
    suite, idempotently, so the schema is present regardless of DB state / order.
    Then clean up any leftover test rows on exit."""
    _run_sql_file(_UP_049)
    _run_sql_file(_UP_050)
    yield
    _cleanup()


def _cleanup() -> None:
    # Order matters: child rows before users (FKs ON DELETE CASCADE/SET NULL).
    try:
        _q("DELETE FROM conversion_events WHERE session_id LIKE %s OR user_id IN "
           "(SELECT id FROM users WHERE email LIKE %s)", (f"{_MARK}-%", f"{_MARK}-%"), fetch="none")
        _q("DELETE FROM users WHERE email LIKE %s", (f"{_MARK}-%",), fetch="none")
    except Exception:
        pass


@pytest.fixture
def new_user():
    """Create a throwaway user, return its id; cleaned up after the test."""
    created: list[str] = []

    def _make(email: str | None = None) -> str:
        email = email or f"{_MARK}-{uuid.uuid4()}@example.test"
        row = _q("INSERT INTO users (email) VALUES (%s) RETURNING id", (email,), fetch="one")
        uid = str(row[0])
        created.append(uid)
        return uid

    yield _make
    for uid in created:
        _q("DELETE FROM users WHERE id = %s::uuid", (uid,), fetch="none")


# ── schema correctness ────────────────────────────────────────────────────────

@pytest.mark.parametrize("entity", _REQUIRED_ENTITIES)
def test_required_entity_exists(entity):
    """Every one of the six required entities resolves to a real DB object."""
    row = _q("SELECT to_regclass(%s)", (f"public.{entity}",), fetch="one")
    assert row[0] is not None, f"required entity '{entity}' does not exist"


def test_session_and_identity_views_expose_canonical_columns():
    """user_sessions exposes session_id; user_identities exposes provider_id —
    the stable identifiers the rest of the product refers to."""
    us_cols = {r[0] for r in _q(
        "SELECT column_name FROM information_schema.columns WHERE table_name='user_sessions'")}
    ui_cols = {r[0] for r in _q(
        "SELECT column_name FROM information_schema.columns WHERE table_name='user_identities'")}
    assert "session_id" in us_cols and "user_id" in us_cols
    assert "provider_id" in ui_cols and "provider" in ui_cols and "user_id" in ui_cols


def test_views_are_backed_by_the_wired_base_tables():
    """The canonical-name views must read the WIRED base tables (single source of
    truth) — not a duplicate copy. Confirm the dependency in pg_depend."""
    for view, base in [("user_sessions", "auth_sessions"),
                       ("user_identities", "oauth_identities"),
                       ("onboarding_profiles", "users")]:
        row = _q(
            """
            SELECT EXISTS (
              SELECT 1
                FROM pg_depend d
                JOIN pg_rewrite r ON r.oid = d.objid
                JOIN pg_class v   ON v.oid = r.ev_class
                JOIN pg_class t   ON t.oid = d.refobjid
               WHERE v.relname = %s AND t.relname = %s
            )
            """,
            (view, base), fetch="one",
        )
        assert row[0] is True, f"view {view} is not backed by base table {base}"


# ── indexes work (exist AND are used) ─────────────────────────────────────────

def test_required_indexes_exist():
    """email / provider_id / session_id indexes are all present."""
    idx = {r[0] for r in _q("SELECT indexname FROM pg_indexes WHERE schemaname='public'")}
    # email
    assert "users_email_lower_uidx" in idx, "case-insensitive email unique index missing"
    # provider_id (composite uniqueness + reverse-lookup)
    assert "oauth_identities_provider_subject_key" in idx
    assert "oauth_identities_subject_idx" in idx, "provider_id reverse-lookup index missing"
    # session_id (auth_sessions PK)
    assert "auth_sessions_pkey" in idx


def test_email_index_serves_lookup(new_user):
    """The case-insensitive email index serves a `lower(email) = ?` lookup."""
    new_user()
    plan = _explain_index_forced(
        "SELECT id FROM users WHERE lower(email) = %s", (f"{_MARK}-x@example.test",))
    assert "users_email_lower_uidx" in plan, f"email lookup did not use the index:\n{plan}"


def test_session_id_index_serves_lookup(new_user):
    """A lookup by session_id (auth_sessions PK) is served by an Index Scan."""
    uid = new_user()
    sid_row = _q(
        "INSERT INTO auth_sessions (user_id, refresh_token_hash, expires_at) "
        "VALUES (%s::uuid, %s, now() + interval '1 day') RETURNING id",
        (uid, f"{_MARK}-{uuid.uuid4()}"), fetch="one")
    sid = str(sid_row[0])
    try:
        plan = _explain_index_forced(
            "SELECT user_id FROM auth_sessions WHERE id = %s::uuid", (sid,))
        assert "Index Scan" in plan, f"session_id lookup not index-served:\n{plan}"
    finally:
        _q("DELETE FROM auth_sessions WHERE id = %s::uuid", (sid,), fetch="none")


def test_provider_id_index_serves_lookup(new_user):
    """The provider_id reverse-lookup index serves a `subject = ?` lookup."""
    uid = new_user()
    subject = f"{_MARK}-sub-{uuid.uuid4()}"
    _q("INSERT INTO oauth_identities (user_id, provider, subject) VALUES (%s::uuid,'google',%s)",
       (uid, subject), fetch="none")
    try:
        plan = _explain_index_forced(
            "SELECT user_id FROM oauth_identities WHERE subject = %s", (subject,))
        assert "Index Scan" in plan and "oauth_identities_subject_idx" in plan, \
            f"provider_id lookup not index-served:\n{plan}"
    finally:
        _q("DELETE FROM oauth_identities WHERE subject = %s", (subject,), fetch="none")


# ── no duplicate prevention bypassed ──────────────────────────────────────────

def test_duplicate_email_rejected_case_insensitive(new_user):
    """No duplicate accounts: a second user with the same email (different case)
    is rejected by the unique index — the prevention cannot be bypassed."""
    email = f"{_MARK}-{uuid.uuid4()}@example.test"
    new_user(email)
    with pytest.raises(psycopg2.IntegrityError):
        _q("INSERT INTO users (email) VALUES (%s)", (email.upper(),), fetch="none")


def test_provider_merge_integrity(new_user):
    """Provider merge: one provider account (provider, subject) cannot be linked
    to two different users — the UNIQUE(provider, subject) key prevents it."""
    u1, u2 = new_user(), new_user()
    subject = f"{_MARK}-sub-{uuid.uuid4()}"
    _q("INSERT INTO oauth_identities (user_id, provider, subject) VALUES (%s::uuid,'google',%s)",
       (u1, subject), fetch="none")
    try:
        with pytest.raises(psycopg2.IntegrityError):
            _q("INSERT INTO oauth_identities (user_id, provider, subject) VALUES (%s::uuid,'google',%s)",
               (u2, subject), fetch="none")
    finally:
        _q("DELETE FROM oauth_identities WHERE subject = %s", (subject,), fetch="none")


def test_account_linking_multiple_providers(new_user):
    """Account linking: one user can link MORE THAN ONE provider identity; the
    user_identities view surfaces them all under provider_id."""
    uid = new_user()
    g_sub = f"{_MARK}-sub-{uuid.uuid4()}"
    m_sub = f"{_MARK}-sub-{uuid.uuid4()}"
    _q("INSERT INTO oauth_identities (user_id, provider, subject) VALUES (%s::uuid,'google',%s)",
       (uid, g_sub), fetch="none")
    _q("INSERT INTO oauth_identities (user_id, provider, subject) VALUES (%s::uuid,'microsoft',%s)",
       (uid, m_sub), fetch="none")
    try:
        rows = _q("SELECT provider, provider_id FROM user_identities WHERE user_id = %s::uuid "
                  "ORDER BY provider", (uid,))
        providers = {r[0]: r[1] for r in rows}
        assert providers == {"google": g_sub, "microsoft": m_sub}
    finally:
        _q("DELETE FROM oauth_identities WHERE subject IN (%s,%s)", (g_sub, m_sub), fetch="none")


# ── view fidelity (the views reflect real writes) ─────────────────────────────

def test_user_sessions_view_reflects_auth_sessions(new_user):
    uid = new_user()
    sid_row = _q(
        "INSERT INTO auth_sessions (user_id, refresh_token_hash, expires_at) "
        "VALUES (%s::uuid, %s, now() + interval '1 day') RETURNING id",
        (uid, f"{_MARK}-{uuid.uuid4()}"), fetch="one")
    sid = str(sid_row[0])
    try:
        row = _q("SELECT session_id, user_id, is_active FROM user_sessions WHERE session_id = %s::uuid",
                 (sid,), fetch="one")
        assert row is not None and str(row[0]) == sid and str(row[1]) == uid
        assert row[2] is True  # freshly issued, not revoked, not expired
    finally:
        _q("DELETE FROM auth_sessions WHERE id = %s::uuid", (sid,), fetch="none")


def test_onboarding_profiles_view_reflects_users(new_user):
    uid = new_user()
    row = _q("SELECT onboarding_complete FROM onboarding_profiles WHERE user_id = %s::uuid",
             (uid,), fetch="one")
    assert row is not None and row[0] is False  # not onboarded yet
    _q("UPDATE users SET role='employee', full_name='Test Claimant', onboarded_at=now() "
       "WHERE id = %s::uuid", (uid,), fetch="none")
    row = _q("SELECT role, full_name, onboarding_complete FROM onboarding_profiles "
             "WHERE user_id = %s::uuid", (uid,), fetch="one")
    assert row[0] == "employee" and row[1] == "Test Claimant" and row[2] is True


# ── conversion_events usable (sixth required entity) ──────────────────────────

def test_conversion_events_anonymous_then_linked(new_user):
    """conversion_events accepts an anonymous (pre-signup) event and a
    user-linked event, and its session_id index serves per-session reconstruction."""
    sess = f"{_MARK}-sess-{uuid.uuid4()}"
    uid = new_user()
    _q("INSERT INTO conversion_events (session_id, event_name) VALUES (%s,'landing_view')",
       (sess,), fetch="none")
    _q("INSERT INTO conversion_events (session_id, event_name, user_id) "
       "VALUES (%s,'signup_completed',%s::uuid)", (sess, uid), fetch="none")
    try:
        rows = _q("SELECT event_name, user_id FROM conversion_events WHERE session_id = %s "
                  "ORDER BY occurred_at", (sess,))
        names = [r[0] for r in rows]
        assert names == ["landing_view", "signup_completed"]
        assert rows[0][1] is None and str(rows[1][1]) == uid
    finally:
        _q("DELETE FROM conversion_events WHERE session_id = %s", (sess,), fetch="none")


# ── migrations run cleanly: idempotent + reversible ───────────────────────────

def test_migration_050_idempotent():
    """Re-applying 050 must not error (CREATE OR REPLACE / IF NOT EXISTS)."""
    _run_sql_file(_UP_050)
    _run_sql_file(_UP_050)
    for v in ("user_sessions", "user_identities", "onboarding_profiles"):
        assert _q("SELECT to_regclass(%s)", (f"public.{v}",), fetch="one")[0] is not None


def test_migration_050_reversible():
    """up → down → up round-trips: down drops exactly 050's objects, up restores
    them. Ends UP so the rest of the suite (and the live DB) keep the views."""
    # DOWN: views + reverse-lookup index gone; canonical tables untouched.
    _run_sql_file(_DOWN_050)
    for v in ("user_sessions", "user_identities", "onboarding_profiles"):
        assert _q("SELECT to_regclass(%s)", (f"public.{v}",), fetch="one")[0] is None
    assert _q("SELECT indexname FROM pg_indexes WHERE indexname='oauth_identities_subject_idx'",
              fetch="all") == []
    # down must NOT have dropped the wired base tables.
    for base in ("auth_sessions", "oauth_identities", "users", "auth_events"):
        assert _q("SELECT to_regclass(%s)", (f"public.{base}",), fetch="one")[0] is not None
    # UP again: restored.
    _run_sql_file(_UP_050)
    for v in ("user_sessions", "user_identities", "onboarding_profiles"):
        assert _q("SELECT to_regclass(%s)", (f"public.{v}",), fetch="one")[0] is not None
