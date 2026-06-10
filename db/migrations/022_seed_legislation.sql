-- Migration 022 — Seed Minimum Viable Legislation Corpus (ERA 1996)
-- Ensures a deterministic baseline for reasoning without requiring external ingestion.

-- Remove potential existing seed data to allow re-run
DELETE FROM legislation WHERE act_title IN ('Employment Rights Act 1996', 'Employment Tribunals Act 1996');

INSERT INTO legislation (
    act_title, leg_type, year, section_ref, jurisdiction, 
    body_text, source_url, 
    effective_from, last_verified_at
) VALUES 
(
    'Employment Rights Act 1996', 'primary', 1996, '94', 'EW',
    'An employee has the right not to be unfairly dismissed by his employer.',
    'https://www.legislation.gov.uk/ukpga/1996/18/section/94',
    '1996-08-22', now()
),
(
    'Employment Rights Act 1996', 'primary', 1996, '95', 'EW',
    'For the purposes of this Part an employee is dismissed by his employer if (a) the contract under which he is employed is terminated by the employer (whether with or without notice), (b) a limited-term contract expires without being renewed, or (c) the employee terminates the contract under which he is employed (with or without notice) in circumstances in which he is entitled to terminate it without notice by reason of the employer’s conduct.',
    'https://www.legislation.gov.uk/ukpga/1996/18/section/95',
    '1996-08-22', now()
),
(
    'Employment Rights Act 1996', 'primary', 1996, '98', 'EW',
    'In determining for the purposes of this Part whether the dismissal of an employee is fair or unfair, it is for the employer to show (a) the reason (or, if more than one, the principal reason) for the dismissal, and (b) that it is either a reason falling within subsection (2) or some other substantial reason of a kind such as to justify the dismissal of an employee holding the position which the employee held. The reasons in subsection (2) are: capability, conduct, redundancy, or statutory restriction.',
    'https://www.legislation.gov.uk/ukpga/1996/18/section/98',
    '1996-08-22', now()
),
(
    'Employment Rights Act 1996', 'primary', 1996, '108', 'EW',
    'Section 94 does not apply to the dismissal of an employee unless he has been continuously employed for a period of not less than two years ending with the effective date of termination.',
    'https://www.legislation.gov.uk/ukpga/1996/18/section/108',
    '2012-04-06', now()
),
(
    'Employment Rights Act 1996', 'primary', 1996, '111', 'EW',
    'An employment tribunal shall not consider a complaint under this section unless it is presented to the tribunal before the end of the period of three months beginning with the effective date of termination, or within such further period as the tribunal considers reasonable in a case where it is satisfied that it was not reasonably practicable for the complaint to be presented before the end of that period of three months.',
    'https://www.legislation.gov.uk/ukpga/1996/18/section/111',
    '1996-08-22', now()
),
(
    'Employment Rights Act 1996', 'primary', 1996, '124', 'EW',
    'Section 124 sets out the calculation and statutory cap for the compensatory award in unfair dismissal claims.',
    'https://www.legislation.gov.uk/ukpga/1996/18/section/124',
    '1996-08-22', now()
),
(
    'Employment Rights Act 1996', 'primary', 1996, '227', 'EW',
    'Section 227 defines the statutory limit on a week''s pay used in employment tribunal award calculations.',
    'https://www.legislation.gov.uk/ukpga/1996/18/section/227',
    '1996-08-22', now()
),
(
    'Employment Rights Act 1996', 'primary', 1996, '13', 'EW',
    'A worker has the right not to suffer unauthorised deductions from wages. This section is the core unlawful deduction from wages protection.',
    'https://www.legislation.gov.uk/ukpga/1996/18/section/13',
    '1996-08-22', now()
),
(
    'Employment Rights Act 1996', 'primary', 1996, '23', 'EW',
    'A worker may present a complaint to an employment tribunal that an employer has made an unauthorised deduction from wages.',
    'https://www.legislation.gov.uk/ukpga/1996/18/section/23',
    '1996-08-22', now()
),
(
    'Employment Rights Act 1996', 'primary', 1996, '24', 'EW',
    'Where an unlawful deduction complaint is well founded, the employment tribunal may make a declaration and order repayment of the amount deducted.',
    'https://www.legislation.gov.uk/ukpga/1996/18/section/24',
    '1996-08-22', now()
),
(
    'Employment Tribunals Act 1996', 'primary', 1996, '18A', 'EW',
    'Before a person institutes relevant proceedings, the person must send relevant information to ACAS in the prescribed manner.',
    'https://www.legislation.gov.uk/ukpga/1996/17/section/18A',
    '2014-04-06', now()
);
