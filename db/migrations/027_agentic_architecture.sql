-- 027_agentic_architecture.sql
-- 4-agent architecture audit/observability tables (AC-005, AC-010).
-- UUID primary keys; every row carries trace_id (UUID) for OTEL correlation.
-- Idempotent (IF NOT EXISTS); additive only.

-- agent_runs: one row per agent invocation
CREATE TABLE IF NOT EXISTS agent_runs (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id              UUID NOT NULL,
    case_id               TEXT,
    agent_name            TEXT NOT NULL,
    model_name            TEXT,
    model_route           TEXT,
    prompt_id             TEXT,
    prompt_version        TEXT,
    input_schema_version  TEXT,
    output_schema_version TEXT,
    started_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at          TIMESTAMPTZ,
    status                TEXT NOT NULL,
    validation_passed     BOOLEAN NOT NULL DEFAULT false,
    grounding_score       DOUBLE PRECISION,
    confidence_score      DOUBLE PRECISION,
    escalated             BOOLEAN NOT NULL DEFAULT false,
    failure_reason        TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_runs_trace_idx ON agent_runs (trace_id);
CREATE INDEX IF NOT EXISTS agent_runs_case_idx  ON agent_runs (case_id);

-- agent_artifacts: validated agent outputs (de-identified payloads only)
CREATE TABLE IF NOT EXISTS agent_artifacts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id      UUID NOT NULL,
    case_id       TEXT,
    agent_name    TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    payload       JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_artifacts_trace_idx ON agent_artifacts (trace_id);

-- agent_validation_failures: rejected/invalid agent output
CREATE TABLE IF NOT EXISTS agent_validation_failures (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id           UUID NOT NULL,
    case_id            TEXT,
    agent_name         TEXT NOT NULL,
    raw_output_excerpt TEXT,
    failure_reason     TEXT NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_validation_failures_trace_idx ON agent_validation_failures (trace_id);

-- agent_escalations: audited cloud escalations (de-identified, policy-gated)
CREATE TABLE IF NOT EXISTS agent_escalations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id         UUID NOT NULL,
    case_id          TEXT,
    agent_name       TEXT NOT NULL,
    reason           TEXT NOT NULL,
    grounding_score  DOUBLE PRECISION,
    pii_scrub_passed BOOLEAN NOT NULL DEFAULT false,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_escalations_trace_idx ON agent_escalations (trace_id);

-- citation_guard_results: persisted Guard verdicts
CREATE TABLE IF NOT EXISTS citation_guard_results (
    id                            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id                      UUID NOT NULL,
    case_id                       TEXT,
    document_id                   TEXT,
    safety_check_passed           BOOLEAN NOT NULL,
    failed_citations              JSONB NOT NULL DEFAULT '[]',
    unsupported_legal_assertions  JSONB NOT NULL DEFAULT '[]',
    reserved_activity_flags       JSONB NOT NULL DEFAULT '[]',
    boundary_notice_present       BOOLEAN NOT NULL DEFAULT false,
    reason_for_failure            TEXT,
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS citation_guard_results_trace_idx ON citation_guard_results (trace_id);
