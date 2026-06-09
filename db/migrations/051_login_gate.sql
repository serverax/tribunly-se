-- 051_login_gate.sql
-- SUBAGENT 3: Login Gate Engineer.
--
-- Free-tool login wall: encrypted temporary state for the anonymous teaser flow.
--
-- (Numbered 051 to avoid collisions with sibling subagent migrations
--  049_conversion_funnel / 050_auth_canonical_views.)
--
-- An anonymous visitor may answer the free-tool teaser questions WITHOUT logging
-- in. Those answers are stored here ENCRYPTED AT REST (Fernet, same key family as
-- cases.facts_encrypted) and addressed by a high-entropy resume token. Only the
-- SHA-256 HASH of that token is stored — the raw token is returned to the client
-- once and never persisted, so a DB read alone cannot resume a session.
--
-- When the visitor logs in, they present the resume token; the row is "claimed"
-- (bound to their user id) and the saved answers are restored EXACTLY — no lost
-- answers. A row already claimed by another user is rejected (no cross-user theft).
--
-- Idempotent (CREATE ... IF NOT EXISTS) — safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS teaser_sessions (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- SHA-256 hex of the raw resume token. The raw token is NEVER stored.
    resume_token_hash   text NOT NULL UNIQUE,

    -- Free-tool identifier (e.g. 'employment_rights_check'). Not sensitive.
    tool                text NOT NULL,

    -- Fernet-encrypted JSON of the teaser answers. Plaintext never stored.
    state_encrypted     bytea NOT NULL,
    encryption_version  text  NOT NULL DEFAULT 'fernet_v1',

    -- Set on resume-after-login. NULL while the session is still anonymous.
    claimed_by_user_id  uuid REFERENCES users(id) ON DELETE CASCADE,
    claimed_at          timestamptz,

    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    -- Temporary state is short-lived; a sweeper deletes expired anonymous rows.
    expires_at          timestamptz NOT NULL DEFAULT (now() + interval '7 days')
);

-- Resume lookup is a point read on the token hash (already UNIQUE → indexed).
-- This partial index supports the expiry sweeper (delete unclaimed expired rows).
CREATE INDEX IF NOT EXISTS teaser_sessions_expires_idx
    ON teaser_sessions (expires_at)
    WHERE claimed_by_user_id IS NULL;

COMMIT;
