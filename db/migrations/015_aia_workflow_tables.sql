-- Migration 015: AIA/internal workflow manager tables
-- Internal orchestration audit trail for the lawapp legal pipeline.
-- Records every pipeline run, step, model call, guardrail event, and retrieval.
-- GUARDRAIL: no raw personal data in logs — fact_snapshot_hash only.

-- ── Workflow runs ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workflow_runs (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             uuid        REFERENCES cases(id) ON DELETE SET NULL,
    claim_type          text,                   -- unfair_dismissal | unpaid_wages | out_of_scope
    jurisdiction        text        NOT NULL DEFAULT 'EW',
    status              text        NOT NULL DEFAULT 'running',
                                                -- running | complete | failed | insufficient_grounding
    fact_snapshot_hash  text,                   -- SHA256 of de-identified facts — no raw PII
    started_at          timestamptz NOT NULL DEFAULT now(),
    completed_at        timestamptz,
    total_duration_ms   int,
    grounding_score     numeric(4,3),
    confidence_score    numeric(4,3),
    insufficient_grounding boolean  NOT NULL DEFAULT false,
    error_message       text,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS wf_runs_case_idx     ON workflow_runs (case_id);
CREATE INDEX IF NOT EXISTS wf_runs_status_idx   ON workflow_runs (status, started_at);
CREATE INDEX IF NOT EXISTS wf_runs_type_idx     ON workflow_runs (claim_type, jurisdiction);

-- ── Workflow steps ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workflow_steps (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              uuid        NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    step_name           text        NOT NULL,   -- classify | retrieve | reason | score | govern | respond
    step_order          int         NOT NULL,
    status              text        NOT NULL DEFAULT 'pending',
                                                -- pending | running | complete | failed | skipped
    started_at          timestamptz,
    completed_at        timestamptz,
    duration_ms         int,
    retry_count         int         NOT NULL DEFAULT 0,
    error_reason        text,
    step_output         jsonb,                  -- step-specific output (no PII)
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS wf_steps_run_idx  ON workflow_steps (run_id, step_order);
CREATE INDEX IF NOT EXISTS wf_steps_name_idx ON workflow_steps (step_name, status);

-- ── Model call audit ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_call_audit (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              uuid        REFERENCES workflow_runs(id) ON DELETE CASCADE,
    step_id             uuid        REFERENCES workflow_steps(id) ON DELETE SET NULL,
    model_provider      text        NOT NULL,   -- anthropic | openrouter | stub
    model_id            text        NOT NULL,
    call_type           text        NOT NULL,   -- classify | reason | embed
    input_tokens        int,
    output_tokens       int,
    latency_ms          int,
    boundary_log        jsonb       NOT NULL,   -- de-identification proof
    grounding_score     numeric(4,3),
    confidence_score    numeric(4,3),
    response_status     text        NOT NULL DEFAULT 'ok', -- ok | error | insufficient_grounding
    error_message       text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT model_call_no_pii CHECK (
        -- boundary_log must be present — enforced at application level
        boundary_log IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS mca_run_idx  ON model_call_audit (run_id);
CREATE INDEX IF NOT EXISTS mca_time_idx ON model_call_audit (created_at);

-- ── Guardrail events ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS guardrail_events (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              uuid        REFERENCES workflow_runs(id) ON DELETE CASCADE,
    gate_number         int         NOT NULL,   -- 1-5 (grounding, confidence, determinism, boundary, honesty)
    gate_name           text        NOT NULL,
    decision            text        NOT NULL,   -- PASS | BLOCK
    failure_reason      text,
    grounding_score     numeric(4,3),
    confidence_score    numeric(4,3),
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ge_run_idx      ON guardrail_events (run_id);
CREATE INDEX IF NOT EXISTS ge_decision_idx ON guardrail_events (decision, gate_name);

-- ── Retrieval audit ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS retrieval_audit (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              uuid        REFERENCES workflow_runs(id) ON DELETE CASCADE,
    retrieval_type      text        NOT NULL,   -- rules | bm25 | pgvector | hybrid
    query_hash          text,                   -- hash of query text — not raw query
    rules_count         int         NOT NULL DEFAULT 0,
    legislation_count   int         NOT NULL DEFAULT 0,
    acas_count          int         NOT NULL DEFAULT 0,
    guidance_count      int         NOT NULL DEFAULT 0,
    case_law_count      int         NOT NULL DEFAULT 0,
    total_authorities   int         NOT NULL DEFAULT 0,
    insufficient_grounding boolean NOT NULL DEFAULT false,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ra_run_idx ON retrieval_audit (run_id);
