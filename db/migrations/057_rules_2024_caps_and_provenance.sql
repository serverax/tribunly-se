-- 057_rules_2024_caps_and_provenance.sql
-- Backfill effective-dated 2024 unfair-dismissal cap rows and normalize rules
-- provenance columns for rows inserted before the legal-data-spine migration.

ALTER TABLE legal_jurisdictions ADD COLUMN IF NOT EXISTS jurisdiction_code TEXT;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='legal_jurisdictions' AND column_name='jurisdiction'
  ) THEN
    EXECUTE '
      UPDATE legal_jurisdictions
      SET jurisdiction_code = COALESCE(NULLIF(jurisdiction_code, ''''), NULLIF(jurisdiction, ''''), country_code)
      WHERE jurisdiction_code IS NULL OR jurisdiction_code = ''''
    ';
  ELSE
    EXECUTE '
      UPDATE legal_jurisdictions
      SET jurisdiction_code = COALESCE(NULLIF(jurisdiction_code, ''''), country_code)
      WHERE jurisdiction_code IS NULL OR jurisdiction_code = ''''
    ';
  END IF;
END $$;

DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['legislation','acas_guidance','official_guidance','rules','case_law_documents','corpus_chunks'] LOOP
    EXECUTE format('ALTER TABLE IF EXISTS %I ADD COLUMN IF NOT EXISTS jurisdiction_code TEXT', t);
  END LOOP;
  FOREACH t IN ARRAY ARRAY['legislation','acas_guidance','official_guidance','rules','corpus_chunks'] LOOP
    EXECUTE format('ALTER TABLE IF EXISTS %I ADD COLUMN IF NOT EXISTS country_code TEXT', t);
    EXECUTE format('ALTER TABLE IF EXISTS %I ADD COLUMN IF NOT EXISTS domain TEXT', t);
  END LOOP;
  FOREACH t IN ARRAY ARRAY['legislation','acas_guidance','official_guidance','rules','case_law_documents'] LOOP
    EXECUTE format('ALTER TABLE IF EXISTS %I ADD COLUMN IF NOT EXISTS legal_system TEXT', t);
    EXECUTE format('ALTER TABLE IF EXISTS %I ADD COLUMN IF NOT EXISTS applies_to_ni BOOLEAN DEFAULT false', t);
    EXECUTE format('ALTER TABLE IF EXISTS %I ADD COLUMN IF NOT EXISTS applies_to_scotland BOOLEAN DEFAULT false', t);
    EXECUTE format('ALTER TABLE IF EXISTS %I ADD COLUMN IF NOT EXISTS applies_to_england_wales BOOLEAN DEFAULT false', t);
    EXECUTE format('ALTER TABLE IF EXISTS %I ADD COLUMN IF NOT EXISTS applies_to_gb BOOLEAN DEFAULT false', t);
  END LOOP;
  ALTER TABLE IF EXISTS rules ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT true;
END $$;

INSERT INTO rules
  (rule_key, claim_type, jurisdiction, jurisdiction_code, domain, country_code,
   value_numeric, value_text, unit, description, authority_type, authority_ref, authority_url,
   effective_from, effective_to, is_prospective, verification_status, last_verified_at,
   legal_system, applies_to_gb, applies_to_england_wales, applies_to_scotland, applies_to_ni,
   is_current)
VALUES
 ('unfair_dismissal.acas_code_adjustment_percent','unfair_dismissal','EW','GB','employment_uk','GB',
  25, NULL, 'percent',
  'Tribunal may adjust any award by up to 25% for unreasonable failure to comply with the ACAS Code of Practice on Disciplinary and Grievance Procedures (uplift against employer, reduction against employee).',
  'legislation','TULRCA 1992 s.207A','https://www.legislation.gov.uk/ukpga/1992/52/section/207A',
  DATE '2009-04-06', NULL, false, 'verified', now(),
  'Great Britain', true, true, true, false, true),
 ('unfair_dismissal.not_reasonably_practicable_extension','unfair_dismissal','EW','GB','employment_uk','GB',
  NULL,
  'The tribunal may consider a complaint presented after the primary time limit where it was not reasonably practicable to present it in time, and it was then presented within such further period as the tribunal considers reasonable.',
  'qualitative',
  'Statutory escape clause extending the primary 3-month time limit for ordinary unfair dismissal where presentation in time was not reasonably practicable.',
  'legislation','ERA 1996 s.111(2)(b)','https://www.legislation.gov.uk/ukpga/1996/18/section/111',
  DATE '1996-08-22', NULL, false, 'verified', now(),
  'Great Britain', true, true, true, false, true)
ON CONFLICT (rule_key, jurisdiction, effective_from) DO UPDATE SET
  value_numeric=EXCLUDED.value_numeric,
  value_text=EXCLUDED.value_text,
  unit=EXCLUDED.unit,
  description=EXCLUDED.description,
  authority_ref=EXCLUDED.authority_ref,
  authority_url=EXCLUDED.authority_url,
  jurisdiction_code=EXCLUDED.jurisdiction_code,
  domain=EXCLUDED.domain,
  country_code=EXCLUDED.country_code,
  verification_status=EXCLUDED.verification_status,
  legal_system=EXCLUDED.legal_system,
  applies_to_gb=EXCLUDED.applies_to_gb,
  applies_to_england_wales=EXCLUDED.applies_to_england_wales,
  applies_to_scotland=EXCLUDED.applies_to_scotland,
  applies_to_ni=EXCLUDED.applies_to_ni,
  is_current=EXCLUDED.is_current,
  last_verified_at=now();

INSERT INTO rules
  (rule_key, claim_type, jurisdiction, jurisdiction_code, domain, country_code,
   value_numeric, value_text, unit, description, authority_type, authority_ref, authority_url,
   effective_from, effective_to, is_prospective, verification_status, last_verified_at,
   legal_system, applies_to_gb, applies_to_england_wales, applies_to_scotland, applies_to_ni,
   is_current)
VALUES
 ('unfair_dismissal.weeks_pay_cap_amount','unfair_dismissal','EW','GB','employment_uk','GB',
  700, NULL, 'GBP',
  'Maximum week''s pay for basic award (ERA 1996 s.227(1)), SI 2024/213. Applies where EDT is on or after 6 April 2024 and before 6 April 2025.',
  'legislation','ERA 1996 s.227(1) + SI 2024/213','https://www.legislation.gov.uk/uksi/2024/213/schedule/made',
  DATE '2024-04-06', DATE '2025-04-05', false, 'verified', now(),
  'Great Britain', true, true, true, false, false),
 ('unfair_dismissal.compensatory_cap_amount','unfair_dismissal','EW','GB','employment_uk','GB',
  115115, NULL, 'GBP',
  'Limb A statutory compensatory cap (ERA 1996 s.124(1ZA)(a)), SI 2024/213. Applies where EDT is on or after 6 April 2024 and before 6 April 2025.',
  'legislation','ERA 1996 s.124(1ZA)(a) + SI 2024/213','https://www.legislation.gov.uk/uksi/2024/213/schedule/made',
  DATE '2024-04-06', DATE '2025-04-05', false, 'verified', now(),
  'Great Britain', true, true, true, false, false)
ON CONFLICT (rule_key, jurisdiction, effective_from) DO UPDATE SET
  value_numeric=EXCLUDED.value_numeric,
  value_text=EXCLUDED.value_text,
  unit=EXCLUDED.unit,
  description=EXCLUDED.description,
  authority_ref=EXCLUDED.authority_ref,
  authority_url=EXCLUDED.authority_url,
  effective_to=EXCLUDED.effective_to,
  is_prospective=EXCLUDED.is_prospective,
  verification_status=EXCLUDED.verification_status,
  jurisdiction_code=EXCLUDED.jurisdiction_code,
  domain=EXCLUDED.domain,
  country_code=EXCLUDED.country_code,
  legal_system=EXCLUDED.legal_system,
  applies_to_gb=EXCLUDED.applies_to_gb,
  applies_to_england_wales=EXCLUDED.applies_to_england_wales,
  applies_to_scotland=EXCLUDED.applies_to_scotland,
  applies_to_ni=EXCLUDED.applies_to_ni,
  is_current=EXCLUDED.is_current,
  last_verified_at=now();

UPDATE rules
SET jurisdiction_code = COALESCE(jurisdiction_code, 'GB'),
    domain = COALESCE(domain, 'employment_uk'),
    country_code = COALESCE(country_code, 'GB'),
    legal_system = COALESCE(legal_system, 'Great Britain'),
    applies_to_gb = COALESCE(applies_to_gb, true),
    applies_to_england_wales = COALESCE(applies_to_england_wales, true),
    applies_to_scotland = COALESCE(applies_to_scotland, true),
    applies_to_ni = COALESCE(applies_to_ni, false),
    last_verified_at = COALESCE(last_verified_at, now())
WHERE claim_type IN ('unfair_dismissal', 'unpaid_wages');

UPDATE legislation
SET jurisdiction_code = COALESCE(NULLIF(jurisdiction_code, ''), 'GB'),
    domain = COALESCE(NULLIF(domain, ''), 'employment_uk'),
    country_code = COALESCE(NULLIF(country_code, ''), 'GB'),
    legal_system = COALESCE(NULLIF(legal_system, ''), 'Great Britain'),
    applies_to_gb = COALESCE(applies_to_gb, true),
    applies_to_england_wales = COALESCE(applies_to_england_wales, true),
    applies_to_scotland = COALESCE(applies_to_scotland, true),
    applies_to_ni = COALESCE(applies_to_ni, false),
    last_verified_at = COALESCE(last_verified_at, now())
WHERE jurisdiction_code IS NULL
   OR jurisdiction_code = ''
   OR legal_system IS NULL
   OR country_code IS NULL
   OR domain IS NULL;

UPDATE acas_guidance
SET jurisdiction_code = COALESCE(NULLIF(jurisdiction_code, ''), 'GB'),
    domain = COALESCE(NULLIF(domain, ''), 'employment_uk'),
    country_code = COALESCE(NULLIF(country_code, ''), 'GB'),
    jurisdiction = COALESCE(NULLIF(jurisdiction, ''), 'EW'),
    legal_system = COALESCE(NULLIF(legal_system, ''), 'Great Britain'),
    applies_to_gb = COALESCE(applies_to_gb, true),
    applies_to_england_wales = COALESCE(applies_to_england_wales, true),
    applies_to_scotland = COALESCE(applies_to_scotland, true),
    applies_to_ni = COALESCE(applies_to_ni, false),
    last_verified_at = COALESCE(last_verified_at, now())
WHERE jurisdiction_code IS NULL
   OR jurisdiction_code = ''
   OR legal_system IS NULL
   OR country_code IS NULL
   OR domain IS NULL
   OR jurisdiction IS NULL;

UPDATE official_guidance
SET jurisdiction_code = COALESCE(NULLIF(jurisdiction_code, ''), 'GB'),
    domain = COALESCE(NULLIF(domain, ''), 'employment_uk'),
    country_code = COALESCE(NULLIF(country_code, ''), 'GB'),
    jurisdiction = COALESCE(NULLIF(jurisdiction, ''), 'EW'),
    legal_system = COALESCE(NULLIF(legal_system, ''), 'Great Britain'),
    applies_to_gb = COALESCE(applies_to_gb, true),
    applies_to_england_wales = COALESCE(applies_to_england_wales, true),
    applies_to_scotland = COALESCE(applies_to_scotland, true),
    applies_to_ni = COALESCE(applies_to_ni, false),
    last_verified_at = COALESCE(last_verified_at, now())
WHERE jurisdiction_code IS NULL
   OR jurisdiction_code = ''
   OR legal_system IS NULL
   OR country_code IS NULL
   OR domain IS NULL
   OR jurisdiction IS NULL;

UPDATE corpus_chunks
SET jurisdiction_code = COALESCE(NULLIF(jurisdiction_code, ''), 'GB'),
    domain = COALESCE(NULLIF(domain, ''), 'employment_uk'),
    country_code = COALESCE(NULLIF(country_code, ''), 'GB')
WHERE jurisdiction_code IS NULL
   OR jurisdiction_code = ''
   OR country_code IS NULL
   OR domain IS NULL;

UPDATE rules
SET is_current = (
    is_prospective = false
    AND effective_from <= CURRENT_DATE
    AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
);

DROP MATERIALIZED VIEW IF EXISTS mv_current_employment_legal_chunks;
CREATE MATERIALIZED VIEW mv_current_employment_legal_chunks AS
SELECT c.id, c.source_table, c.source_row_uuid, c.source_id, c.domain, c.claim_type,
       c.jurisdiction_code, c.authority_ref, c.source_url, c.title, c.heading,
       c.body_text, c.chunk_index, c.chunk_hash, c.embedding, c.embedding_model,
       c.effective_from, c.effective_to, c.quality_score, c.source_type, c.licence_status
FROM corpus_chunks c
WHERE c.is_current = true
  AND COALESCE(c.is_prospective,false) = false
  AND c.jurisdiction_code IN ('GB','EW','S','UK')
  AND c.source_url IS NOT NULL AND c.source_url <> ''
  AND c.chunk_hash IS NOT NULL AND c.chunk_hash <> ''
  AND c.body_text IS NOT NULL AND c.body_text <> ''
  AND COALESCE(c.quality_score, 0) >= 0.6
  AND (c.licence_status IS NULL OR c.licence_status IN ('open','GRANTED','granted'));
CREATE UNIQUE INDEX IF NOT EXISTS mv_current_chunks_hash_idx ON mv_current_employment_legal_chunks (chunk_hash);
CREATE INDEX IF NOT EXISTS mv_current_chunks_juris_idx ON mv_current_employment_legal_chunks (jurisdiction_code, claim_type);
