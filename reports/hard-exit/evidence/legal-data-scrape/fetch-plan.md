# SA-001 Fetch Plan  -  RAW UK Employment-Law Sources

Scope: acquisition only. Fetch raw official source bytes to disk. No parsing into rules,
no corpus_chunks, no embeddings, no DB rows. Record real HTTP status + sha256 for every fetch.

Method: `curl -sS -L` (follow redirects), custom UA `lawapp-legal-scraper/1.0`, body written to
`raw/<slug>.<ext>`, `-w '%{http_code}|%{size_download}|%{url_effective}'` to capture real status,
byte count, and effective URL. `sleep 2` between requests (polite rate-limit). HTTP status is taken
from curl `%{http_code}` and never fabricated.

| # | slug | URL | type | jurisdiction | why this source |
|---|------|-----|------|--------------|-----------------|
| 1 | era-1996 | https://www.legislation.gov.uk/ukpga/1996/18/data.xml | legislation (CLML/XML) | UK | Core statute for unfair dismissal, written statement, notice, redundancy entitlement, working time interactions. Data/XML form preferred (machine-parsable, point-in-time versioned). |
| 2 | equality-act-2010 | https://www.legislation.gov.uk/ukpga/2010/15/data.xml | legislation (CLML/XML) | UK | Discrimination / protected characteristics / harassment / victimisation in employment. |
| 3 | eta-1996 | https://www.legislation.gov.uk/ukpga/1996/17/data.xml | legislation (CLML/XML) | UK | Constitution/procedure of Employment Tribunals and the EAT; underpins claim procedure. |
| 4 | acas-dismissals | https://www.acas.org.uk/dismissals | acas_guidance (HTML) | EW | Authoritative procedural guidance on dismissal types and fairness. |
| 5 | acas-disciplinary-grievance | https://www.acas.org.uk/disciplinary-and-grievance-procedures | acas_guidance (HTML) | EW | ACAS Code of Practice hub for discipline & grievance (procedural fairness). Redirects to /discipline-and-grievance. |
| 6 | govuk-et-make-a-claim | https://www.gov.uk/employment-tribunals/make-a-claim | govuk_guidance (HTML) | EW | Tribunal claim route, time limits, early conciliation entry point. |
| 7 | acas-early-conciliation | https://www.acas.org.uk/early-conciliation | acas_guidance (HTML) | EW | Mandatory early conciliation step before tribunal claim. |
| 8 | govuk-redundancy | https://www.gov.uk/redundancy-your-rights | govuk_guidance (HTML) | EW | Redundancy rights, statutory redundancy pay, notice, consultation. |
| 9 | govuk-holiday-entitlement | https://www.gov.uk/holiday-entitlement-rights | govuk_guidance (HTML) | EW | Holiday entitlement / holiday pay / wages. |

Find Case Law (caselaw.nationalarchives.gov.uk) bulk/computational scrape: NOT performed.
No licence/application on record; out of scope for SA-001.

Licence notes:
- legislation.gov.uk and GOV.UK: Open Government Licence v3.0 (Crown copyright); XML/API + single-page fetch permitted.
- ACAS: Crown copyright / OGL where applicable; single-page fetch only, no bulk computational scrape.
