-- Promote the first two additional employment modules only after DB-backed
-- rules and deterministic workflow proof exist. Remaining modules stay partial.

INSERT INTO rules (
  rule_key, claim_type, jurisdiction, country_code, domain, legal_system,
  value_numeric, value_text, unit, effective_from, effective_to,
  authority_type, authority_ref, authority_url,
  verification_status, last_verified_at,
  is_prospective, is_current, applies_to_england_wales, applies_to_scotland, applies_to_gb,
  description
)
VALUES
 ('redundancy.weeks_pay_cap_amount','redundancy','GB','GB','employment_uk','GB',
  700,NULL,'GBP','2024-04-06','2025-04-05',
  'legislation',
  'ERA 1996 s.227(1) + SI 2024/213','https://www.legislation.gov.uk/uksi/2024/213/schedule/made',
  'verified',NOW(),false,false,true,true,true,
  'Maximum amount of a week''s pay for statutory redundancy payment calculations.'),
 ('redundancy.weeks_pay_cap_amount','redundancy','GB','GB','employment_uk','GB',
  719,NULL,'GBP','2025-04-06','2026-04-05',
  'legislation',
  'ERA 1996 s.227(1) + SI 2025/348','https://www.legislation.gov.uk/uksi/2025/348/schedule/made',
  'verified',NOW(),false,false,true,true,true,
  'Maximum amount of a week''s pay for statutory redundancy payment calculations.'),
 ('redundancy.weeks_pay_cap_amount','redundancy','GB','GB','employment_uk','GB',
  751,NULL,'GBP','2026-04-06',NULL,
  'legislation',
  'ERA 1996 s.227(1) + SI 2026/310','https://www.legislation.gov.uk/uksi/2026/310/schedule/made',
  'verified',NOW(),false,true,true,true,true,
  'Maximum amount of a week''s pay for statutory redundancy payment calculations.'),
 ('redundancy.max_years_counted','redundancy','GB','GB','employment_uk','GB',
  20,NULL,'years','1996-08-22',NULL,
  'legislation',
  'ERA 1996 s.162(3)','https://www.legislation.gov.uk/ukpga/1996/18/section/162',
  'verified',NOW(),false,true,true,true,true,
  'Maximum complete years counted for statutory redundancy payment.'),
 ('redundancy.multiplier_under_22','redundancy','GB','GB','employment_uk','GB',
  0.5,NULL,'weeks','1996-08-22',NULL,
  'legislation',
  'ERA 1996 s.162(1)','https://www.legislation.gov.uk/ukpga/1996/18/section/162',
  'verified',NOW(),false,true,true,true,true,
  'Half a week''s pay for each counted year where the employee was under 22.'),
 ('redundancy.multiplier_22_to_40','redundancy','GB','GB','employment_uk','GB',
  1,NULL,'weeks','1996-08-22',NULL,
  'legislation',
  'ERA 1996 s.162(1)','https://www.legislation.gov.uk/ukpga/1996/18/section/162',
  'verified',NOW(),false,true,true,true,true,
  'One week''s pay for each counted year where the employee was aged 22 to 40.'),
 ('redundancy.multiplier_41_plus','redundancy','GB','GB','employment_uk','GB',
  1.5,NULL,'weeks','1996-08-22',NULL,
  'legislation',
  'ERA 1996 s.162(1)','https://www.legislation.gov.uk/ukpga/1996/18/section/162',
  'verified',NOW(),false,true,true,true,true,
  'One and a half weeks'' pay for each counted year where the employee was aged 41 or over.')
ON CONFLICT (rule_key, jurisdiction, effective_from) DO UPDATE SET
  value_numeric = EXCLUDED.value_numeric,
  authority_ref = EXCLUDED.authority_ref,
  authority_url = EXCLUDED.authority_url,
  verification_status = EXCLUDED.verification_status,
  last_verified_at = EXCLUDED.last_verified_at,
  is_current = EXCLUDED.is_current,
  description = EXCLUDED.description;

UPDATE employment_modules
SET status = 'production',
    updated_at = NOW()
WHERE module_key IN ('redundancy', 'wrongful_dismissal');
