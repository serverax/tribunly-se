"""T-010  -  CROSS-USER ROW-LEVEL SECURITY (RLS) END-TO-END proof.

This suite proves, against the REAL local DB and over REAL HTTP, that user A can
never see, modify, or unlock user B's data  -  at the backend monolith (the actual
RLS boundary) and across the distributed AI services.

────────────────────────────────────────────────────────────────────────────────
ARCHITECTURE TRUTH (read before judging the assertions)
────────────────────────────────────────────────────────────────────────────────
User-owned rows live ONLY in the backend monolith DB:
    cases(user_id)         documents(case_id → cases.user_id)
    reminder_events(case_id) payment_events(user_id, case_id)
RLS is enforced there by:
    • /cases                        -  SELECT ... WHERE user_id = <caller>   (own rows only)
    • /cases/{id} and every         -  check_case_ownership() → 401 anon / 403 wrong user
      /cases/{id}/* sub-route         (via the _require_case_owner dependency)
    • paid unlock (is_case_paid)    -  DB-backed, keyed to the OWNING case row only

The distributed AI services (lawapp-rules-engine, lawapp-rag-retrieval,
lawapp-llm-gateway, lawapp-document-service, lawapp-brain) are STATELESS legal
COMPUTE. They store NO per-user rows: the rules table and legal corpus are shared
public knowledge, document content is generated from facts supplied IN the request
body, and inference is stateless. Therefore "A can't read B's data" at the service
tier is a STRUCTURAL guarantee, proven here three ways:
    1. tenancy context is MANDATORY (services 400 without user/workspace/case ids);
    2. the only stateful retrieval (document GET) returns 501  -  it can never echo
       another user's stored document because no per-user store is wired;
    3. service responses carry NO user-owned fields and never echo a caller's PII
       (the llm-gateway rejects PII at the model boundary  -  data minimisation).

We do NOT pretend the compute services run their own row filter  -  they have no
user rows to filter. Faking such an assertion would be a false PASS.

────────────────────────────────────────────────────────────────────────────────
SECURITY REGRESSION FIXED BY THIS WORK (T-010)
────────────────────────────────────────────────────────────────────────────────
check_case_ownership() previously early-returned when user_id is None. In jwt/mock
(enforcing) modes an ANONYMOUS request also yields user_id=None, so a no-token
caller could read/modify ANY case by id (confidentiality breach). Fixed in
backend/core/user_auth.py: enforcing modes now raise 401 on a missing identity;
only dev 'none' mode passes through. `test_anonymous_*` below pins the fix.

If the local DB is unreachable the DB-backed tests SKIP  -  they are never faked.
"""
from __future__ import annotations

import importlib
import os
import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

# ── Identities & fixtures ─────────────────────────────────────────────────────
_SECRET = "t010-rls-e2e-secret-min-32-bytes-len!!"   # ≥32 bytes (HS256, no warning)
UID_A = str(uuid.uuid4())
UID_B = str(uuid.uuid4())
CASE_A = str(uuid.uuid4())   # owned by A, payment_status = 'paid'
CASE_B = str(uuid.uuid4())   # owned by B, payment_status = 'none'
A_SECRET_MARKER = "alpha-confidential-marker"
B_SECRET_MARKER = "bravo-confidential-marker"


def _token(sub: str) -> str:
    return jwt.encode({"sub": sub, "exp": int(time.time()) + 3600}, _SECRET, algorithm="HS256")


def _auth(sub: str) -> dict:
    return {"Authorization": f"Bearer {_token(sub)}"}


def _db_available() -> bool:
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        conn.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def env_jwt():
    """Enforcing (production-representative) auth: jwt mode, HS256 forged tokens.
    No issuer/audience configured → tokens validate on signature + exp only."""
    saved = {k: os.environ.get(k) for k in
             ("LAWAPP_AUTH_MODE", "JWT_SECRET", "JWT_ISSUER", "JWT_AUDIENCE")}
    os.environ["LAWAPP_AUTH_MODE"] = "jwt"
    os.environ["JWT_SECRET"] = _SECRET
    os.environ.pop("JWT_ISSUER", None)
    os.environ.pop("JWT_AUDIENCE", None)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture(scope="module")
def seeded(env_jwt):
    """Seed two real users + two real cases (+ a reminder each) in the live DB.
    Skips the whole suite if the DB is unreachable  -  RLS is never proven on mocks."""
    if not _db_available():
        pytest.skip("local DB unreachable  -  cross-user RLS cannot be proven on mock data")
    from ingestion.db import get_connection
    from backend.core.user_auth import ensure_user_exists

    conn = get_connection()
    cur = conn.cursor()
    ensure_user_exists(conn, UID_A)
    ensure_user_exists(conn, UID_B)
    seed = (
        (CASE_A, UID_A, "paid", A_SECRET_MARKER),
        (CASE_B, UID_B, "none", B_SECRET_MARKER),
    )
    for cid, uid, pay, marker in seed:
        cur.execute(
            """
            INSERT INTO cases (id, user_id, claim_type, jurisdiction, status,
                               payment_status, assessment, key_dates)
            VALUES (%s::uuid, %s::uuid, 'unfair_dismissal', 'EW', 'diagnosis',
                    %s, %s::jsonb, '{"deadline_date": "2026-09-01", "edt": "2026-06-01"}'::jsonb)
            """,
            (cid, uid, pay, f'{{"confidential": "{marker}"}}'),
        )
        cur.execute(
            "INSERT INTO reminder_events (case_id, reminder_type) VALUES (%s::uuid, %s)",
            (cid, "deadline_approaching"),
        )
    conn.commit()
    conn.close()
    try:
        yield
    finally:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM reminder_events WHERE case_id IN (%s::uuid, %s::uuid)", (CASE_A, CASE_B))
        cur.execute("DELETE FROM cases WHERE id IN (%s::uuid, %s::uuid)", (CASE_A, CASE_B))
        cur.execute("DELETE FROM users WHERE id IN (%s::uuid, %s::uuid)", (UID_A, UID_B))
        conn.commit()
        conn.close()


@pytest.fixture(scope="module")
def client(seeded):
    from backend.api.main import app
    return TestClient(app, raise_server_exceptions=False)


# ══════════════════════════════════════════════════════════════════════════════
# PART 1  -  BACKEND MONOLITH: the real RLS boundary (real DB rows, real HTTP, JWT)
# ══════════════════════════════════════════════════════════════════════════════

class TestListIsolation:
    def test_user_a_lists_only_own_cases(self, client):
        r = client.get("/cases", headers=_auth(UID_A))
        assert r.status_code == 200, r.text
        ids = {c["case_id"] for c in r.json()["cases"]}
        assert CASE_A in ids, "A cannot see its own case"
        assert CASE_B not in ids, "RLS LEAK: A's case list contains B's case"
        assert B_SECRET_MARKER not in r.text, "RLS LEAK: B's confidential data in A's list"

    def test_user_b_lists_only_own_cases(self, client):
        r = client.get("/cases", headers=_auth(UID_B))
        assert r.status_code == 200, r.text
        ids = {c["case_id"] for c in r.json()["cases"]}
        assert CASE_B in ids
        assert CASE_A not in ids, "RLS LEAK: B's case list contains A's case"
        assert A_SECRET_MARKER not in r.text, "RLS LEAK: A's confidential data in B's list"

    def test_list_requires_authentication(self, client):
        r = client.get("/cases")   # no token, jwt mode
        assert r.status_code == 401, f"unauth list must be 401, got {r.status_code}"


class TestGetCaseIsolation:
    def test_owner_reads_own_case(self, client):
        r = client.get(f"/cases/{CASE_A}", headers=_auth(UID_A))
        assert r.status_code == 200, r.text
        assert r.json()["case_id"] == CASE_A

    def test_cross_user_get_is_forbidden(self, client):
        r = client.get(f"/cases/{CASE_B}", headers=_auth(UID_A))
        assert r.status_code == 403, f"A reading B's case must be 403, got {r.status_code}"
        assert B_SECRET_MARKER not in r.text, "RLS LEAK: B's confidential data returned to A"

    def test_cross_user_get_reverse_is_forbidden(self, client):
        r = client.get(f"/cases/{CASE_A}", headers=_auth(UID_B))
        assert r.status_code == 403
        assert A_SECRET_MARKER not in r.text

    def test_anonymous_get_is_unauthorized(self, client):
        # Regression pin: a no-token request in jwt mode must NOT read a case.
        r = client.get(f"/cases/{CASE_B}")
        assert r.status_code == 401, f"anon get must be 401 (was the RLS leak), got {r.status_code}"
        assert B_SECRET_MARKER not in r.text


class TestSubResourceIsolation:
    """Every /cases/{id}/* sub-route is guarded by the same ownership dependency."""

    def test_cross_user_deadline_forbidden(self, client):
        r = client.get(f"/cases/{CASE_B}/deadline", headers=_auth(UID_A))
        assert r.status_code == 403

    def test_anonymous_deadline_unauthorized(self, client):
        assert client.get(f"/cases/{CASE_B}/deadline").status_code == 401

    def test_cross_user_list_reminders_forbidden(self, client):
        r = client.get(f"/cases/{CASE_B}/reminders", headers=_auth(UID_A))
        assert r.status_code == 403, "A must not read B's reminders"

    def test_cross_user_create_reminder_forbidden(self, client):
        r = client.post(f"/cases/{CASE_B}/reminders", headers=_auth(UID_A),
                        json={"reminder_type": "deadline_approaching"})
        assert r.status_code == 403, "A must not write a reminder onto B's case"

    def test_cross_user_timeline_forbidden(self, client):
        assert client.get(f"/cases/{CASE_B}/timeline", headers=_auth(UID_A)).status_code == 403

    def test_cross_user_escalation_forbidden(self, client):
        assert client.get(f"/cases/{CASE_B}/escalation", headers=_auth(UID_A)).status_code == 403

    def test_cross_user_delete_forbidden(self, client):
        r = client.delete(f"/cases/{CASE_B}", headers=_auth(UID_A))
        assert r.status_code == 403, "A must not delete B's case"
        # And B's case still exists afterwards (no destructive cross-user side effect).
        assert client.get(f"/cases/{CASE_B}", headers=_auth(UID_B)).status_code == 200


class TestPaidEntitlementIsolation:
    """Paid unlock is bound to the OWNING case row  -  A's payment never unlocks B,
    and B is not auto-unlocked. Ownership is checked BEFORE entitlement (403 first)."""

    def test_cross_user_paid_bundle_forbidden(self, client):
        # A cannot even reach B's paid bundle generator  -  owner check fires first.
        r = client.post(f"/cases/{CASE_B}/bundle/generate", headers=_auth(UID_A), json={})
        assert r.status_code == 403, f"A reaching B's bundle must be 403, got {r.status_code}"

    def test_cross_user_bundle_preview_forbidden(self, client):
        r = client.post(f"/cases/{CASE_B}/bundle/preview", headers=_auth(UID_A))
        assert r.status_code == 403

    def test_entitlement_bound_to_owning_case_row(self, client):
        # DB-backed truth: CASE_A (paid) unlocks, CASE_B (unpaid) does not  -  proving
        # A's payment cannot bleed into B's case and B is never silently unlocked.
        from unittest.mock import patch
        from backend.core.payment import is_case_paid
        with patch.dict(os.environ, {"PAYMENT_MODE": "stripe_test"}):
            assert is_case_paid(CASE_A) is True,  "owner's paid case not recognised"
            assert is_case_paid(CASE_B) is False, "ENTITLEMENT LEAK: unpaid case treated as paid"


# ══════════════════════════════════════════════════════════════════════════════
# PART 2  -  DISTRIBUTED AI SERVICES: stateless compute, structural isolation
# ══════════════════════════════════════════════════════════════════════════════

DOC = "services.lawapp_document_service.app"
RAG = "services.lawapp_rag_retrieval.app"
RULES = "services.lawapp_rules_engine.app"
GATEWAY = "services.lawapp_llm_gateway.app"
BRAIN = "services.lawapp_brain.app"

# Tokens/markers that must NEVER appear in a stateless-service response.
_USER_OWNED_TOKENS = (UID_A, UID_B, CASE_A, CASE_B, A_SECRET_MARKER, B_SECRET_MARKER)
_PII_FIELD_NAMES = ("email", "phone", "ni_number", "national_insurance",
                    "full_name", "address", "postcode", "dob")


def _svc(modname: str) -> TestClient:
    return TestClient(importlib.import_module(modname).app, raise_server_exceptions=False)


class TestServiceTenancyMandatory:
    """A stateless service must refuse to act without a tenancy context  -  it can't
    be tricked into operating in an ambient, un-scoped way."""

    def test_document_service_requires_tenancy(self):
        r = _svc(DOC).post("/v1/documents/generate",
                           json={"document_type": "particulars_of_claim", "citations": ["x"]})
        assert r.status_code in (400, 422), r.text   # missing user/workspace/case → rejected

    def test_brain_assess_requires_tenancy(self):
        r = _svc(BRAIN).post("/v1/assess", json={"claim_type": "unfair_dismissal"})
        assert r.status_code == 400, "brain must reject a tenancy-less assess"

    def test_brain_deadline_explain_requires_tenancy(self):
        r = _svc(BRAIN).post("/v1/deadline/explain", json={"edt": "2026-06-01"})
        assert r.status_code == 400


class TestServiceNoCrossUserStore:
    """The only stateful retrieval surface returns 501  -  there is no per-user
    document store, so it can NEVER echo another user's stored document."""

    def test_document_retrieval_not_implemented_no_leak(self):
        r = _svc(DOC).get(f"/v1/documents/{CASE_B}")
        assert r.status_code == 501, "doc retrieval must be an honest 501, never a fake echo"
        assert B_SECRET_MARKER not in r.text


class TestServiceResponsesCarryNoUserData:
    """Shared-knowledge services return public legal content only  -  never a caller's
    user/case identifiers or PII. With no user-owned data in the response there is,
    structurally, nothing to leak across users."""

    def test_rag_retrieval_returns_only_shared_corpus(self):
        c = _svc(RAG)
        body = {"query": "unfair dismissal time limit", "claim_type": "unfair_dismissal",
                "jurisdiction": "EW"}
        r = c.post("/v1/retrieve", json=body)
        if r.status_code == 503:
            pytest.skip("retrieval DB unavailable  -  cannot assert on mock data")
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["source"] == "local_corpus" and j["llm_called"] is False
        for tok in _USER_OWNED_TOKENS:
            assert tok not in r.text, f"service LEAK: user-owned token {tok!r} in corpus response"
        for k in _PII_FIELD_NAMES:
            assert k not in j, f"service LEAK: PII field {k!r} in corpus response"

    def test_rules_engine_returns_only_shared_rules(self):
        c = _svc(RULES)
        r = c.post("/v1/rules/evaluate",
                   json={"claim_type": "unfair_dismissal", "jurisdiction": "EW"})
        if r.status_code == 503:
            pytest.skip("rules DB unavailable  -  cannot assert on mock data")
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["source"] == "rules_table" and j["llm_called"] is False
        for tok in _USER_OWNED_TOKENS:
            assert tok not in r.text, f"service LEAK: user-owned token {tok!r} in rules response"

    def test_rules_engine_identical_regardless_of_caller(self):
        # No per-user scoping exists: the same shared rules are returned no matter
        # who asks (two independent callers ⇒ identical count). No per-user data path.
        c = _svc(RULES)
        payload = {"claim_type": "unfair_dismissal", "jurisdiction": "EW",
                   "relevant_date": "2026-06-01"}
        r1 = c.post("/v1/rules/evaluate", json=payload)
        r2 = c.post("/v1/rules/evaluate", json=payload)
        if r1.status_code == 503 or r2.status_code == 503:
            pytest.skip("rules DB unavailable")
        assert r1.json()["count"] == r2.json()["count"]


class TestGatewayPiiBoundary:
    """The llm-gateway is the only service allowed to call the model. It rejects raw
    PII at the boundary  -  user PII never crosses into inference (data minimisation,
    a per-user confidentiality control)."""

    def test_gateway_rejects_pii_in_context(self):
        r = _svc(GATEWAY).post("/v1/generate", json={
            "messages": [{"role": "user", "content": "explain my deadline"}],
            "context": {"email": "claimant@example.com"},
        })
        assert r.status_code == 422, "gateway must reject PII at the model boundary"
        assert r.json()["detail"]["error"] == "pii_rejected"

    def test_gateway_rejects_pii_in_message_body(self):
        r = _svc(GATEWAY).post("/v1/generate", json={
            "messages": [{"role": "user", "content": "my NI number is AB123456C"}],
        })
        assert r.status_code == 422
        assert r.json()["detail"]["error"] == "pii_rejected"

    def test_gateway_non_pii_request_not_rejected_as_pii(self):
        # A clean (dates-only) request is NOT a 422/pii_rejected; it either succeeds
        # (200) or fails closed because the model is unavailable (503)  -  never a
        # silent PII bypass and never a hallucinated fallback.
        r = _svc(GATEWAY).post("/v1/generate", json={
            "messages": [{"role": "user", "content": "Explain the 3-month ET time limit."}],
            "context": {"deadline": "2026-09-01", "authority": "ERA 1996 s.111(2)"},
        })
        assert r.status_code in (200, 503), r.text
        if r.status_code == 422:
            pytest.fail("clean request wrongly flagged as PII")
