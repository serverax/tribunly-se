-- 084_ingestion_jobs_dual_plane.sql
-- Dual-plane ingestion job tracking (Postgres always; Neo4j optional via NEO4J_ENABLED).
-- Extends knowledge.ingestion_proposals (created by 082_*) for worker metadata.

BEGIN;

ALTER TABLE knowledge.ingestion_proposals
    ADD COLUMN IF NOT EXISTS source_worker TEXT,
    ADD COLUMN IF NOT EXISTS document_id TEXT,
    ADD COLUMN IF NOT EXISTS chunk_id TEXT;

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_type         TEXT NOT NULL CHECK (worker_type IN ('legislation','case_law','acas','rules_compiler')),
    queue_name          TEXT NOT NULL,
    document_id         TEXT,
    chunk_id            TEXT,
    postgres_status     TEXT NOT NULL DEFAULT 'pending'
                        CHECK (postgres_status IN ('pending','processing','done','failed','skipped')),
    neo4j_status        TEXT NOT NULL DEFAULT 'skipped'
                        CHECK (neo4j_status IN ('pending','processing','done','failed','skipped')),
    error_message       TEXT,
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ingestion_jobs_document_idx ON ingestion_jobs (document_id);
CREATE INDEX IF NOT EXISTS ingestion_jobs_postgres_status_idx ON ingestion_jobs (postgres_status);
CREATE INDEX IF NOT EXISTS ingestion_jobs_neo4j_status_idx ON ingestion_jobs (neo4j_status);

COMMIT;
