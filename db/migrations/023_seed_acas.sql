-- Migration 023 — Seed Minimum Viable ACAS Guidance
-- Ensures a deterministic baseline for reasoning.

-- Remove potential existing seed data to allow re-run
DELETE FROM acas_guidance WHERE doc_title IN ('ACAS Code of Practice on disciplinary and grievance procedures', 'ACAS Guidance: Dismissals');

INSERT INTO acas_guidance (
    doc_title, section_ref, 
    body_text, source_url, 
    last_verified_at
) VALUES 
(
    'ACAS Code of Practice on disciplinary and grievance procedures',
    'Introduction',
    'The ACAS Code of Practice on disciplinary and grievance procedures provides practical guidance to employers, employees and their representatives and sets out principles for handling disciplinary and grievance situations in the workplace.',
    'https://www.acas.org.uk/code-of-practice-on-disciplinary-and-grievance-procedures',
    now()
),
(
    'ACAS Guidance: Dismissals',
    'Standard Procedure',
    'Employers should follow a fair procedure before dismissing an employee. This includes investigation, notification of the problem, and a hearing where the employee can present their case.',
    'https://www.acas.org.uk/dismissals',
    now()
);
