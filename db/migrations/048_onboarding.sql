-- 048_onboarding.sql
-- SUBAGENT: Onboarding Engineer.
-- (Numbered 048 to avoid a collision with the untracked 047_auth_stack.sql.)
--
-- Post-signup onboarding wizard support.
--
-- 1. User profile fields captured during onboarding (name, role, employer).
--    `role` is a free-text canonical slug (employee | former_employee |
--    solicitor | hr | union_rep | insurer | other) — validated at the API
--    layer, not by a DB CHECK, so new role types can be added without a
--    migration. `onboarded_at` is the idempotency marker: a NON-NULL value
--    means the user has completed onboarding and the API will NOT create a
--    second onboarding case.
--
-- 2. cases.case_title — human-readable label for a case (the existing
--    claim_type column stays the machine key that drives rules/deadline logic).
--    cases.created_from — provenance of the row ('onboarding' | 'assessment' |
--    'manual'); lets us distinguish the auto-created onboarding shell case from
--    a real saved diagnosis.
--
-- Idempotent (ADD COLUMN IF NOT EXISTS) — safe to re-run.

BEGIN;

-- ── User onboarding profile ─────────────────────────────────────────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name      text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role           text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS employer_name  text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarded_at   timestamptz;

-- ── Case labelling + provenance ─────────────────────────────────────────────
ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_title    text;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS created_from  text NOT NULL DEFAULT 'assessment';

-- Find a user's auto-created onboarding case quickly (idempotency lookup).
CREATE INDEX IF NOT EXISTS cases_user_created_from_idx
    ON cases (user_id, created_from)
    WHERE deleted_at IS NULL;

COMMIT;
