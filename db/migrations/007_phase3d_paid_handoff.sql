-- Migration 007: Phase 3D  -  handoff leads
-- Stores contact information voluntarily submitted by users requesting solicitor referral.
-- NOTE: contains PII (name, email). Phase 3D is local/test-only.
-- Encryption at rest required before production deployment (Phase 5).

CREATE TABLE IF NOT EXISTS handoff_leads (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         uuid        REFERENCES cases(id) ON DELETE SET NULL,
    trigger_reason  text        NOT NULL,   -- seek_solicitor | insufficient_grounding | low_confidence
    name            text        NOT NULL,
    email           text        NOT NULL,
    phone           text,
    case_summary    text,
    consent_given   boolean     NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT handoff_leads_consent_required CHECK (consent_given = true)
);

CREATE INDEX IF NOT EXISTS handoff_leads_created_idx ON handoff_leads (created_at);
CREATE INDEX IF NOT EXISTS handoff_leads_trigger_idx ON handoff_leads (trigger_reason);
