-- 058_employment_module_catalog.sql
-- Server/DB catalogue for the 24 UK employment-law modules LawApp must cover.
-- Status is honest release evidence: production means DB-backed rules/corpus,
-- workflow proof, and tests are present. Planned/partial modules must fail closed.

CREATE TABLE IF NOT EXISTS employment_modules (
    module_key          TEXT PRIMARY KEY,
    label               TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('production','partial','planned')),
    db_backed_required  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO employment_modules (module_key, label, status, db_backed_required) VALUES
('unfair_dismissal', 'Unfair dismissal', 'production', true),
('unpaid_wages', 'Unpaid wages / unlawful deduction', 'production', true),
('constructive_dismissal', 'Constructive dismissal', 'partial', true),
('wrongful_dismissal', 'Wrongful dismissal / notice pay', 'planned', true),
('redundancy', 'Redundancy rights and pay', 'planned', true),
('discrimination', 'Discrimination', 'planned', true),
('pregnancy_maternity_discrimination', 'Pregnancy and maternity discrimination', 'planned', true),
('equal_pay', 'Equal pay', 'planned', true),
('whistleblowing', 'Whistleblowing detriment/dismissal', 'planned', true),
('health_and_safety', 'Health and safety detriment/dismissal', 'planned', true),
('trade_union_rights', 'Trade union rights', 'planned', true),
('flexible_working', 'Flexible working', 'planned', true),
('maternity_rights', 'Maternity rights', 'planned', true),
('paternity_rights', 'Paternity rights', 'planned', true),
('parental_leave', 'Parental leave', 'planned', true),
('shared_parental_leave', 'Shared parental leave', 'planned', true),
('holiday_pay', 'Holiday pay and annual leave', 'planned', true),
('working_time', 'Working time and rest breaks', 'planned', true),
('national_minimum_wage', 'National Minimum Wage', 'planned', true),
('part_time_workers', 'Part-time worker rights', 'planned', true),
('fixed_term_workers', 'Fixed-term worker rights', 'planned', true),
('agency_workers', 'Agency worker rights', 'planned', true),
('tupe', 'TUPE transfers', 'planned', true),
('employment_contracts', 'Employment contracts / written particulars', 'planned', true)
ON CONFLICT (module_key) DO UPDATE SET
    label = EXCLUDED.label,
    status = EXCLUDED.status,
    db_backed_required = EXCLUDED.db_backed_required,
    updated_at = now();

CREATE OR REPLACE VIEW employment_module_readiness AS
SELECT
    m.module_key,
    m.label,
    m.status,
    m.db_backed_required,
    count(r.rule_key) FILTER (WHERE r.verification_status IN ('verified','case_law_verified')) AS verified_rule_count
FROM employment_modules m
LEFT JOIN rules r ON r.claim_type = m.module_key
GROUP BY m.module_key, m.label, m.status, m.db_backed_required
ORDER BY m.module_key;
