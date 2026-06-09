-- 033_seed_required_rules.sql
-- Seed the two remaining required GB unfair-dismissal rule keys, fully cited and
-- effective-dated. Values come from primary legislation already in the corpus
-- (TULRCA 1992 s.207A; ERA 1996 s.111(2)(b)) — not hardcoded in app logic.
-- Idempotent via the (rule_key, jurisdiction, effective_from) unique key.

INSERT INTO rules
  (rule_key, claim_type, jurisdiction, jurisdiction_code, domain, country_code,
   value_numeric, value_text, unit, description, authority_type, authority_ref, authority_url,
   effective_from, is_prospective, verification_status, last_verified_at,
   legal_system, applies_to_gb, applies_to_england_wales, applies_to_scotland, applies_to_ni)
VALUES
 ('unfair_dismissal.acas_code_adjustment_percent','unfair_dismissal','EW','GB','employment_uk','GB',
  25, NULL, 'percent',
  'Tribunal may adjust any award by up to 25% for unreasonable failure to comply with the ACAS Code of Practice on Disciplinary and Grievance Procedures (uplift against employer, reduction against employee).',
  'legislation','TULRCA 1992 s.207A','https://www.legislation.gov.uk/ukpga/1992/52/section/207A',
  DATE '2009-04-06', false, 'verified', now(),
  'Great Britain', true, true, true, false),
 ('unfair_dismissal.not_reasonably_practicable_extension','unfair_dismissal','EW','GB','employment_uk','GB',
  NULL,
  'The tribunal may consider a complaint presented after the primary time limit where it was not reasonably practicable to present it in time, and it was then presented within such further period as the tribunal considers reasonable.',
  'qualitative',
  'Statutory escape clause extending the primary 3-month time limit for ordinary unfair dismissal where presentation in time was not reasonably practicable.',
  'legislation','ERA 1996 s.111(2)(b)','https://www.legislation.gov.uk/ukpga/1996/18/section/111',
  DATE '1996-08-22', false, 'verified', now(),
  'Great Britain', true, true, true, false)
ON CONFLICT (rule_key, jurisdiction, effective_from) DO UPDATE SET
  value_numeric=EXCLUDED.value_numeric, value_text=EXCLUDED.value_text, unit=EXCLUDED.unit,
  description=EXCLUDED.description, authority_ref=EXCLUDED.authority_ref, authority_url=EXCLUDED.authority_url,
  jurisdiction_code=EXCLUDED.jurisdiction_code, domain=EXCLUDED.domain, verification_status=EXCLUDED.verification_status,
  last_verified_at=now();
