-- Migration 050: Auth DB — canonical entity-name views + provider_id index
-- ============================================================================
-- SUBAGENT 8 — Database Engineer (Landing Page + Authentication Experience).
--
-- CONTEXT / HONEST RECONCILIATION
-- -------------------------------
-- The lawapp auth stack already exists and is WIRED to live code
-- (backend/core/auth/service.py, migration 047_auth_stack.sql):
--
--     users             — real table  (identity + verification + onboarding cols)
--     auth_sessions     — real table  (one row per issued refresh token)
--     oauth_identities  — real table  (provider account → user linkage)
--     auth_tokens       — real table  (single-use magic-link / verify / reset)
--     auth_events       — real table  (append-only auth audit trail)
--
-- The auth SERVICE issues/rotates/revokes sessions against `auth_sessions` and
-- links providers against `oauth_identities`. Those are the SINGLE SOURCE OF
-- TRUTH. Creating second base tables named `user_sessions` / `user_identities`
-- would fork the auth schema into two competing copies of the session/identity
-- store — a security hazard and a forbidden parallel/dead schema
-- (BEHAVIOUR_CONSTITUTION §4 "no DB tables that are never used", §10 "avoid
-- duplicated logic", §19 "broken user isolation can expose private legal data").
--
-- Therefore the requested entity NAMES are provided here as canonical VIEWS over
-- the wired tables (one source of truth, zero duplication, no second writer):
--
--     user_sessions        VIEW → auth_sessions     (exposes session_id)
--     user_identities      VIEW → oauth_identities  (exposes provider_id)
--     onboarding_profiles  VIEW → users             (onboarding columns; 1/user)
--
-- conversion_events is the SIXTH required entity. It is a genuinely-new ANONYMOUS
-- acquisition-funnel table owned by SUBAGENT 5 (migration 049_conversion_funnel.sql)
-- — keyed on an anonymous visitor session_id that exists BEFORE any user. It is a
-- dependency of this work, not redefined here (redefining it would duplicate a
-- table another subagent owns). 050 must be applied AFTER 049.
--
-- INDEXES required by the task:
--     email       → users_email_lower_uidx (UNIQUE lower(email))      [047, exists]
--     provider_id → oauth_identities_provider_subject_key (UNIQUE)    [047, exists]
--                   + oauth_identities_subject_idx (added below — reverse lookup)
--     session_id  → auth_sessions_pkey (PRIMARY KEY id)               [047, exists]
--
-- Additive + idempotent (IF NOT EXISTS / CREATE OR REPLACE) — safe to re-run.
-- Reversible — db/migrations/down/050_auth_canonical_views.down.sql
-- ============================================================================

BEGIN;

-- ── provider_id reverse-lookup index ─────────────────────────────────────────
-- oauth_identities already has UNIQUE(provider, subject) — the (provider, account)
-- key that prevents two users claiming the same provider account (= provider
-- merge integrity). A lookup by the provider account id (subject / provider_id)
-- ALONE — "which identity owns provider_id X" — is not served by that composite
-- key, so add a dedicated index. Genuinely useful, not a placeholder. Idempotent.
CREATE INDEX IF NOT EXISTS oauth_identities_subject_idx ON oauth_identities (subject);

-- Existing shared databases may already have an auth_sessions table from an
-- earlier/non-LawApp schema. Add the canonical LawApp session columns before
-- creating the view so this migration remains idempotent.
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS refresh_token_hash text;
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS issued_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS revoked_reason text;
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS rotated_to uuid REFERENCES auth_sessions(id) ON DELETE SET NULL;
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS mfa_satisfied boolean NOT NULL DEFAULT true;
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS ip_hash text;
UPDATE auth_sessions
   SET refresh_token_hash = COALESCE(refresh_token_hash, session_token_hash)
 WHERE refresh_token_hash IS NULL
   AND EXISTS (
       SELECT 1 FROM information_schema.columns
       WHERE table_schema='public'
         AND table_name='auth_sessions'
         AND column_name='session_token_hash'
   );
CREATE UNIQUE INDEX IF NOT EXISTS auth_sessions_refresh_token_hash_uidx
    ON auth_sessions (refresh_token_hash)
    WHERE refresh_token_hash IS NOT NULL;

-- ── user_sessions: canonical-name VIEW over the wired auth_sessions table ─────
-- `session_id` is the stable identifier the rest of the product refers to; it is
-- the auth_sessions primary key (indexed by auth_sessions_pkey). `is_active` is a
-- derived convenience flag (a live, non-revoked, non-expired session).
DO $$
BEGIN
    IF to_regclass('public.user_sessions') IS NULL
       OR EXISTS (
           SELECT 1
           FROM pg_class c
           JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public'
             AND c.relname = 'user_sessions'
             AND c.relkind = 'v'
       )
    THEN
        EXECUTE $view$
            CREATE OR REPLACE VIEW user_sessions AS
            SELECT
                id                  AS session_id,
                id,
                user_id,
                refresh_token_hash,
                issued_at,
                expires_at,
                revoked_at,
                revoked_reason,
                rotated_to,
                mfa_satisfied,
                user_agent,
                ip_hash,
                created_at,
                (revoked_at IS NULL AND expires_at > now()) AS is_active
            FROM auth_sessions
        $view$;
    ELSE
        RAISE NOTICE 'Skipping user_sessions view because a non-view relation already exists.';
    END IF;
END $$;

-- ── user_identities: canonical-name VIEW over the wired oauth_identities ──────
-- `provider_id` is the provider's stable account identifier (the OIDC `sub`
-- claim, stored as `subject`). UNIQUE(provider, subject) on the base table
-- guarantees one identity per provider account (account linking + provider
-- merge integrity: a provider account cannot be linked to two users).
CREATE OR REPLACE VIEW user_identities AS
SELECT
    id,
    user_id,
    provider,
    subject             AS provider_id,
    subject,
    email,
    created_at,
    last_login_at
FROM oauth_identities;

-- ── onboarding_profiles: 1:1 VIEW of the onboarding fields stored on users ───
-- Onboarding data (role / full_name / employer) is persisted on `users` by the
-- wired POST /onboarding/complete route (migration 048). This view exposes it
-- under the requested entity name without forking storage. `onboarding_complete`
-- is the derived flag (onboarded_at IS NOT NULL) the wizard uses for idempotency.
CREATE OR REPLACE VIEW onboarding_profiles AS
SELECT
    id                          AS user_id,
    full_name,
    role,
    employer_name,
    onboarded_at,
    (onboarded_at IS NOT NULL)  AS onboarding_complete
FROM users;

COMMIT;
