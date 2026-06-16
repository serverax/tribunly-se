-- 083_quarantine_queue.sql
-- Quarantine failed ingestion records until validated and promoted by ops.

BEGIN;

CREATE TABLE IF NOT EXISTS knowledge.quarantine_queue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector       TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    authority_ref   TEXT,
    raw_payload     JSONB NOT NULL DEFAULT '{}',
    validation_errors JSONB NOT NULL DEFAULT '[]',
    content_hash    TEXT,
    status          TEXT NOT NULL DEFAULT 'quarantined'
                    CHECK (status IN ('quarantined', 'released', 'rejected')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    released_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS quarantine_queue_status_idx
    ON knowledge.quarantine_queue (status, created_at DESC);

COMMIT;
