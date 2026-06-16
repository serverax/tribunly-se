-- Migration 019  -  Brain Phase 1: Safety Boundary + Context Compression Audit Tables
-- Created as part of PHASE 1 Brain Algorithm foundation.
--
-- New tables:
--   safety_boundary_checks   -  immutable log of every safety policy check at Brain step 16
--   context_compression_log  -  log of context compression metrics at Brain step 13
--
-- These tables are APPEND-ONLY. No UPDATE or DELETE is permitted at app level.

-- ── safety_boundary_checks ───────────────────────────────────────────────────
-- Records every invocation of the Brain's "apply_safety_policy" step (step 16).
-- Each row is one check within one Brain run.
-- A blocked=true row means the answer was suppressed.

CREATE TABLE IF NOT EXISTS safety_boundary_checks (
    id              BIGSERIAL PRIMARY KEY,
    trace_id        TEXT        REFERENCES brain_traces (trace_id) ON DELETE SET NULL,
    user_id         UUID,
    check_name      TEXT        NOT NULL,          -- e.g. "guarantee_language", "reserved_activity", "pii_in_output"
    passed          BOOLEAN     NOT NULL,
    failure_reason  TEXT,                          -- null if passed
    blocked         BOOLEAN     NOT NULL DEFAULT false,
    severity        TEXT        NOT NULL DEFAULT 'medium', -- critical | high | medium | low
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS safety_boundary_trace_idx ON safety_boundary_checks (trace_id);
CREATE INDEX IF NOT EXISTS safety_boundary_passed_idx ON safety_boundary_checks (passed);
CREATE INDEX IF NOT EXISTS safety_boundary_blocked_idx ON safety_boundary_checks (blocked);

-- ── context_compression_log ──────────────────────────────────────────────────
-- Records context compression metrics at Brain step 13.
-- Used to monitor compression efficiency and identify retrieval bloat.

CREATE TABLE IF NOT EXISTS context_compression_log (
    id                  BIGSERIAL PRIMARY KEY,
    trace_id            TEXT,                      -- not FK  -  may be written before brain_traces row
    original_tokens     INTEGER     NOT NULL DEFAULT 0,
    compressed_tokens   INTEGER     NOT NULL DEFAULT 0,
    citations_preserved INTEGER     NOT NULL DEFAULT 0,
    rules_preserved     INTEGER     NOT NULL DEFAULT 0,
    compression_ratio   FLOAT       NOT NULL DEFAULT 1.0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS context_compression_trace_idx ON context_compression_log (trace_id);

-- ── brain_traces: add missing_facts and rag_sources columns (if not present) ─
-- These columns are added by this migration to support the 19-step Brain.
-- Using DO $$ to avoid errors if columns already exist.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'brain_traces' AND column_name = 'missing_facts'
    ) THEN
        ALTER TABLE brain_traces ADD COLUMN missing_facts JSONB NOT NULL DEFAULT '[]';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'brain_traces' AND column_name = 'rag_sources'
    ) THEN
        ALTER TABLE brain_traces ADD COLUMN rag_sources JSONB NOT NULL DEFAULT '[]';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'brain_traces' AND column_name = 'safety_passed'
    ) THEN
        ALTER TABLE brain_traces ADD COLUMN safety_passed BOOLEAN;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'brain_traces' AND column_name = 'memory_saved'
    ) THEN
        ALTER TABLE brain_traces ADD COLUMN memory_saved BOOLEAN NOT NULL DEFAULT false;
    END IF;
END
$$;
