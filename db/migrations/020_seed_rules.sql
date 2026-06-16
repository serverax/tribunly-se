-- Migration 020  -  Seed rules data
-- Seeds all effective-dated rules from primary UK legislation sources.
-- This migration is idempotent: ON CONFLICT DO NOTHING.
-- Running it multiple times is safe.
--
-- Sources verified 2026-05-31 from legislation.gov.uk
-- Authority: ERA 1996, ERRA 2013, ERA 2025, relevant SIs
-- All values from primary legislation only  -  not from AI memory.

-- Unfair dismissal rules
INSERT INTO rules (rule_key, claim_type, jurisdiction, value_numeric, value_text, unit, description, authority_type, authority_ref, authority_url, effective_from, effective_to, is_prospective, last_verified_at)
VALUES

-- ── Time limit: current 3 months ────────────────────────────────────────────
('unfair_dismissal.time_limit_months', 'unfair_dismissal', 'EW',
 3, NULL, 'months',
 'Primary limitation period: claim presented before end of 3 months beginning with EDT (ERA 1996 s.111(2); in force 1996-08-22). EC stop-the-clock (s.207B) in force 2014-04-06.',
 'legislation',
 'ERA 1996 s.111(2) (commencement 1996-08-22); ERA 1996 s.207B (in force 2014-04-06, inserted by ERRA 2013); Luton Borough Council v Haque UKEAT/0180/17/JOJ [2018] UKEAT 0180_17_1204 para 17 (ratio) and para 26 (no-op (3) case)',
 'https://www.legislation.gov.uk/ukpga/1996/18/section/111',
 '1996-08-22', NULL, false, now()),

-- ── Time limit: prospective 6 months (ERA 2025) ───────────────────────────
('unfair_dismissal.time_limit_months', 'unfair_dismissal', 'EW',
 6, NULL, 'months',
 'PROSPECTIVE  -  NOT IN FORCE. ERA 2025 s.152 + Schedule 12 para 4(25) extends the time limit to 6 months. Commencement SI pending; effective_from is PROVISIONAL.',
 'legislation',
 'Employment Rights Act 2025 s.152 and Schedule 12 para 4(25) (amending ERA 1996 s.111(2)); commencement SI pending  -  effective_from is PROVISIONAL from government statements',
 'https://www.legislation.gov.uk/ukpga/2025/36/section/152',
 '2026-10-01', NULL, true, now()),

-- ── Early Conciliation required ───────────────────────────────────────────
('unfair_dismissal.early_conciliation_required', 'unfair_dismissal', 'EW',
 NULL, 'true', NULL,
 'Prospective claimant must notify ACAS and obtain EC certificate before presenting claim (ETA 1996 s.18A; in force 2014-04-06).',
 'legislation',
 'Employment Tribunals Act 1996 s.18A (in force 2014-04-06 per Haque para 30; inserted by ERRA 2013 s.7); SI 2014/253 (mandatory requirement from 2014-05-06)',
 'https://www.legislation.gov.uk/ukpga/1996/17/section/18A',
 '2014-04-06', NULL, false, now()),

-- ── Qualifying period: current 2 years ───────────────────────────────────
('unfair_dismissal.qualifying_period', 'unfair_dismissal', 'EW',
 2, NULL, 'years',
 'Continuous employment of not less than 2 years ending with EDT (ERA 1996 s.108(1)). Introduced by SI 2012/989 on 2012-04-06.',
 'legislation',
 'ERA 1996 s.108(1); SI 2012/989 (Unfair Dismissal and Statement of Reasons for Dismissal (Variation of Qualifying Period) Order 2012)',
 'https://www.legislation.gov.uk/ukpga/1996/18/section/108',
 '2012-04-06', NULL, false, now()),

-- ── Qualifying period: prospective 6 months (ERA 2025) ───────────────────
('unfair_dismissal.qualifying_period', 'unfair_dismissal', 'EW',
 6, NULL, 'months',
 'PROSPECTIVE  -  NOT IN FORCE. ERA 2025 s.25(2) substitutes six months for two years. Commencement SI pending; effective_from is PROVISIONAL.',
 'legislation',
 'Employment Rights Act 2025 s.25(2) (amending ERA 1996 s.108(1) and (2)); commencement SI pending  -  effective_from is PROVISIONAL',
 'https://www.legislation.gov.uk/ukpga/2025/36/section/25',
 '2027-01-01', NULL, true, now()),

-- ── Week''s pay cap 2025 ─────────────────────────────────────────────────
('unfair_dismissal.weeks_pay_cap_amount', 'unfair_dismissal', 'EW',
 719, NULL, 'GBP',
 'Maximum week''s pay for basic award (ERA 1996 s.227(1)), SI 2025/348. Applies where EDT is on or after 2025-04-06 and before 2026-04-06.',
 'legislation',
 'ERA 1996 s.227(1) + SI 2025/348',
 'https://www.legislation.gov.uk/uksi/2025/348/schedule/made',
 '2025-04-06', '2026-04-05', false, now()),

-- ── Week''s pay cap 2026 ─────────────────────────────────────────────────
('unfair_dismissal.weeks_pay_cap_amount', 'unfair_dismissal', 'EW',
 751, NULL, 'GBP',
 'Maximum week''s pay for basic award (ERA 1996 s.227(1)), SI 2026/310. Applies where EDT is on or after 2026-04-06.',
 'legislation',
 'ERA 1996 s.227(1) + SI 2026/310',
 'https://www.legislation.gov.uk/uksi/2026/310/schedule/made',
 '2026-04-06', NULL, false, now()),

-- ── Compensatory cap 2025 ────────────────────────────────────────────────
('unfair_dismissal.compensatory_cap_amount', 'unfair_dismissal', 'EW',
 118223, NULL, 'GBP',
 'Limb A statutory compensatory cap (ERA 1996 s.124(1ZA)(a)), SI 2025/348. Applies where EDT is on or after 2025-04-06 and before 2026-04-06.',
 'legislation',
 'ERA 1996 s.124(1ZA)(a) + SI 2025/348',
 'https://www.legislation.gov.uk/uksi/2025/348/schedule/made',
 '2025-04-06', '2026-04-05', false, now()),

-- ── Compensatory cap 2026 ────────────────────────────────────────────────
('unfair_dismissal.compensatory_cap_amount', 'unfair_dismissal', 'EW',
 123543, NULL, 'GBP',
 'Limb A statutory compensatory cap (ERA 1996 s.124(1ZA)(a)), SI 2026/310. Applies where EDT is on or after 2026-04-06.',
 'legislation',
 'ERA 1996 s.124(1ZA)(a) + SI 2026/310',
 'https://www.legislation.gov.uk/uksi/2026/310/schedule/made',
 '2026-04-06', NULL, false, now()),

-- ── Compensatory cap: prospective omission (ERA 2025) ────────────────────
('unfair_dismissal.compensatory_cap_amount', 'unfair_dismissal', 'EW',
 NULL, 's124_omitted_by_era2025_s25', 'GBP',
 'PROSPECTIVE  -  NOT IN FORCE. ERA 2025 s.25(3): omit section 124. Commencement SI pending; effective_from is PROVISIONAL.',
 'legislation',
 'Employment Rights Act 2025 s.25(3) (omitting ERA 1996 s.124); commencement SI pending  -  effective_from is PROVISIONAL',
 'https://www.legislation.gov.uk/ukpga/2025/36/section/25',
 '2027-01-01', NULL, true, now()),

-- ── Compensatory cap weeks (52 weeks) ─────────────────────────────────────
('unfair_dismissal.compensatory_cap_weeks_pay', 'unfair_dismissal', 'EW',
 52, NULL, 'weeks_gross_pay',
 'Alternative compensatory cap: 52 x actual gross weekly pay (ERA 1996 s.124(1ZA)(b)). Applied if lower than statutory cap.',
 'legislation',
 'ERA 1996 s.124(1ZA)(b)',
 'https://www.legislation.gov.uk/ukpga/1996/18/section/124',
 '2013-07-29', NULL, false, now()),

-- ── Basic award formula ───────────────────────────────────────────────────
('unfair_dismissal.basic_award_formula', 'unfair_dismissal', 'EW',
 NULL,
 'Per complete year of service (max 20 years): 1.5 x week''s pay for each year while aged 41+; 1.0 x week''s pay for each year while aged 22-40; 0.5 x week''s pay for each year while under 22. Week''s pay capped at weeks_pay_cap_amount (s.227). Computed in application code. Do not hard-code the cap value.',
 NULL,
 'Reference row for the statutory basic award formula (ERA 1996 s.119). The monetary cap is in weeks_pay_cap_amount.',
 'legislation',
 'ERA 1996 s.119',
 'https://www.legislation.gov.uk/ukpga/1996/18/section/119',
 '1996-08-22', NULL, false, now()),

-- ── Basic award minimum (automatic unfair dismissal) ──────────────────────
('unfair_dismissal.basic_award_min_automatic', 'unfair_dismissal', 'EW',
 9157, NULL, 'GBP',
 'Minimum basic award where dismissal is automatically unfair on specified grounds (ERA 1996 s.120), SI 2026/310.',
 'legislation',
 'ERA 1996 s.120(1) + SI 2026/310',
 'https://www.legislation.gov.uk/uksi/2026/310/schedule/made',
 '2026-04-06', NULL, false, now()),

-- ── EC maximum duration ───────────────────────────────────────────────────
('unfair_dismissal.ec_max_duration_weeks', 'unfair_dismissal', 'EW',
 12, NULL, 'weeks',
 'Maximum duration of ACAS Early Conciliation: up to 12 weeks for EC notifications on or after 2025-12-01.',
 'legislation',
 'Employment Tribunals (Early Conciliation: Exemptions and Rules of Procedure) (Amendment) Regulations 2025 (SI 2025/1153), Schedule rule 6(1)',
 'https://www.legislation.gov.uk/uksi/2025/1153/made',
 '2025-12-01', NULL, false, now()),

-- ── Unpaid wages: time limit ──────────────────────────────────────────────
('unlawful_deduction_wages.time_limit_months', 'unpaid_wages', 'EW',
 3, NULL, 'months',
 'Claim must be presented to ET within 3 months of the deduction (ERA 1996 s.23(2)). EC stop-clock applies.',
 'legislation',
 'ERA 1996 s.23(2); ERA 1996 s.207B (EC stop-clock)',
 'https://www.legislation.gov.uk/ukpga/1996/18/section/23',
 '1996-08-22', NULL, false, now()),

-- ── Unpaid wages: qualifying period ──────────────────────────────────────
('unlawful_deduction_wages.qualifying_period_years', 'unpaid_wages', 'EW',
 0, 'none  -  day-one right', 'years',
 'No qualifying period. Day-one right for workers (ERA 1996 s.13).',
 'legislation',
 'ERA 1996 s.13, s.230(3)',
 'https://www.legislation.gov.uk/ukpga/1996/18/section/13',
 '1996-08-22', NULL, false, now()),

-- ── Unpaid wages: worker status ───────────────────────────────────────────
('unlawful_deduction_wages.worker_status', 'unpaid_wages', 'EW',
 NULL, 'worker', NULL,
 'Right applies to workers (s.230(3)): employees, agency workers, casual/zero-hours workers. Self-employed excluded.',
 'legislation',
 'ERA 1996 s.13, s.230(3); Uber v Aslam [2021] UKSC 5',
 'https://www.legislation.gov.uk/ukpga/1996/18/section/230',
 '1996-08-22', NULL, false, now()),

-- ── Unpaid wages: series deductions ──────────────────────────────────────
('unlawful_deduction_wages.series_deductions_note', 'unpaid_wages', 'EW',
 NULL, 'time_runs_from_last_deduction_in_series', NULL,
 'For a series of deductions, time runs from the last deduction (s.23(3A)).',
 'case_law',
 'ERA 1996 s.23(3A); Bear Scotland Ltd v Fulton [2015] IRLR 15 (EAT)',
 'https://www.legislation.gov.uk/ukpga/1996/18/section/23',
 '2015-01-30', NULL, false, now()),

-- ── Unpaid wages: remedy ──────────────────────────────────────────────────
('unlawful_deduction_wages.remedy_basis', 'unpaid_wages', 'EW',
 NULL, 'repayment_gross_amount_unlawfully_deducted', NULL,
 'Remedy: ET orders repayment of gross amount unlawfully deducted (ERA 1996 s.24).',
 'case_law',
 'ERA 1996 s.24; Delaney v Staples [1992] 1 AC 687 (HL)  -  gross wages',
 'https://www.legislation.gov.uk/ukpga/1996/18/section/24',
 '1996-08-22', NULL, false, now())

ON CONFLICT (rule_key, jurisdiction, effective_from) DO NOTHING;

-- Set verification status: all current-law rules are verified from official sources
-- Prospective rules remain verification_required until they come into force
UPDATE rules SET verification_status = 'verified' WHERE is_prospective = false AND verification_status = 'verification_required';
