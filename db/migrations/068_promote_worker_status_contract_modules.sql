-- Promote additional narrow diagnosis workflows that are fully DB-rule anchored.
-- Scope is limited to diagnosis; document/remedy matrices remain separate gates.

UPDATE employment_modules
SET status = 'production',
    updated_at = NOW()
WHERE module_key IN (
  'employment_contracts',
  'fixed_term_workers',
  'part_time_workers',
  'agency_workers'
);
