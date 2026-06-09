-- Migration 002: split case_law into case_law_documents (one row per decision)
-- and case_law_chunks (one row per chunk, FK to documents).
--
-- Rationale:
--   - content_hash belongs on the document row, not duplicated across 100+ chunk rows
--   - document_uri UNIQUE belongs on the document row; chunk uniqueness is (document_id, chunk_index)
--   - change-detection is per-document (compare hash); retrieval is per-chunk (embed search)
--   - parent/child is far cheaper to introduce before Phase 2 retrieval builds on top

DROP TABLE IF EXISTS case_law CASCADE;

-- One row per EAT/ET decision
CREATE TABLE IF NOT EXISTS case_law_documents (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    document_uri     text        NOT NULL UNIQUE,  -- stable d-{uuid} identifier from atom feed
    fetch_url        text        NOT NULL,           -- actual XML endpoint (eat/year/num/data.xml)
    neutral_citation text,
    fclid            text,
    case_name        text,
    court_code       text        NOT NULL,
    decision_date    date,
    judges           text[],
    parties          text[],
    content_hash     text        NOT NULL,           -- SHA256 of body text; one per document
    published_date   date,
    updated_date     timestamptz,
    last_verified_at timestamptz NOT NULL DEFAULT now(),
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS cl_doc_court_date_idx  ON case_law_documents (court_code, decision_date);
CREATE INDEX IF NOT EXISTS cl_doc_hash_idx        ON case_law_documents (content_hash);
CREATE INDEX IF NOT EXISTS cl_doc_citation_idx    ON case_law_documents (neutral_citation);

-- One row per chunk of a decision (body text + embedding)
CREATE TABLE IF NOT EXISTS case_law_chunks (
    id          uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid    NOT NULL REFERENCES case_law_documents(id) ON DELETE CASCADE,
    chunk_index int     NOT NULL,
    body_text   text    NOT NULL,
    embedding   vector(1536),
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS cl_chunk_embedding_idx
    ON case_law_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS cl_chunk_doc_idx ON case_law_chunks (document_id);

-- Update the source_freshness view to count decisions (not chunks)
CREATE OR REPLACE VIEW source_freshness AS
    SELECT 'legislation'   AS source,
           count(*)        AS rows,
           min(last_verified_at) AS oldest_verified
    FROM legislation
    UNION ALL
    SELECT 'case_law',     count(*), min(last_verified_at) FROM case_law_documents
    UNION ALL
    SELECT 'acas_guidance',count(*), min(last_verified_at) FROM acas_guidance
    UNION ALL
    SELECT 'rules',        count(*), min(last_verified_at) FROM rules;
