-- Migration 001: initial schema
-- Employment Claim Co-Pilot — PostgreSQL 16 + pgvector
-- Run automatically by docker-compose on first start (via entrypoint.d mount).
-- To apply manually: psql $DATABASE_URL -f db/migrations/001_initial.sql

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── Legal source tables ──────────────────────────────────────────────────────

-- 2.1 legislation (statute text from legislation.gov.uk, CLML XML, chunked)
CREATE TABLE IF NOT EXISTS legislation (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    act_title        text        NOT NULL,
    leg_type         text        NOT NULL,              -- ukpga, uksi, asp …
    year             int         NOT NULL,
    chapter          text,                              -- e.g. "18"
    section_ref      text,                              -- e.g. "94"
    jurisdiction     text        NOT NULL DEFAULT 'EW', -- EW, S, NI, UK
    heading          text,
    body_text        text        NOT NULL,
    chunk_index      int         NOT NULL DEFAULT 0,
    embedding        vector(1536),                      -- dim = EMBEDDING_DIM
    source_url       text        NOT NULL,
    version_date     date,
    effective_from   date,
    effective_to     date,                              -- NULL = currently in force
    is_prospective   boolean     NOT NULL DEFAULT false,
    last_verified_at timestamptz NOT NULL DEFAULT now(),
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS legislation_source_chunk_uq
    ON legislation (source_url, chunk_index);
CREATE INDEX IF NOT EXISTS legislation_embedding_idx
    ON legislation USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS legislation_act_section_idx
    ON legislation (act_title, section_ref);
CREATE INDEX IF NOT EXISTS legislation_jurisdiction_idx
    ON legislation (jurisdiction);
CREATE INDEX IF NOT EXISTS legislation_in_force_idx
    ON legislation (effective_from, effective_to)
    WHERE effective_to IS NULL;

-- 2.2 case_law (EAT decisions from Find Case Law / Akoma Ntoso)
CREATE TABLE IF NOT EXISTS case_law (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    document_uri     text        NOT NULL UNIQUE,       -- stable Find Case Law URI
    neutral_citation text,                              -- e.g. "[2024] EAT 12"
    fclid            text,
    case_name        text,
    court_code       text        NOT NULL,              -- e.g. "eat"
    decision_date    date,
    judges           text[],
    parties          text[],
    body_text        text        NOT NULL,
    chunk_index      int         NOT NULL DEFAULT 0,
    embedding        vector(1536),
    content_hash     text        NOT NULL,              -- SHA256 from <uk:hash>
    source_url       text        NOT NULL,
    published_date   date,
    updated_date     timestamptz,
    last_verified_at timestamptz NOT NULL DEFAULT now(),
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS case_law_doc_chunk_uq
    ON case_law (document_uri, chunk_index);
CREATE INDEX IF NOT EXISTS case_law_embedding_idx
    ON case_law USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS case_law_court_date_idx
    ON case_law (court_code, decision_date);
CREATE INDEX IF NOT EXISTS case_law_hash_idx
    ON case_law (content_hash);

-- 2.3 acas_guidance (ACAS Code of Practice + guidance, static documents)
CREATE TABLE IF NOT EXISTS acas_guidance (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_title        text        NOT NULL,
    edition          text,                              -- e.g. "March 2015"
    section_ref      text,
    body_text        text        NOT NULL,
    chunk_index      int         NOT NULL DEFAULT 0,
    embedding        vector(1536),
    source_url       text        NOT NULL,
    effective_from   date,
    last_verified_at timestamptz NOT NULL DEFAULT now(),
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS acas_embedding_idx
    ON acas_guidance USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 2.4 rules — DETERMINISTIC legal facts (time limits, caps, thresholds)
-- GUARDRAIL: never inferred by a model; always queried by code with effective-date filtering.
CREATE TABLE IF NOT EXISTS rules (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_key         text        NOT NULL,              -- e.g. "unfair_dismissal.time_limit_months"
    claim_type       text        NOT NULL,              -- e.g. "unfair_dismissal"
    jurisdiction     text        NOT NULL DEFAULT 'EW',
    value_numeric    numeric,
    value_text       text,
    unit             text,                              -- "months", "GBP", "years", "weeks_gross_pay" …
    description      text        NOT NULL,
    authority_type   text        NOT NULL,              -- "legislation" | "case_law" | "acas"
    authority_ref    text        NOT NULL,              -- e.g. "ERA 1996 s.111(2)"
    authority_url    text        NOT NULL,
    effective_from   date        NOT NULL,
    effective_to     date,                              -- NULL = current
    is_prospective   boolean     NOT NULL DEFAULT false,
    last_verified_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (rule_key, jurisdiction, effective_from)
);

CREATE INDEX IF NOT EXISTS rules_claim_type_idx  ON rules (claim_type, jurisdiction);
CREATE INDEX IF NOT EXISTS rules_key_idx         ON rules (rule_key);
CREATE INDEX IF NOT EXISTS rules_effective_idx   ON rules (effective_from, effective_to);

-- ── Application tables ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    email               text        UNIQUE,
    created_at          timestamptz NOT NULL DEFAULT now(),
    subscription_status text        NOT NULL DEFAULT 'none' -- none | active | cancelled
);

-- cases.facts_encrypted holds special-category data (Art.9) — encrypted at rest.
CREATE TABLE IF NOT EXISTS cases (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          uuid        REFERENCES users(id) ON DELETE CASCADE,
    claim_type       text        NOT NULL DEFAULT 'unfair_dismissal',
    jurisdiction     text        NOT NULL DEFAULT 'EW',
    facts_encrypted  bytea,                             -- AES-256-GCM encrypted JSON
    assessment       jsonb,                             -- latest structured assessment object
    key_dates        jsonb,                             -- {"dismissal_date":…, "limitation_date":…}
    status           text        NOT NULL DEFAULT 'diagnosis', -- diagnosis|paid|bundle|handoff
    payment_tier     text,                              -- core | full | none
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS cases_user_idx ON cases (user_id);

CREATE TABLE IF NOT EXISTS documents (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id          uuid        REFERENCES cases(id) ON DELETE CASCADE,
    doc_type         text        NOT NULL,  -- particulars_of_claim|schedule_of_loss|witness_statement|upload
    storage_ref      text        NOT NULL,  -- encrypted blob location
    is_user_upload   boolean     NOT NULL DEFAULT false,
    extracted_facts  jsonb,                             -- post-OCR extraction (requires user confirm)
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS documents_case_idx ON documents (case_id);

CREATE TABLE IF NOT EXISTS referrals (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id          uuid        REFERENCES cases(id),
    partner_firm     text,
    status           text        NOT NULL DEFAULT 'triggered', -- triggered|sent|accepted|rejected
    fee_status       text,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- ── Operational view ─────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW source_freshness AS
    SELECT 'legislation'   AS source,
           count(*)        AS rows,
           min(last_verified_at) AS oldest_verified
    FROM legislation
    UNION ALL
    SELECT 'case_law',     count(*), min(last_verified_at) FROM case_law
    UNION ALL
    SELECT 'acas_guidance',count(*), min(last_verified_at) FROM acas_guidance
    UNION ALL
    SELECT 'rules',        count(*), min(last_verified_at) FROM rules;
