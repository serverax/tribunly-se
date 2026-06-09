-- 036_verification_status_canonical.sql
-- Correction: an earlier migration (034) used a non-canonical 'verified_live'
-- status. The canonical production vocabulary is verified / case_law_verified /
-- prospective / unverified (see backend/api/main.py verification gate). This
-- migration maps any 'verified_live' back to canonical 'verified'. Idempotent.
UPDATE rules SET verification_status = 'verified' WHERE verification_status = 'verified_live';
