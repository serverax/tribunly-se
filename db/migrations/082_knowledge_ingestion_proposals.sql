-- 082_knowledge_ingestion_proposals.sql
-- Graph relationship proposals from LLM extractor (pending human validation).
-- No direct Neo4j write from extractor; promotion via approved ingest job only.

BEGIN;

CREATE TABLE IF NOT EXISTS knowledge.ingestion_proposals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_type       TEXT NOT NULL CHECK (proposal_type IN ('relationship', 'node')),
    from_ref            TEXT NOT NULL,
    to_ref              TEXT NOT NULL,
    relationship_type   TEXT,
    confidence          NUMERIC,
    source              TEXT NOT NULL DEFAULT 'llm_extractor',
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected')),
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at         TIMESTAMPTZ,
    reviewed_by         TEXT
);

CREATE INDEX IF NOT EXISTS ingestion_proposals_status_idx
    ON knowledge.ingestion_proposals (status, created_at DESC);

COMMIT;
