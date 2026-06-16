-- Migration 011: Phase 5C  -  rules verification status columns
-- Adds verification_status and verification_notes to the rules table.
-- verification_status values:
--   verified            -  confirmed against primary statutory source (legislation.gov.uk)
--   case_law_verified   -  confirmed against case law authority (EAT/Court decision)
--   prospective         -  not yet in force; is_prospective=true rows always use this
--   verification_required  -  not yet verified against primary source
--   failed              -  verification failed; statutory text does not match claimed rule

ALTER TABLE rules ADD COLUMN IF NOT EXISTS verification_status text DEFAULT 'verification_required';
ALTER TABLE rules ADD COLUMN IF NOT EXISTS verification_notes  text;

-- Retrospectively mark all prospective rules
UPDATE rules SET verification_status = 'prospective'
WHERE is_prospective = true AND verification_status = 'verification_required';

CREATE INDEX IF NOT EXISTS rules_verification_idx ON rules (verification_status, is_prospective);
