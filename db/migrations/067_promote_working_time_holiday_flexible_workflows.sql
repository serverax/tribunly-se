-- Promote narrow diagnosis workflows whose legal thresholds are already
-- represented by verified DB-backed rules. These are diagnosis scope only;
-- broader document/remedy matrices remain separate release gates.

UPDATE employment_modules
SET status = 'production',
    updated_at = NOW()
WHERE module_key IN ('working_time', 'holiday_pay', 'flexible_working');
