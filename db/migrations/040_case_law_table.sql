-- 040_case_law_table.sql
-- Creates the case_law table (jurisdiction-aware, provenance-complete). It is
-- EMPTY by design: Find Case Law bulk computational-analysis ingestion is BLOCKED
-- until the licence application is granted. No fake/placeholder case rows.
-- Records the blocker in corpus_ingestion_runs so it is auditable. Idempotent.
CREATE TABLE IF NOT EXISTS case_law (
    id                BIGSERIAL PRIMARY KEY,
    neutral_citation  TEXT,
    case_name         TEXT,
    court_code        TEXT,
    tribunal_code     TEXT,
    jurisdiction_code TEXT NOT NULL REFERENCES legal_jurisdictions(jurisdiction_code),
    country_code      TEXT,
    document_uri      TEXT,
    source_url        TEXT NOT NULL,
    authority_ref     TEXT,
    parser_type       TEXT,                       -- akn|legaldocml|html_fallback
    heading           TEXT,
    body_text         TEXT,
    chunk_index       INT NOT NULL DEFAULT 0,
    content_hash      TEXT,
    embedding         vector(384),
    embedding_model   TEXT,
    effective_from    DATE,
    effective_to      DATE,
    is_current        BOOLEAN NOT NULL DEFAULT true,
    is_prospective    BOOLEAN NOT NULL DEFAULT false,
    licence_status    TEXT,
    source_type       TEXT NOT NULL DEFAULT 'case_law',
    last_verified_at  DATE,
    ingestion_run_id  UUID,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS case_law_juris_idx   ON case_law (jurisdiction_code, is_current);
CREATE INDEX IF NOT EXISTS case_law_citation_idx ON case_law (neutral_citation);
CREATE UNIQUE INDEX IF NOT EXISTS case_law_hash_uidx ON case_law (content_hash) WHERE content_hash IS NOT NULL;

-- Record the FCL blocker as an auditable ingestion run (once).
INSERT INTO corpus_ingestion_runs (domain, source_id, run_kind, status, validation_passed, failures)
SELECT 'employment_uk', 'find_case_law', 'case_law', 'blocked', false,
       '["BLOCKED: Find Case Law bulk computational-analysis licence not granted (application_status != granted). No bulk crawl performed; case_law table intentionally empty."]'::jsonb
WHERE NOT EXISTS (
    SELECT 1 FROM corpus_ingestion_runs WHERE source_id = 'find_case_law' AND status = 'blocked'
);
