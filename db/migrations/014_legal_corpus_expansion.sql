-- Migration 014: Legal corpus expansion
-- Adds tables for GOV.UK guidance, Bills tracking, legal change watch,
-- public datasets index, and ingestion run tracking.
-- Extends retrieval sources for the full lawapp data spine.

-- ── GOV.UK official guidance ─────────────────────────────────────────────────
-- Authoritative government guidance (explanation/support, not primary law).
CREATE TABLE IF NOT EXISTS official_guidance (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name      text        NOT NULL DEFAULT 'govuk',
    source_url       text        NOT NULL UNIQUE,
    title            text        NOT NULL,
    description      text,
    body_text        text        NOT NULL,
    document_type    text        NOT NULL DEFAULT 'guidance',  -- guidance | policy | tool
    jurisdiction     text        NOT NULL DEFAULT 'EW',
    metadata         jsonb,
    content_hash     text        NOT NULL,
    effective_from   date,
    effective_to     date,
    is_current       boolean     NOT NULL DEFAULT true,
    chunk_index      int         NOT NULL DEFAULT 0,
    embedding        vector(1536),
    last_verified_at timestamptz NOT NULL DEFAULT now(),
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS official_guidance_url_chunk_uq
    ON official_guidance (source_url, chunk_index);
CREATE INDEX IF NOT EXISTS official_guidance_type_idx
    ON official_guidance (document_type, jurisdiction);
CREATE INDEX IF NOT EXISTS official_guidance_embedding_idx
    ON official_guidance USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ── UK Parliament Bills ───────────────────────────────────────────────────────
-- Track bills through Parliament  -  NOT active law until commenced.
-- GUARDRAIL: never use as an active rule without verifying commencement.
CREATE TABLE IF NOT EXISTS bills (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    bill_id          int,                     -- Parliament API bill ID
    title            text        NOT NULL,
    short_title      text,
    bill_type        text,                    -- PublicBill | PrivateBill | HybridBill
    introduced_date  date,
    royal_assent_date date,
    stage            text,                    -- e.g. "Royal Assent" | "Report Stage"
    house_origin     text,                    -- Commons | Lords
    jurisdiction     text        NOT NULL DEFAULT 'UK',
    summary          text,
    source_url       text        NOT NULL,
    is_in_force      boolean     NOT NULL DEFAULT false,  -- true only after commenced
    commencement_note text,
    last_verified_at timestamptz NOT NULL DEFAULT now(),
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS bills_source_url_uq ON bills (source_url);
CREATE INDEX IF NOT EXISTS bills_stage_idx ON bills (stage, is_in_force);

-- ── Legal change watch ────────────────────────────────────────────────────────
-- Track specific legal changes affecting rules or thresholds.
-- Links a bill or statutory instrument to affected rules.
CREATE TABLE IF NOT EXISTS legal_change_watch (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    change_type      text        NOT NULL,   -- amendment | commencement | new_limit | repeal
    affected_rule_key text,                  -- links to rules.rule_key if known
    bill_id          uuid        REFERENCES bills(id),
    description      text        NOT NULL,
    expected_in_force date,
    is_in_force      boolean     NOT NULL DEFAULT false,
    source_url       text,
    jurisdiction     text        NOT NULL DEFAULT 'EW',
    last_verified_at timestamptz NOT NULL DEFAULT now(),
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lcw_rule_key_idx ON legal_change_watch (affected_rule_key);
CREATE INDEX IF NOT EXISTS lcw_in_force_idx ON legal_change_watch (is_in_force, expected_in_force);

-- ── Public datasets index (data.gov.uk CKAN) ─────────────────────────────────
-- Discovery index for government open datasets. Not legal authority.
CREATE TABLE IF NOT EXISTS public_datasets_index (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name      text        NOT NULL DEFAULT 'data.gov.uk',
    dataset_id       text,
    title            text        NOT NULL,
    description      text,
    document_type    text        NOT NULL DEFAULT 'dataset',
    jurisdiction     text        NOT NULL DEFAULT 'UK',
    licence          text,
    source_url       text        NOT NULL UNIQUE,
    metadata         jsonb,
    is_current       boolean     NOT NULL DEFAULT true,
    last_verified_at timestamptz NOT NULL DEFAULT now(),
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- ── Ingestion runs ────────────────────────────────────────────────────────────
-- Audit log for every ingestion run.
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    source           text        NOT NULL,   -- legislation | case_law | acas | govuk | bills
    run_at           timestamptz NOT NULL DEFAULT now(),
    records_ingested int         NOT NULL DEFAULT 0,
    records_updated  int         NOT NULL DEFAULT 0,
    records_skipped  int         NOT NULL DEFAULT 0,
    errors           int         NOT NULL DEFAULT 0,
    status           text        NOT NULL DEFAULT 'running',  -- running | complete | failed
    notes            text,
    completed_at     timestamptz
);

CREATE INDEX IF NOT EXISTS ir_source_idx ON ingestion_runs (source, run_at);

-- ── Update source_freshness view to include new tables ────────────────────────
CREATE OR REPLACE VIEW source_freshness AS
    SELECT 'legislation'      AS source, count(*) AS rows, min(last_verified_at) AS oldest_verified FROM legislation
    UNION ALL SELECT 'case_law',       count(*), min(created_at) FROM case_law_chunks
    UNION ALL SELECT 'acas_guidance',  count(*), min(last_verified_at) FROM acas_guidance
    UNION ALL SELECT 'official_guidance', count(*), min(last_verified_at) FROM official_guidance
    UNION ALL SELECT 'bills',          count(*), min(last_verified_at) FROM bills
    UNION ALL SELECT 'rules',          count(*), min(last_verified_at) FROM rules;
