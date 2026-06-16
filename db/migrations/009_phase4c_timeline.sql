-- Migration 009: Phase 4C  -  case timeline events
-- Stores manually entered and user-facing timeline events linked to a case.
-- System-generated events (from key_dates, documents, etc.) are computed
-- on demand by the API and not persisted in this table.

CREATE TABLE IF NOT EXISTS case_timeline_events (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id     uuid        REFERENCES cases(id) ON DELETE CASCADE,
    event_type  text        NOT NULL,
    -- employment_started | dismissal | appeal_submitted | appeal_outcome |
    -- acas_day_a | acas_day_b | et_deadline | document_uploaded |
    -- document_generated | handoff_triggered | custom_user_event
    event_date  date,           -- null = missing_date (must not be invented)
    title       text        NOT NULL,
    description text,
    source      text        NOT NULL DEFAULT 'user_entered',
    -- user_entered | rules_engine | confirmed_extraction | system_generated
    status      text        NOT NULL DEFAULT 'active',
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS cte_case_idx  ON case_timeline_events (case_id);
CREATE INDEX IF NOT EXISTS cte_date_idx  ON case_timeline_events (event_date);
