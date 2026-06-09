"""
/api/auth/* — email+password, sessions, verification, reset, logout audit.

Real HTTP via TestClient against the live DB. No mocks of the auth path.
"""

from __future__ import annotations


def _register(client, email, password="Str0ngPass!23", display_name="Test User"):
    return client.post("/api/auth/register",
                       json={"email": email, "password": password, "display_name": display_name})


# ── register + login happy path ──────────────────────────────────────────────

def test_register_returns_tokens_and_persists_user(client, unique_email, db_query):
    email = unique_email()
    resp = _register(client, email)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["trace_id"]                       # trace_id on every response
    assert body["email_verified"] is False

    row = db_query("SELECT email, primary_auth_provider, password_hash FROM users WHERE lower(email)=%s",
                   (email.lower(),), fetch="one")
    assert row is not None
    assert row[1] == "password"
    assert row[2] and row[2].startswith("pbkdf2_sha256$")   # never plaintext


def test_login_succeeds_with_correct_password(client, unique_email):
    email = unique_email()
    _register(client, email, password="Str0ngPass!23")
    resp = client.post("/api/auth/login", json={"email": email, "password": "Str0ngPass!23"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


def test_login_is_case_insensitive_on_email(client, unique_email):
    email = unique_email()
    _register(client, email.lower(), password="Str0ngPass!23")
    resp = client.post("/api/auth/login", json={"email": email.upper(), "password": "Str0ngPass!23"})
    assert resp.status_code == 200, resp.text


# ── negatives ────────────────────────────────────────────────────────────────

def test_login_wrong_password_is_401_and_audited(client, unique_email, db_query):
    email = unique_email()
    _register(client, email, password="Str0ngPass!23")
    resp = client.post("/api/auth/login", json={"email": email, "password": "wrong-password-9"})
    assert resp.status_code == 401
    rows = db_query("SELECT count(*) FROM auth_events WHERE event_type='login_failure' "
                    "AND email_attempted=%s", (email.lower(),), fetch="one")
    assert rows[0] >= 1


def test_login_unknown_user_is_401(client, unique_email):
    resp = client.post("/api/auth/login",
                       json={"email": unique_email(), "password": "whatever-123"})
    assert resp.status_code == 401


def test_weak_password_rejected(client, unique_email):
    resp = _register(client, unique_email(), password="short")
    assert resp.status_code == 400


def test_duplicate_email_is_409(client, unique_email):
    email = unique_email()
    assert _register(client, email).status_code == 201
    assert _register(client, email).status_code == 409


# ── email verification ───────────────────────────────────────────────────────

def test_email_verification_flow(client, unique_email, email_outbox, extract_token, db_query):
    email = unique_email()
    _register(client, email)
    token = extract_token(email_outbox, subject_contains="Verify")
    resp = client.post("/api/auth/verify-email", json={"token": token})
    assert resp.status_code == 200, resp.text
    assert resp.json()["verified"] is True

    verified = db_query("SELECT email_verified FROM users WHERE lower(email)=%s",
                        (email.lower(),), fetch="one")[0]
    assert verified is True

    # single-use: replay fails
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 400


# ── password reset ───────────────────────────────────────────────────────────

def test_password_reset_request_is_generic(client, unique_email):
    # Unknown email still returns a generic 200 (no enumeration).
    resp = client.post("/api/auth/password-reset", json={"email": unique_email()})
    assert resp.status_code == 200
    assert "message" in resp.json()


def test_password_reset_full_flow(client, unique_email, email_outbox, extract_token):
    email = unique_email()
    _register(client, email, password="Str0ngPass!23")

    assert client.post("/api/auth/password-reset", json={"email": email}).status_code == 200
    token = extract_token(email_outbox, subject_contains="Reset")

    new_pw = "Br4ndNewPass!9"
    confirm = client.post("/api/auth/password-reset",
                          json={"token": token, "new_password": new_pw})
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["reset"] is True

    # old password no longer works; new one does
    assert client.post("/api/auth/login",
                       json={"email": email, "password": "Str0ngPass!23"}).status_code == 401
    assert client.post("/api/auth/login",
                       json={"email": email, "password": new_pw}).status_code == 200

    # reset token is single-use
    assert client.post("/api/auth/password-reset",
                       json={"token": token, "new_password": "An0therPass!1"}).status_code == 400


def test_password_reset_revokes_existing_sessions(client, unique_email, email_outbox,
                                                  extract_token, db_query):
    email = unique_email()
    reg = _register(client, email, password="Str0ngPass!23").json()
    old_refresh = reg["refresh_token"]

    client.post("/api/auth/password-reset", json={"email": email})
    token = extract_token(email_outbox, subject_contains="Reset")
    client.post("/api/auth/password-reset", json={"token": token, "new_password": "Br4ndNewPass!9"})

    # the pre-reset refresh token must no longer work
    assert client.post("/api/auth/refresh", json={"refresh_token": old_refresh}).status_code == 400


# ── refresh / session expiration ─────────────────────────────────────────────

def test_refresh_rotates_and_old_token_is_rejected(client, unique_email):
    reg = _register(client, unique_email()).json()
    r1 = reg["refresh_token"]
    rot = client.post("/api/auth/refresh", json={"refresh_token": r1})
    assert rot.status_code == 200, rot.text
    r2 = rot.json()["refresh_token"]
    assert r2 and r2 != r1
    # reusing the rotated (old) token is detected and rejected
    assert client.post("/api/auth/refresh", json={"refresh_token": r1}).status_code == 400


def test_refresh_reuse_revokes_whole_chain(client, unique_email, db_query):
    reg = _register(client, unique_email()).json()
    user_id = reg["user_id"]
    r1 = reg["refresh_token"]
    r2 = client.post("/api/auth/refresh", json={"refresh_token": r1}).json()["refresh_token"]
    # replay the old token → reuse detected
    assert client.post("/api/auth/refresh", json={"refresh_token": r1}).status_code == 400
    # the legitimate-looking newer token is now revoked too (chain killed)
    assert client.post("/api/auth/refresh", json={"refresh_token": r2}).status_code == 400
    active = db_query("SELECT count(*) FROM auth_sessions WHERE user_id=%s::uuid AND revoked_at IS NULL",
                      (user_id,), fetch="one")[0]
    assert active == 0
    audited = db_query("SELECT count(*) FROM auth_events WHERE user_id=%s::uuid "
                       "AND event_type='refresh_reuse'", (user_id,), fetch="one")[0]
    assert audited >= 1


def test_expired_refresh_token_rejected(client, unique_email, db_query):
    reg = _register(client, unique_email()).json()
    r1 = reg["refresh_token"]
    sid = reg["session_id"]
    # force the session to be expired in the DB
    db_query("UPDATE auth_sessions SET expires_at = now() - interval '1 hour' WHERE id=%s::uuid",
             (sid,), fetch="none")
    assert client.post("/api/auth/refresh", json={"refresh_token": r1}).status_code == 400


# ── logout + concurrent sessions ─────────────────────────────────────────────

def test_logout_revokes_single_session_and_audits(client, unique_email, db_query):
    reg = _register(client, unique_email()).json()
    user_id, refresh = reg["user_id"], reg["refresh_token"]
    resp = client.post("/api/auth/logout", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert client.post("/api/auth/refresh", json={"refresh_token": refresh}).status_code == 400
    logged = db_query("SELECT count(*) FROM auth_events WHERE user_id=%s::uuid AND event_type='logout'",
                      (user_id,), fetch="one")[0]
    assert logged >= 1


def test_concurrent_sessions_and_logout_all(client, unique_email, db_query):
    email = unique_email()
    _register(client, email, password="Str0ngPass!23")
    s1 = client.post("/api/auth/login", json={"email": email, "password": "Str0ngPass!23"}).json()
    s2 = client.post("/api/auth/login", json={"email": email, "password": "Str0ngPass!23"}).json()
    user_id = s1["user_id"]

    active = db_query("SELECT count(*) FROM auth_sessions WHERE user_id=%s::uuid AND revoked_at IS NULL",
                      (user_id,), fetch="one")[0]
    assert active >= 2     # at least the two explicit logins (register also made one)

    # logout-all requires a bearer access token; revokes every session
    out = client.post("/api/auth/logout", json={"all_sessions": True},
                      headers={"Authorization": f"Bearer {s2['access_token']}"})
    assert out.status_code == 200
    assert out.json()["scope"] == "all"

    active_after = db_query("SELECT count(*) FROM auth_sessions WHERE user_id=%s::uuid "
                            "AND revoked_at IS NULL", (user_id,), fetch="one")[0]
    assert active_after == 0
    # both refresh tokens now dead
    assert client.post("/api/auth/refresh", json={"refresh_token": s1["refresh_token"]}).status_code == 400
    assert client.post("/api/auth/refresh", json={"refresh_token": s2["refresh_token"]}).status_code == 400


def test_logout_all_without_bearer_is_401(client):
    assert client.post("/api/auth/logout", json={"all_sessions": True}).status_code == 401
