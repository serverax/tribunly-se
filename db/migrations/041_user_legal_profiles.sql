-- 041_user_legal_profiles.sql
-- Sovereign architecture: stores employment variables extracted from a user's
-- unstructured narrative (reverse data flow / LLM-driven structured extraction).
-- Per the order's DDL. Idempotent + additive. Isolation is enforced at the
-- application layer (user_id), not Postgres RLS (this stack does not set
-- request.jwt.claim.* session vars).
CREATE TABLE IF NOT EXISTS user_legal_profiles (
    user_id              UUID PRIMARY KEY,
    employment_type      VARCHAR(50) NOT NULL DEFAULT 'unknown',
    tenure_months        INTEGER NOT NULL DEFAULT 0,
    has_probation_clause BOOLEAN NOT NULL DEFAULT FALSE,
    recent_incident      TEXT,
    alleged_violation    TEXT,
    start_date           DATE,
    jurisdiction_code    TEXT,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
