"""
Legacy ↔ canonical route security parity (route-repair regression suite).

Background — a QA audit found the legacy `@app` shim routes in backend/api/main.py
did NOT enforce the same auth/payment gates as their canonical equivalents:

  * POST /api/payment/create-session   returned 200 unauthenticated (canonical 401)
  * POST /documents/generate           ran past the auth check (no explicit 401)
  * GET  /api/documents/{id}/download  served files with NO auth gate, ownership
                                       skipped when user_id was None, and NO payment
                                       check at all — an unauthenticated document leak.

These tests pin the fix: every legacy shim must block unauthenticated callers and must
never deliver a paid document to an unpaid caller, matching the canonical route.

Auth: LAWAPP_AUTH_MODE=mock (conftest) → the X-User-ID header is the identity, and an
ABSENT header means unauthenticated. PAYMENT_MODE=disabled (conftest) → paid output
blocked unless the DB says the case is paid.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from ingestion.db import get_connection

client = TestClient(app)

ZERO_UUID = "00000000-0000-0000-0000-000000000000"

# (method, path) pairs — canonical first, legacy second, grouped by capability.
PROTECTED_ROUTES = [
    ("post", "/api/payments/create-session"),   # canonical payment
    ("post", "/api/payment/create-session"),    # legacy payment shim
    ("post", "/api/documents/generate"),        # canonical document generate
    ("post", "/documents/generate"),            # legacy self-help draft shim
    ("get",  f"/api/documents/{ZERO_UUID}"),    # canonical download
    ("get",  f"/api/documents/{ZERO_UUID}/download"),  # legacy download shim
    ("get",  "/api/payment/status"),            # legacy payment-mode shim
]

# A body that satisfies both request schemas (canonical needs case_id+document_type;
# legacy /documents/generate additionally needs assessment+facts).
_FULL_BODY = {
    "case_id": ZERO_UUID,
    "document_type": "particulars_of_claim",
    "assessment": {"status": "ok", "citations": []},
    "facts": {},
    "confirmed_facts": {},
}


@pytest.fixture()
def unpaid_case():
    """Seed a real, owned, UNPAID case; yield (user_id, case_id); clean up after."""
    user_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # cases.user_id has a FK to users(id) — seed the user first.
            cur.execute(
                "INSERT INTO users (id) VALUES (%s::uuid) ON CONFLICT (id) DO NOTHING",
                (user_id,),
            )
            cur.execute(
                """
                INSERT INTO cases (user_id, claim_type, jurisdiction, payment_status)
                VALUES (%s::uuid, %s, %s, %s)
                RETURNING id
                """,
                (user_id, "unfair_dismissal", "EW", "unpaid"),
            )
            case_id = str(cur.fetchone()[0])
        conn.commit()
    finally:
        conn.close()

    yield user_id, case_id

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE case_id = %s::uuid", (case_id,))
            cur.execute("DELETE FROM cases WHERE id = %s::uuid", (case_id,))
            cur.execute("DELETE FROM users WHERE id = %s::uuid", (user_id,))
        conn.commit()
    finally:
        conn.close()


# ── 1. Unauthenticated callers are blocked on canonical AND legacy ──────────────

@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
def test_unauthenticated_blocked_on_every_route(method, path):
    """No X-User-ID header → 401 on both canonical and legacy variants."""
    resp = client.request(method, path, json=_FULL_BODY)  # NB: no auth header
    assert resp.status_code == 401, (
        f"{method.upper()} {path} must reject unauthenticated callers; "
        f"got {resp.status_code}: {resp.text[:200]}"
    )


# ── 2. Legacy shims are marked deprecated in the OpenAPI schema ─────────────────

def test_legacy_routes_are_deprecated_in_openapi():
    schema = app.openapi()
    legacy = {
        ("post", "/documents/generate"),
        ("post", "/api/payment/create-session"),
        ("get",  "/api/payment/status"),
        ("post", "/api/payment/webhook"),
        ("get",  "/api/documents/{document_id}/download"),
    }
    for method, path in legacy:
        node = schema["paths"].get(path, {}).get(method)
        assert node is not None, f"legacy route missing from schema: {method} {path}"
        assert node.get("deprecated") is True, f"{method} {path} not marked deprecated"


# ── 3. Unpaid users cannot generate a paid document (canonical) ─────────────────

def test_unpaid_cannot_generate_canonical(unpaid_case):
    user_id, case_id = unpaid_case
    resp = client.post(
        "/api/documents/generate",
        headers={"X-User-ID": user_id},
        json={"case_id": case_id, "document_type": "particulars", "confirmed_facts": {}},
    )
    assert resp.status_code == 402, (
        f"canonical generate must return 402 for an unpaid case; "
        f"got {resp.status_code}: {resp.text[:200]}"
    )


# ── 4. Legacy self-help draft never unlocks full content for an unpaid case ─────

def test_unpaid_legacy_generate_does_not_unlock(unpaid_case):
    user_id, case_id = unpaid_case
    resp = client.post(
        "/documents/generate",
        headers={"X-User-ID": user_id},
        json={
            "case_id": case_id,
            "document_type": "particulars_of_claim",
            "assessment": {"status": "ok", "citations": []},
            "facts": {},
        },
    )
    # Either it preview-gates (200 + payment_required) or hard-blocks — never a paid unlock.
    assert resp.status_code in (200, 402), f"unexpected {resp.status_code}: {resp.text[:200]}"
    if resp.status_code == 200:
        body = resp.json()
        assert body.get("payment_required") is True, (
            "legacy draft delivered content for an UNPAID case without payment_required"
        )


# ── 5. Unpaid users cannot download via the legacy alias (was unauth/no-pay leak) ─

def test_unpaid_cannot_download_legacy(unpaid_case):
    user_id, case_id = unpaid_case
    document_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (id, case_id, user_id, doc_type, storage_ref, is_user_upload)
                VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s)
                """,
                (document_id, case_id, user_id, "particulars", "/tmp/nonexistent.docx", False),
            )
        conn.commit()
    finally:
        conn.close()

    resp = client.get(
        f"/api/documents/{document_id}/download",
        headers={"X-User-ID": user_id},
    )
    assert resp.status_code == 402, (
        f"legacy download must 402 for an unpaid case (payment gate); "
        f"got {resp.status_code}: {resp.text[:200]}"
    )
