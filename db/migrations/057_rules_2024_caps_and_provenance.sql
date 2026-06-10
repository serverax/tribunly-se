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
  ALTER TABLE IF EXISTS legislation ADD COLUMN IF NOT EXISTS content_hash TEXT;
  ALTER TABLE IF EXISTS rules ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT true;
  ALTER TABLE IF EXISTS user_legal_profiles ADD COLUMN IF NOT EXISTS jurisdiction_code TEXT;
  ALTER TABLE IF EXISTS deadline_calculation_audit ADD COLUMN IF NOT EXISTS jurisdiction_code TEXT;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='deadline_calculation_audit' AND column_name='jurisdiction'
  ) THEN
    EXECUTE 'ALTER TABLE deadline_calculation_audit ALTER COLUMN jurisdiction DROP NOT NULL';
    EXECUTE '
      UPDATE deadline_calculation_audit
      SET jurisdiction_code = COALESCE(NULLIF(jurisdiction_code, ''''), NULLIF(jurisdiction, ''''), ''GB'')
      WHERE jurisdiction_code IS NULL OR jurisdiction_code = ''''
    ';
  ELSE
    EXECUTE '
      UPDATE deadline_calculation_audit
      SET jurisdiction_code = COALESCE(NULLIF(jurisdiction_code, ''''), ''GB'')
      WHERE jurisdiction_code IS NULL OR jurisdiction_code = ''''
    ';
  END IF;
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

INSERT INTO legislation
  (act_title, leg_type, year, chapter, section_ref, jurisdiction, heading,
   body_text, chunk_index, source_url, effective_from, last_verified_at,
   content_hash, country_code, domain, source_type, licence_status,
   parser_type, parent_source_id, jurisdiction_code, legal_system,
   applies_to_gb, applies_to_england_wales, applies_to_scotland, applies_to_ni)
VALUES
 ('Employment Rights Act 1996','primary',1996,'18','13','EW',
  'Right not to suffer unauthorised deductions',
  'A worker has the right not to suffer unauthorised deductions from wages. This section is the core unlawful deduction from wages protection.',
  0,'https://www.legislation.gov.uk/ukpga/1996/18/section/13',
  DATE '1996-08-22', now(),
  encode(sha256('ERA 1996 s13 unpaid wages'::bytea), 'hex'),
  'GB','employment_uk','primary_legislation','GRANTED','seeded_text','legislation_gov_uk',
  'GB','Great Britain',true,true,true,false),
 ('Employment Rights Act 1996','primary',1996,'18','23','EW',
  'Complaints to employment tribunals',
  'A worker may present a complaint to an employment tribunal that an employer has made an unauthorised deduction from wages.',
  0,'https://www.legislation.gov.uk/ukpga/1996/18/section/23',
  DATE '1996-08-22', now(),
  encode(sha256('ERA 1996 s23 wages complaint'::bytea), 'hex'),
  'GB','employment_uk','primary_legislation','GRANTED','seeded_text','legislation_gov_uk',
  'GB','Great Britain',true,true,true,false),
 ('Employment Rights Act 1996','primary',1996,'18','24','EW',
  'Determination of complaints',
  'Where an unlawful deduction complaint is well founded, the employment tribunal may make a declaration and order repayment of the amount deducted.',
  0,'https://www.legislation.gov.uk/ukpga/1996/18/section/24',
  DATE '1996-08-22', now(),
  encode(sha256('ERA 1996 s24 wages remedy'::bytea), 'hex'),
  'GB','employment_uk','primary_legislation','GRANTED','seeded_text','legislation_gov_uk',
  'GB','Great Britain',true,true,true,false),
 ('Employment Rights Act 1996','primary',1996,'18','124','EW',
  'Compensatory award',
  'Section 124 sets out the calculation and statutory cap for the compensatory award in unfair dismissal claims.',
  0,'https://www.legislation.gov.uk/ukpga/1996/18/section/124',
  DATE '1996-08-22', now(),
  encode(sha256('ERA 1996 s124 compensatory award'::bytea), 'hex'),
  'GB','employment_uk','primary_legislation','GRANTED','seeded_text','legislation_gov_uk',
  'GB','Great Britain',true,true,true,false),
 ('Employment Rights Act 1996','primary',1996,'18','227','EW',
  'Maximum amount of a week''s pay',
  'Section 227 defines the statutory limit on a week''s pay used in employment tribunal award calculations.',
  0,'https://www.legislation.gov.uk/ukpga/1996/18/section/227',
  DATE '1996-08-22', now(),
  encode(sha256('ERA 1996 s227 weeks pay cap'::bytea), 'hex'),
  'GB','employment_uk','primary_legislation','GRANTED','seeded_text','legislation_gov_uk',
  'GB','Great Britain',true,true,true,false)
ON CONFLICT (source_url, chunk_index) DO UPDATE SET
  act_title=EXCLUDED.act_title,
  section_ref=EXCLUDED.section_ref,
  heading=EXCLUDED.heading,
  body_text=EXCLUDED.body_text,
  effective_from=EXCLUDED.effective_from,
  last_verified_at=now(),
  content_hash=EXCLUDED.content_hash,
  country_code=EXCLUDED.country_code,
  domain=EXCLUDED.domain,
  source_type=EXCLUDED.source_type,
  licence_status=EXCLUDED.licence_status,
  parser_type=EXCLUDED.parser_type,
  parent_source_id=EXCLUDED.parent_source_id,
  jurisdiction_code=EXCLUDED.jurisdiction_code,
  legal_system=EXCLUDED.legal_system,
  applies_to_gb=EXCLUDED.applies_to_gb,
  applies_to_england_wales=EXCLUDED.applies_to_england_wales,
  applies_to_scotland=EXCLUDED.applies_to_scotland,
  applies_to_ni=EXCLUDED.applies_to_ni;

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

DROP VIEW IF EXISTS source_freshness;
CREATE VIEW source_freshness AS
WITH base AS (
  SELECT 'legislation' AS source_name, 'legislation' AS source_type, 'legislation' AS run_src, jurisdiction_code, last_verified_at FROM legislation
  UNION ALL SELECT 'acas_guidance','acas','acas', jurisdiction_code, last_verified_at FROM acas_guidance
  UNION ALL SELECT 'official_guidance','govuk','govuk', jurisdiction_code, last_verified_at FROM official_guidance
  UNION ALL SELECT 'rules','rules','limits_orders', jurisdiction_code, last_verified_at FROM rules
  UNION ALL SELECT 'case_law_documents','case_law','case_law', jurisdiction_code, last_verified_at FROM case_law_documents
)
SELECT b.source_name, b.source_type, b.jurisdiction_code,
       count(*) AS rows_count,
       count(*) AS rows,
       min(b.last_verified_at) AS oldest_verified_at,
       min(b.last_verified_at) AS oldest_verified,
       max(b.last_verified_at) AS newest_verified_at,
       count(*) FILTER (WHERE b.last_verified_at < now() - interval '120 days') AS stale_rows_count,
       (SELECT r.status FROM corpus_ingestion_runs r WHERE r.source_id = b.run_src ORDER BY r.created_at DESC LIMIT 1) AS last_ingestion_status,
       (SELECT COALESCE(r.finished_at, r.completed_at) FROM corpus_ingestion_runs r WHERE r.source_id = b.run_src ORDER BY r.created_at DESC LIMIT 1) AS last_ingestion_finished_at
FROM base b
GROUP BY b.source_name, b.source_type, b.jurisdiction_code, b.run_src;

DROP VIEW IF EXISTS corpus_quality_report;
CREATE VIEW corpus_quality_report AS
SELECT
   c.source_type, c.domain, c.claim_type, c.jurisdiction_code,
   count(*) AS total_chunks,
   count(*) FILTER (WHERE c.embedding IS NOT NULL) AS chunks_with_embedding,
   count(*) FILTER (WHERE c.embedding IS NULL) AS chunks_without_embedding,
   count(*) FILTER (WHERE c.source_url IS NOT NULL AND c.source_url <> '') AS chunks_with_source_url,
   count(*) FILTER (WHERE c.source_url IS NULL OR c.source_url = '') AS chunks_without_source_url,
   round(avg(c.quality_score), 3) AS avg_quality_score,
   (SELECT count(*) FROM rules WHERE verification_status NOT IN ('verified','case_law_verified')) AS unverified_rules_count,
   (SELECT count(*) FROM rules WHERE is_prospective) AS prospective_rows_count,
   (count(*) - count(DISTINCT c.chunk_hash)) AS duplicate_hash_count
FROM corpus_chunks c
GROUP BY c.source_type, c.domain, c.claim_type, c.jurisdiction_code;

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
