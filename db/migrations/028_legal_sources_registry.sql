-- 028_legal_sources_registry.sql
-- UK legal dataset provenance + ingestion audit.
--   legal_sources         : registry of every authorised source (one row per source).
--   corpus_ingestion_runs : one row per ingestion run (what ran, counts, pass/fail).
-- Idempotent (IF NOT EXISTS); additive only. No fake/seed rows  -  populated by the
-- Corpus Ingestion AIA from the domain pack (domains/employment_uk/).

CREATE TABLE IF NOT EXISTS legal_sources (
    id                            BIGSERIAL PRIMARY KEY,
    domain                        TEXT NOT NULL,                 -- e.g. employment_uk
    source_id                     TEXT NOT NULL,                 -- e.g. legislation_gov_uk
    source_name                   TEXT NOT NULL,
    source_type                   TEXT NOT NULL,                 -- primary_legislation|official_guidance|case_law
    base_url                      TEXT NOT NULL,
    jurisdiction                  TEXT,                          -- EW|S|NI
    licence_type                  TEXT NOT NULL,
    licence_status                TEXT NOT NULL,                 -- GRANTED|BLOCKED_BY_OWNER
    bulk_allowed                  BOOLEAN NOT NULL DEFAULT false,
    computational_analysis_allowed BOOLEAN NOT NULL DEFAULT false,
    requires_owner_approval       BOOLEAN NOT NULL DEFAULT false,
    gate_env_var                  TEXT,                          -- e.g. FCL_BULK_LICENCE_GRANTED
    active                        BOOLEAN NOT NULL DEFAULT true,
    last_verified_at              DATE,
    notes                         TEXT,
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (domain, source_id)
);
CREATE INDEX IF NOT EXISTS legal_sources_domain_idx ON legal_sources (domain);
CREATE INDEX IF NOT EXISTS legal_sources_type_idx   ON legal_sources (source_type);

CREATE TABLE IF NOT EXISTS corpus_ingestion_runs (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain             TEXT NOT NULL,
    source_id          TEXT,                                     -- null = multi-source run
    run_kind           TEXT NOT NULL,                            -- legislation|acas|govuk|embeddings|full
    trace_id           UUID,
    started_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at       TIMESTAMPTZ,
    status             TEXT NOT NULL DEFAULT 'running',          -- running|passed|failed
    rows_ingested      INTEGER NOT NULL DEFAULT 0,
    rows_rejected      INTEGER NOT NULL DEFAULT 0,
    sections_expected  INTEGER,
    sections_present   INTEGER,
    validation_passed  BOOLEAN NOT NULL DEFAULT false,
    failures           JSONB,                                    -- list of gate failure strings
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS corpus_ingestion_runs_domain_idx ON corpus_ingestion_runs (domain);
CREATE INDEX IF NOT EXISTS corpus_ingestion_runs_status_idx ON corpus_ingestion_runs (status);
