-- 084_ingestion_jobs_dual_plane.sql
-- Dual-plane ingestion job tracking (Postgres always; Neo4j optional via NEO4J_ENABLED).
-- Proposals queue for rule candidates (never direct rules write).

BEGIN;

CREATE TABLE IF NOT EXISTS knowledge.ingestion_proposals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_type       TEXT NOT NULL CHECK (proposal_type IN ('rule_candidate','graph_edge','graph_entity')),
    source_worker       TEXT NOT NULL,
    document_id         TEXT,
    chunk_id            TEXT,
    payload             JSONB NOT NULL DEFAULT '{}',
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','rejected','applied')),
    reviewer_notes      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ingestion_proposals_status_idx
    ON knowledge.ingestion_proposals (status, created_at DESC);

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
