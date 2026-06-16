-- Migration 081: Admin audit extensions + reviewer role flag
-- Additive only. Extends brain_traces for AI audit panel; adds users.is_admin.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE brain_traces
    ADD COLUMN IF NOT EXISTS input_summary      TEXT,
    ADD COLUMN IF NOT EXISTS retrieved_sources  JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS reasoning_trace    JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS confidence         DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS model_version      TEXT;

CREATE INDEX IF NOT EXISTS brain_traces_created_idx ON brain_traces (created_at DESC);
CREATE INDEX IF NOT EXISTS brain_traces_compliance_idx ON brain_traces (compliance_verdict);
