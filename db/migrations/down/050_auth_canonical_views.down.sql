-- DOWN migration for 050_auth_canonical_views.sql
-- ============================================================================
-- Reverses EXACTLY what 050 added, and nothing more. It MUST NOT touch the
-- canonical wired auth tables (auth_sessions / oauth_identities / users / auth_*)
-- — those are owned by migration 047 and carry live data. This down migration
-- only drops the canonical-name VIEWS and the reverse-lookup index that 050
-- created, so applying 050 → down → 050 round-trips cleanly.
--
-- Idempotent (IF EXISTS) — safe to re-run.
-- ============================================================================

BEGIN;

DROP VIEW  IF EXISTS onboarding_profiles;
DROP VIEW  IF EXISTS user_identities;
DROP VIEW  IF EXISTS user_sessions;
DROP INDEX IF EXISTS oauth_identities_subject_idx;

COMMIT;
