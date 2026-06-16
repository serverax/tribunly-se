-- Migration 047: Full authentication stack
-- ----------------------------------------------------------------------------
-- Adds the schema for the lawapp auth stack (backend/core/auth/*):
--   * extra user columns (verification, MFA-ready, provenance)
--   * auth_sessions       -  refresh-token-backed sessions (rotation + logout-all)
--   * auth_tokens         -  single-use opaque tokens (magic link / verify / reset)
--   * oauth_identities    -  provider account linkage (google/microsoft/apple/linkedin)
--   * auth_events         -  immutable audit trail for every auth action
--
-- GUARDRAILS encoded here:
--   * refresh tokens are stored ONLY as SHA-256 hashes (token_hash / refresh_token_hash);
--     the raw token never touches the DB.
--   * IP addresses are stored ONLY as salted hashes (ip_hash)  -  no raw PII at rest.
--   * auth_events is append-only audit (never updated/deleted by the app).
-- Additive + idempotent (IF NOT EXISTS)  -  safe to re-run.
-- ----------------------------------------------------------------------------

-- ── users: verification, MFA-readiness, provenance ──────────────────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified        boolean     NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name          text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled           boolean     NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_secret            text;        -- TOTP secret (MFA-ready; encrypted at app layer when populated)
ALTER TABLE users ADD COLUMN IF NOT EXISTS primary_auth_provider text        NOT NULL DEFAULT 'password';
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at         timestamptz;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_updated_at   timestamptz;

-- Case-insensitive email uniqueness (registration + login normalise to lower()).
CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_uidx ON users (lower(email));

-- ── auth_sessions: one row per issued refresh token ─────────────────────────
-- A "session" == a refresh token. Access tokens are short-lived JWTs carrying
-- this session id (sid). Logout-all = revoke every non-revoked row for a user.
CREATE TABLE IF NOT EXISTS auth_sessions (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash text        NOT NULL UNIQUE,          -- SHA-256(raw refresh token)
    issued_at          timestamptz NOT NULL DEFAULT now(),
    expires_at         timestamptz NOT NULL,
    revoked_at         timestamptz,                          -- set on logout / rotation / reuse
    revoked_reason     text,                                 -- logout | rotated | reuse_detected | logout_all
    rotated_to         uuid        REFERENCES auth_sessions(id) ON DELETE SET NULL,
    mfa_satisfied      boolean     NOT NULL DEFAULT true,    -- false while an MFA challenge is pending
    user_agent         text,
    ip_hash            text,                                 -- salted SHA-256 of client IP (no raw PII)
    created_at         timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS refresh_token_hash text;
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS issued_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS revoked_reason text;
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS rotated_to uuid REFERENCES auth_sessions(id) ON DELETE SET NULL;
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS mfa_satisfied boolean NOT NULL DEFAULT true;
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS ip_hash text;
DO $$
BEGIN
  IF EXISTS (
       SELECT 1 FROM information_schema.columns
       WHERE table_schema='public'
         AND table_name='auth_sessions'
         AND column_name='session_token_hash'
  ) THEN
    EXECUTE $sql$
      UPDATE auth_sessions
         SET refresh_token_hash = COALESCE(refresh_token_hash, session_token_hash)
       WHERE refresh_token_hash IS NULL
    $sql$;
  END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS auth_sessions_refresh_token_hash_uidx
    ON auth_sessions (refresh_token_hash)
    WHERE refresh_token_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS auth_sessions_user_idx   ON auth_sessions (user_id);
CREATE INDEX IF NOT EXISTS auth_sessions_active_idx ON auth_sessions (user_id) WHERE revoked_at IS NULL;

-- ── auth_tokens: single-use opaque tokens ───────────────────────────────────
CREATE TABLE IF NOT EXISTS auth_tokens (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash   text        NOT NULL UNIQUE,                -- SHA-256(raw token)
    purpose      text        NOT NULL,                       -- magic_link | email_verify | password_reset
    expires_at   timestamptz NOT NULL,
    consumed_at  timestamptz,                                -- set when redeemed (single-use)
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS auth_tokens_user_purpose_idx ON auth_tokens (user_id, purpose);

-- ── oauth_identities: provider account → user linkage ───────────────────────
CREATE TABLE IF NOT EXISTS oauth_identities (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider      text        NOT NULL,                      -- google | microsoft | apple | linkedin
    subject       text        NOT NULL,                      -- provider stable 'sub' claim
    email         text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz,
    UNIQUE (provider, subject)
);
CREATE INDEX IF NOT EXISTS oauth_identities_user_idx ON oauth_identities (user_id);

-- ── auth_events: append-only audit trail ────────────────────────────────────
CREATE TABLE IF NOT EXISTS auth_events (
    id              bigserial   PRIMARY KEY,
    user_id         uuid        REFERENCES users(id) ON DELETE SET NULL,
    email_attempted text,                                    -- lower()'d email for failed/unknown-user events
    event_type      text        NOT NULL,                    -- register|login_success|login_failure|logout|logout_all|refresh|refresh_reuse|magic_link_issued|magic_link_consumed|email_verify_issued|email_verified|password_reset_requested|password_reset_completed|oauth_login
    provider        text,                                    -- password|magic_link|google|microsoft|apple|linkedin
    success         boolean     NOT NULL,
    trace_id        text,                                    -- == request X-Request-ID / Brain trace_id
    ip_hash         text,
    user_agent      text,
    detail          jsonb,                                   -- structured, NEVER contains secrets/tokens/raw PII
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS auth_events_user_idx    ON auth_events (user_id);
CREATE INDEX IF NOT EXISTS auth_events_type_idx    ON auth_events (event_type);
CREATE INDEX IF NOT EXISTS auth_events_created_idx ON auth_events (created_at);
