-- 082_ingestion_proposals.sql
-- Proposal queue: LLM and learning loop may ONLY enqueue ingestion proposals.
-- No direct writes to rules, legislation, or corpus from automated paths.

BEGIN;

CREATE TABLE IF NOT EXISTS knowledge.ingestion_proposals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type     TEXT NOT NULL,
    authority_ref   TEXT NOT NULL,
    gap_type        TEXT NOT NULL DEFAULT 'retrieval_miss',
    rationale       TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    content_hash    TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected', 'merged')),
    trace_id        TEXT,
    reviewed_by     TEXT,
    reviewed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ingestion_proposals_status_idx
    ON knowledge.ingestion_proposals (status, created_at DESC);

COMMIT;
