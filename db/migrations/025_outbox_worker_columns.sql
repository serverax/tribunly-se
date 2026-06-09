-- 025_outbox_worker_columns.sql
-- Additive columns for the outbox worker lifecycle (order §17).
-- Adds failure-triage and completion-timestamp columns used by the consumer
-- (backend/core/outbox_worker.py) and the atomic claim in outbox.claim_batch().
-- Idempotent: safe to run repeatedly.

ALTER TABLE outbox_events
    ADD COLUMN IF NOT EXISTS last_error   TEXT,
    ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ;

-- Partial index to speed up the worker's pending claim scan.
CREATE INDEX IF NOT EXISTS outbox_pending_claim_idx
    ON outbox_events (created_at)
    WHERE status = 'pending';
