-- 076_agentic_foundation.sql
-- Phase 1 agentic scaffolding: user corrections, masked agent memory,
-- extended brain_traces compliance fields. Idempotent; additive only.

-- ── agent_feedback: user corrections on assessments (auth-gated API) ─────────
CREATE TABLE IF NOT EXISTS agent_feedback (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    case_id         UUID,
    trace_id        TEXT,
    correction_type TEXT NOT NULL DEFAULT 'factual',
    original_excerpt TEXT,
    corrected_value  TEXT NOT NULL,
    comment          TEXT,
    status           TEXT NOT NULL DEFAULT 'pending',
    pii_stripped     BOOLEAN NOT NULL DEFAULT false,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_feedback_user_idx  ON agent_feedback (user_id);
CREATE INDEX IF NOT EXISTS agent_feedback_trace_idx ON agent_feedback (trace_id);
CREATE INDEX IF NOT EXISTS agent_feedback_status_idx ON agent_feedback (status);

-- ── agent_memory: long-lived masked memories (consent-gated writes) ─────────
CREATE TABLE IF NOT EXISTS agent_memory (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL,
    case_id      UUID,
    memory_key   TEXT NOT NULL,
    memory_value JSONB NOT NULL DEFAULT '{}',
    masked_value JSONB NOT NULL DEFAULT '{}',
    memory_type  TEXT NOT NULL DEFAULT 'preference',
    consent_given BOOLEAN NOT NULL DEFAULT false,
    expires_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_memory_user_case_idx ON agent_memory (user_id, case_id);

-- ── brain_traces: compliance + orchestration audit ─────────────────────────
ALTER TABLE brain_traces
    ADD COLUMN IF NOT EXISTS compliance_verdict       TEXT,
    ADD COLUMN IF NOT EXISTS reasoning_chain_summary  JSONB,
    ADD COLUMN IF NOT EXISTS orchestration_stages     JSONB NOT NULL DEFAULT '[]';
