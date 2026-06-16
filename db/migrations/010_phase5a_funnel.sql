-- Migration 010: Phase 5A  -  funnel event tracking
-- Stores funnel events locally. No external analytics. case_id optional.
-- GUARDRAIL: metadata must not contain raw personal facts or file content.

CREATE TABLE IF NOT EXISTS funnel_events (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id     uuid        REFERENCES cases(id) ON DELETE SET NULL,
    event_name  text        NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    metadata    jsonb       -- no PII, no raw uploaded text
);

CREATE INDEX IF NOT EXISTS fe_case_idx  ON funnel_events (case_id);
CREATE INDEX IF NOT EXISTS fe_event_idx ON funnel_events (event_name);
