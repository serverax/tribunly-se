-- Graph RAG v1: human-gated relationship proposals (no direct LLM Neo4j write)
CREATE TABLE IF NOT EXISTS knowledge.ingestion_proposals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_type   TEXT NOT NULL CHECK (proposal_type IN ('relationship', 'node')),
    from_ref        TEXT NOT NULL,
    to_ref          TEXT NOT NULL,
    relationship    TEXT,
    payload         JSONB NOT NULL DEFAULT '{}',
    source          TEXT NOT NULL DEFAULT 'relationship_extractor',
    status          TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewer_notes  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ingestion_proposals_status_idx
    ON knowledge.ingestion_proposals (status, created_at DESC);
