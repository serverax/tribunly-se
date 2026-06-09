-- 031_legal_data_spine.sql
-- Legal data spine: jurisdiction model, taxonomy, chunk labels, and provenance
-- extensions to legal_sources / corpus_ingestion_runs, plus jurisdiction_code +
-- applies_to_* on every legal table. Embedding dim = 384 (local bge-small; the
-- spec's vector(1536) was for OpenAI — lawapp runs the local 384-dim model).
-- Idempotent; additive; backfills existing rows. No fake legal content.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── 1. legal_jurisdictions (controlled jurisdiction dimension) ───────────────
CREATE TABLE IF NOT EXISTS legal_jurisdictions (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction_code         TEXT UNIQUE NOT NULL,
    country_code              TEXT NOT NULL,
    label                     TEXT NOT NULL,
    legal_system              TEXT NOT NULL,
    applies_to_employment_law BOOLEAN NOT NULL DEFAULT false,
    notes                     TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO legal_jurisdictions (jurisdiction_code, country_code, label, legal_system, applies_to_employment_law, notes) VALUES
 ('GB','GB','Great Britain','Employment law covering England, Wales and Scotland where legislation applies GB-wide', true,  'Default for ordinary unfair dismissal MVP.'),
 ('EW','EW','England and Wales','England and Wales', true,  NULL),
 ('S','SCT','Scotland','Scots law', true,  'Shares GB employment-law values where source applies GB-wide.'),
 ('NI','NIR','Northern Ireland','Northern Ireland employment law', true, 'Separate legislation (e.g. Employment Rights (NI) Order 1996). NOT yet ingested — unsupported / fail-closed.'),
 ('UK','UK','United Kingdom','UK-wide source or institution', true, 'Only where the source is genuinely UK-wide.')
ON CONFLICT (jurisdiction_code) DO NOTHING;

-- ── 2. legal_taxonomy + seed ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS legal_taxonomy (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    taxonomy_key TEXT UNIQUE NOT NULL,
    parent_key   TEXT,
    label        TEXT NOT NULL,
    description  TEXT,
    domain       TEXT NOT NULL,
    claim_type   TEXT,
    source_types TEXT[],
    examples     TEXT[],
    active       BOOLEAN NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO legal_taxonomy (taxonomy_key, parent_key, label, domain, claim_type) VALUES
 ('employment_uk', NULL, 'UK Employment Law', 'employment_uk', NULL),
 ('employment_uk.unfair_dismissal', 'employment_uk', 'Unfair dismissal', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.eligibility', 'employment_uk.unfair_dismissal', 'Eligibility', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.qualifying_period', 'employment_uk.unfair_dismissal', 'Qualifying period', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.dismissal', 'employment_uk.unfair_dismissal', 'Dismissal', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.constructive_dismissal', 'employment_uk.unfair_dismissal', 'Constructive dismissal', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.fair_reason', 'employment_uk.unfair_dismissal', 'Fair reason', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.reasonableness', 'employment_uk.unfair_dismissal', 'Reasonableness', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.procedure', 'employment_uk.unfair_dismissal', 'Procedure', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.acas_code', 'employment_uk.unfair_dismissal', 'ACAS Code', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.deadline', 'employment_uk.unfair_dismissal', 'Deadline', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.early_conciliation', 'employment_uk.unfair_dismissal', 'Early conciliation', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.remedy', 'employment_uk.unfair_dismissal', 'Remedy', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.basic_award', 'employment_uk.unfair_dismissal', 'Basic award', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.compensatory_award', 'employment_uk.unfair_dismissal', 'Compensatory award', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.reinstatement', 'employment_uk.unfair_dismissal', 'Reinstatement', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.unfair_dismissal.reengagement', 'employment_uk.unfair_dismissal', 'Re-engagement', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.automatically_unfair', 'employment_uk', 'Automatically unfair dismissal', 'employment_uk', 'unfair_dismissal'),
 ('employment_uk.discrimination_future', 'employment_uk', 'Discrimination (future)', 'employment_uk', 'discrimination'),
 ('employment_uk.unpaid_wages_future', 'employment_uk', 'Unpaid wages (future)', 'employment_uk', 'unlawful_deduction_wages')
ON CONFLICT (taxonomy_key) DO NOTHING;

-- ── 3. legal_chunk_labels (chunk ↔ taxonomy, many-to-many) ──────────────────
CREATE TABLE IF NOT EXISTS legal_chunk_labels (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_table     TEXT NOT NULL,             -- legislation | case_law | acas_guidance
    source_row_id    BIGINT,                    -- legislation/acas use BIGINT id
    source_row_uuid  UUID,                       -- case_law uses UUID id
    taxonomy_key     TEXT NOT NULL REFERENCES legal_taxonomy(taxonomy_key),
    label_confidence NUMERIC,
    label_method     TEXT,                       -- manual | rule | model | hybrid
    reviewed         BOOLEAN NOT NULL DEFAULT false,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS legal_chunk_labels_tax_idx ON legal_chunk_labels (taxonomy_key);
CREATE INDEX IF NOT EXISTS legal_chunk_labels_src_idx ON legal_chunk_labels (source_table, source_row_id);

-- ── 4. extend legal_sources to the spine spec + seed required sources ────────
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS source_key             TEXT;
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS licence_name           TEXT;
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS licence_url            TEXT;
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS bulk_ingestion_allowed BOOLEAN DEFAULT false;
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS rate_limit_text        TEXT;
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS requires_application   BOOLEAN DEFAULT false;
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS application_status     TEXT;
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS owner_contact          TEXT;
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS last_checked_at        TIMESTAMPTZ;
UPDATE legal_sources SET source_key = COALESCE(source_key, domain||':'||source_id) WHERE source_key IS NULL;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='legal_sources_source_key_key') THEN
    ALTER TABLE legal_sources ADD CONSTRAINT legal_sources_source_key_key UNIQUE (source_key);
  END IF;
END $$;

-- Seed the required spine sources (idempotent on (domain, source_id)).
INSERT INTO legal_sources
  (domain, source_id, source_key, source_name, source_type, base_url, jurisdiction,
   licence_type, licence_name, licence_url, licence_status, bulk_allowed, bulk_ingestion_allowed,
   computational_analysis_allowed, requires_application, application_status, requires_owner_approval,
   gate_env_var, active, last_verified_at, last_checked_at, notes)
VALUES
 ('employment_uk','legislation_gov_uk','employment_uk:legislation_gov_uk','legislation.gov.uk','legislation','https://www.legislation.gov.uk','GB',
  'open_government_licence','Open Government Licence v3.0','https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/','open',true,true,
  true,false,'not_required',false,NULL,true,now(),now(),'Primary statute source. REST + /data.xml.'),
 ('employment_uk','find_case_law','employment_uk:find_case_law','Find Case Law (National Archives)','case_law','https://caselaw.nationalarchives.gov.uk','UK',
  'open_justice_licence','Open Justice Licence','https://caselaw.nationalarchives.gov.uk/about/open-justice-licence','application_required',false,false,
  false,true,'pending',true,'FCL_BULK_LICENCE_GRANTED',true,now(),now(),'Bulk + computational analysis require National Archives permission. Fail-closed.'),
 ('employment_uk','acas','employment_uk:acas','ACAS','acas','https://www.acas.org.uk','GB',
  'acas_public_guidance','ACAS public guidance',NULL,'open',true,true,
  true,false,'not_required',false,NULL,true,now(),now(),'Static authoritative documents; no confirmed open data API.'),
 ('employment_uk','govuk_et_decisions','employment_uk:govuk_et_decisions','GOV.UK Employment Tribunal decisions','tribunal','https://www.gov.uk/employment-tribunal-decisions','GB',
  'open_government_licence','Open Government Licence v3.0','https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/','restricted',false,false,
  false,false,'unknown',false,NULL,true,now(),now(),'Public ET decisions from Feb 2017. Fallback only; prefer Find Case Law XML.'),
 ('employment_uk','govuk_eat_decisions','employment_uk:govuk_eat_decisions','GOV.UK Employment Appeal Tribunal decisions','tribunal','https://www.gov.uk/employment-appeal-tribunal-decisions','GB',
  'open_government_licence','Open Government Licence v3.0','https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/','restricted',false,false,
  false,false,'unknown',false,NULL,true,now(),now(),'EAT decisions. Fallback only; prefer Find Case Law XML.'),
 ('employment_uk','parliament_bills','employment_uk:parliament_bills','UK Parliament Bills API','parliament','https://bills-api.parliament.uk','UK',
  'open_parliament_licence','Open Parliament Licence',NULL,'open',true,true,
  true,false,'not_required',false,NULL,true,now(),now(),'Reform-watch / monitoring only. NOT legal authority.'),
 ('employment_uk','govuk_courts_tribunals_publishing','employment_uk:govuk_courts_tribunals_publishing','GOV.UK Courts and Tribunals Publishing API','govuk','https://www.gov.uk','UK',
  'open_government_licence','Open Government Licence v3.0','https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/','unknown',false,false,
  false,false,'unknown',false,NULL,true,now(),now(),'Supporting source; catalogue listing does not guarantee public access.'),
 ('employment_uk','ni_employment_law','employment_uk:ni_employment_law','Northern Ireland employment law (placeholder)','legislation','https://www.legislation.gov.uk','NI',
  'open_government_licence','Open Government Licence v3.0','https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/','unknown',false,false,
  false,false,'unknown',true,NULL,true,now(),now(),'NOT implemented. NI employment law (e.g. Employment Rights (NI) Order 1996) not yet ingested. NI fails closed.')
ON CONFLICT (domain, source_id) DO UPDATE SET
  source_key=EXCLUDED.source_key, source_name=EXCLUDED.source_name, source_type=EXCLUDED.source_type,
  base_url=EXCLUDED.base_url, jurisdiction=EXCLUDED.jurisdiction, licence_name=EXCLUDED.licence_name,
  licence_url=EXCLUDED.licence_url, licence_status=EXCLUDED.licence_status,
  bulk_ingestion_allowed=EXCLUDED.bulk_ingestion_allowed, requires_application=EXCLUDED.requires_application,
  application_status=EXCLUDED.application_status, last_checked_at=now(), notes=EXCLUDED.notes;

-- ── 5. extend corpus_ingestion_runs to the reproducible-run spec ────────────
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS run_key              TEXT;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS claim_type           TEXT;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS jurisdiction_code    TEXT;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS ingestion_mode       TEXT;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS finished_at          TIMESTAMPTZ;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS records_discovered   INT DEFAULT 0;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS records_fetched      INT DEFAULT 0;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS records_inserted     INT DEFAULT 0;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS records_updated      INT DEFAULT 0;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS records_skipped      INT DEFAULT 0;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS records_failed       INT DEFAULT 0;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS chunks_created       INT DEFAULT 0;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS embeddings_created   INT DEFAULT 0;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS error_summary        TEXT;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS blocker_reason       TEXT;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS config_json          JSONB;
ALTER TABLE corpus_ingestion_runs ADD COLUMN IF NOT EXISTS proof_json           JSONB;

-- ── 6. jurisdiction_code + applies_to_* on every legal table ────────────────
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['legislation','acas_guidance','official_guidance','rules','case_law_documents'] LOOP
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS jurisdiction_code TEXT', t);
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS legal_system TEXT', t);
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS applies_to_ni BOOLEAN DEFAULT false', t);
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS applies_to_scotland BOOLEAN DEFAULT false', t);
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS applies_to_england_wales BOOLEAN DEFAULT false', t);
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS applies_to_gb BOOLEAN DEFAULT false', t);
  END LOOP;
END $$;

-- Backfill: employment legislation/guidance/rules apply GB-wide (E&W + Scotland);
-- NI is NOT covered (separate NI legislation, not ingested → fail-closed).
UPDATE legislation       SET jurisdiction_code=COALESCE(jurisdiction_code,'GB'), legal_system='Great Britain', applies_to_gb=true, applies_to_england_wales=true, applies_to_scotland=true, applies_to_ni=false WHERE jurisdiction_code IS NULL OR jurisdiction_code='';
UPDATE acas_guidance     SET jurisdiction_code=COALESCE(jurisdiction_code,'GB'), legal_system='Great Britain', applies_to_gb=true, applies_to_england_wales=true, applies_to_scotland=true, applies_to_ni=false WHERE jurisdiction_code IS NULL OR jurisdiction_code='';
UPDATE official_guidance SET jurisdiction_code=COALESCE(jurisdiction_code,'GB'), legal_system='Great Britain', applies_to_gb=true, applies_to_england_wales=true, applies_to_scotland=true, applies_to_ni=false WHERE jurisdiction_code IS NULL OR jurisdiction_code='';
UPDATE rules             SET jurisdiction_code=COALESCE(jurisdiction_code,'GB'), legal_system='Great Britain', applies_to_gb=true, applies_to_england_wales=true, applies_to_scotland=true, applies_to_ni=false WHERE jurisdiction_code IS NULL OR jurisdiction_code='';
UPDATE case_law_documents SET jurisdiction_code=COALESCE(jurisdiction_code,'GB') WHERE jurisdiction_code IS NULL OR jurisdiction_code='';

-- FK to the controlled jurisdiction table (guarded)
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['legislation','acas_guidance','official_guidance','rules','case_law_documents'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = t||'_jurisdiction_fk') THEN
      EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (jurisdiction_code) REFERENCES legal_jurisdictions(jurisdiction_code)', t, t||'_jurisdiction_fk');
    END IF;
  END LOOP;
END $$;
