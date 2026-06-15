-- Ensure promoted redundancy workflow rules participate in GB source-freshness
-- reporting instead of appearing under a blank jurisdiction_code bucket.

UPDATE rules
SET jurisdiction_code = 'GB',
    country_code = 'GB',
    legal_system = 'GB',
    applies_to_england_wales = true,
    applies_to_scotland = true,
    applies_to_gb = true
WHERE rule_key IN (
  'redundancy.weeks_pay_cap_amount',
  'redundancy.max_years_counted',
  'redundancy.multiplier_under_22',
  'redundancy.multiplier_22_to_40',
  'redundancy.multiplier_41_plus'
)
AND jurisdiction = 'GB';
