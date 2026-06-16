-- Migration 024  -  Advanced technology tables
-- Idempotent (CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS)

-- injection_guard_log
CREATE TABLE IF NOT EXISTS injection_guard_log (
    id              BIGSERIAL PRIMARY KEY,
    trace_id        UUID,
    user_id         UUID,
    source          TEXT NOT NULL DEFAULT 'user_input',
    text_excerpt    TEXT,
    clean           BOOLEAN NOT NULL DEFAULT true,
    category        TEXT,
    pattern_excerpt TEXT,
    duration_ms     NUMERIC(8,2),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS inj_guard_trace_idx ON injection_guard_log (trace_id);
CREATE INDEX IF NOT EXISTS inj_guard_clean_idx ON injection_guard_log (clean);

-- cost_governor_log
CREATE TABLE IF NOT EXISTS cost_governor_log (
    id               BIGSERIAL PRIMARY KEY,
    trace_id         UUID,
    user_id          UUID,
    route            TEXT NOT NULL,
    estimated_tokens INTEGER NOT NULL DEFAULT 0,
    actual_tokens    INTEGER,
    daily_used       INTEGER NOT NULL DEFAULT 0,
    daily_limit      INTEGER NOT NULL DEFAULT 50000,
    allowed          BOOLEAN NOT NULL DEFAULT true,
    route_override   TEXT,
    reason           TEXT NOT NULL DEFAULT 'within_budget',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS cost_gov_user_date_idx ON cost_governor_log (user_id, created_at);

-- human_review_queue
CREATE TABLE IF NOT EXISTS human_review_queue (
    id                    BIGSERIAL PRIMARY KEY,
    trace_id              UUID UNIQUE NOT NULL,
    user_id               UUID,
    case_id               UUID,
    claim_type            TEXT,
    urgency               TEXT,
    trigger_reason        TEXT NOT NULL,
    missing_facts_summary JSONB NOT NULL DEFAULT '[]',
    status                TEXT NOT NULL DEFAULT 'pending',
    reviewer_id           UUID,
    resolution_notes      TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS human_review_status_idx  ON human_review_queue (status);
CREATE INDEX IF NOT EXISTS human_review_urgency_idx ON human_review_queue (urgency, created_at);

-- outbox_events
CREATE TABLE IF NOT EXISTS outbox_events (
    event_id    TEXT PRIMARY KEY,
    event_type  TEXT NOT NULL,
    payload     JSONB NOT NULL DEFAULT '{}',
    trace_id    UUID,
    status      TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    worker_id   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS outbox_status_idx ON outbox_events (status, created_at);
CREATE INDEX IF NOT EXISTS outbox_type_idx   ON outbox_events (event_type);
