-- 029_legal_provenance_columns.sql
-- Reusable-corpus provenance: every legal row carries country_code, domain,
-- source_type, licence_status, parser_type, parent_source_id so the dataset is
-- organised, cited, versioned and reusable for future law areas / countries.
-- Idempotent (IF NOT EXISTS); additive; backfills existing rows from the known
-- UK employment provenance. No fake data — these are provenance labels, not content.

-- ── legislation ────────────────────────────────────────────────────────────
ALTER TABLE legislation ADD COLUMN IF NOT EXISTS country_code     TEXT;
ALTER TABLE legislation ADD COLUMN IF NOT EXISTS domain           TEXT;
ALTER TABLE legislation ADD COLUMN IF NOT EXISTS source_type      TEXT;
ALTER TABLE legislation ADD COLUMN IF NOT EXISTS licence_status   TEXT;
ALTER TABLE legislation ADD COLUMN IF NOT EXISTS parser_type      TEXT;
ALTER TABLE legislation ADD COLUMN IF NOT EXISTS parent_source_id TEXT;
UPDATE legislation SET
    country_code     = COALESCE(country_code, 'GB'),
    domain           = COALESCE(domain, 'employment_uk'),
    source_type      = COALESCE(source_type, 'primary_legislation'),
    licence_status   = COALESCE(licence_status, 'GRANTED'),
    parser_type      = COALESCE(parser_type, 'clml_xml'),
    parent_source_id = COALESCE(parent_source_id, 'legislation_gov_uk'),
    jurisdiction     = COALESCE(jurisdiction, 'EW');

-- ── acas_guidance ──────────────────────────────────────────────────────────
ALTER TABLE acas_guidance ADD COLUMN IF NOT EXISTS country_code     TEXT;
ALTER TABLE acas_guidance ADD COLUMN IF NOT EXISTS jurisdiction     TEXT;
ALTER TABLE acas_guidance ADD COLUMN IF NOT EXISTS domain           TEXT;
ALTER TABLE acas_guidance ADD COLUMN IF NOT EXISTS source_type      TEXT;
ALTER TABLE acas_guidance ADD COLUMN IF NOT EXISTS licence_status   TEXT;
ALTER TABLE acas_guidance ADD COLUMN IF NOT EXISTS parser_type      TEXT;
ALTER TABLE acas_guidance ADD COLUMN IF NOT EXISTS parent_source_id TEXT;
UPDATE acas_guidance SET
    country_code     = COALESCE(country_code, 'GB'),
    jurisdiction     = COALESCE(jurisdiction, 'EW'),
    domain           = COALESCE(domain, 'employment_uk'),
    source_type      = COALESCE(source_type, 'official_guidance'),
    licence_status   = COALESCE(licence_status, 'GRANTED'),
    parser_type      = COALESCE(parser_type, 'html'),
    parent_source_id = COALESCE(parent_source_id, 'acas');

-- ── official_guidance (GOV.UK) ─────────────────────────────────────────────
ALTER TABLE official_guidance ADD COLUMN IF NOT EXISTS country_code     TEXT;
ALTER TABLE official_guidance ADD COLUMN IF NOT EXISTS domain           TEXT;
ALTER TABLE official_guidance ADD COLUMN IF NOT EXISTS source_type      TEXT;
ALTER TABLE official_guidance ADD COLUMN IF NOT EXISTS licence_status   TEXT;
ALTER TABLE official_guidance ADD COLUMN IF NOT EXISTS parser_type      TEXT;
ALTER TABLE official_guidance ADD COLUMN IF NOT EXISTS parent_source_id TEXT;
UPDATE official_guidance SET
    country_code     = COALESCE(country_code, 'GB'),
    jurisdiction     = COALESCE(jurisdiction, 'EW'),
    domain           = COALESCE(domain, 'employment_uk'),
    source_type      = COALESCE(source_type, 'official_guidance'),
    licence_status   = COALESCE(licence_status, 'GRANTED'),
    parser_type      = COALESCE(parser_type, 'html'),
    parent_source_id = COALESCE(parent_source_id, 'govuk');

-- content_hash backfill for guidance tables (migration 026 only covered legislation).
UPDATE acas_guidance
   SET content_hash = encode(sha256(coalesce(body_text,'')::bytea), 'hex')
 WHERE content_hash IS NULL OR content_hash = '';
UPDATE official_guidance
   SET content_hash = encode(sha256(coalesce(body_text,'')::bytea), 'hex')
 WHERE content_hash IS NULL OR content_hash = '';

-- ── rules ──────────────────────────────────────────────────────────────────
ALTER TABLE rules ADD COLUMN IF NOT EXISTS domain       TEXT;
ALTER TABLE rules ADD COLUMN IF NOT EXISTS country_code TEXT;
UPDATE rules SET
    domain       = COALESCE(domain, 'employment_uk'),
    country_code = COALESCE(country_code, 'GB');
