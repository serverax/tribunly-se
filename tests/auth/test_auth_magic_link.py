"""
/api/auth/magic-link — passwordless sign-in (issue + consume).

Delivery is asserted against the in-memory email outbox; consuming the link
yields a real session and marks the email verified.
"""

from __future__ import annotations


def test_magic_link_request_is_generic_and_delivers(client, unique_email, email_outbox):
    email = unique_email()
    resp = client.post("/api/auth/magic-link", json={"email": email})
    assert resp.status_code == 200
    assert "message" in resp.json()
    assert resp.json()["trace_id"]
    # delivery proof: a sign-in email landed in the outbox
    assert any("sign-in" in m.subject.lower() for m in email_outbox)


def test_magic_link_consume_creates_session(client, unique_email, email_outbox,
                                            extract_token, db_query):
    email = unique_email()
    client.post("/api/auth/magic-link", json={"email": email})
    token = extract_token(email_outbox, subject_contains="sign-in")

    resp = client.post("/api/auth/magic-link", json={"token": token})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["email_verified"] is True

    verified = db_query("SELECT email_verified FROM users WHERE lower(email)=%s",
                        (email.lower(),), fetch="one")[0]
    assert verified is True

    # single-use: the same link cannot be redeemed twice
    assert client.post("/api/auth/magic-link", json={"token": token}).status_code == 400


def test_magic_link_invalid_token_rejected(client):
    assert client.post("/api/auth/magic-link",
                       json={"token": "not-a-real-token"}).status_code == 400


def test_magic_link_issue_is_audited(client, unique_email, email_outbox, db_query):
    email = unique_email()
    client.post("/api/auth/magic-link", json={"email": email})
    n = db_query("SELECT count(*) FROM auth_events WHERE event_type='magic_link_issued' "
                 "AND email_attempted=%s", (email.lower(),), fetch="one")[0]
    assert n >= 1
