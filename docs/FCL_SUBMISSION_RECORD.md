# Find Case Law Computational Analysis Application — Submission Record

**Status:** Submitted — pending grant
**Submitted by:** serverax@gmail.com (account owner)
**Submission date:** 2026-05-31
**Application URL:** https://caselaw.nationalarchives.gov.uk/re-use-find-case-law-records/licence-application-process
**Contact email:** caselawlicence@nationalarchives.gov.uk
**Reference number:** [record when received from TNA]

---

## What was applied for

Computational analysis access to Employment Appeal Tribunal (EAT) and first-tier
Employment Tribunal (ET) decisions via the Find Case Law atom feed and data.xml
endpoints, for the purpose of populating and maintaining a vector index for
semantic retrieval in the UK employment law self-help co-pilot.

Per-document fetches of individual decisions under the Open Justice Licence are
permitted and continue without restriction.

---

## What is blocked until grant is received

- Bulk atom-feed pagination of EAT/ET decisions
- Programmatic bulk extraction of decision text at corpus scale
- Corpus-level embedding of case law text
- Any systematic automated analysis across multiple decisions

All of the above are controlled by the `FCL_BULK_LICENCE_GRANTED` environment
variable, which is set to `false` in `.env` and defaults to `false` in
`docker-compose.yml`. The ingestion code raises a hard error if bulk operations
are attempted without this flag set to `true`.

Do not set `FCL_BULK_LICENCE_GRANTED=true` until a written grant confirmation
is received from TNA (caselawlicence@nationalarchives.gov.uk).

---

## Current case law corpus

5 EAT decisions ingested per-document under the Open Justice Licence:
- eat/2026/74 — DHL Services Limited v Pawel Ignatowicz
- eat/2026/75 — E Komeng v National Highways Limited
- eat/2026/76 — Noel Deans v RBL Law Ltd (in liquidation) & Ors
- eat/2026/77 — London Ambulance Service NHS Trust v Ricky Garrett
- eat/2026/78 — H Rogers v Secretary of State for Justice

Stable identifiers (d-{uuid}) stored as document_uri.
Fetch paths (eat/year/num) stored as fetch_url.
367 chunks across 5 decisions (case_law_chunks table).

---

## Phase 1 status

**Phase 1: PASS pending FCL grant.**

All Phase 1 technical acceptance criteria are met. The FCL application
submission satisfies the build plan's requirement that it be submitted
before bulk ingestion begins. Bulk ingestion remains blocked until the
grant is received.

---

## After grant received

1. Record the grant date and any reference number in this file.
2. Set `FCL_BULK_LICENCE_GRANTED=true` in `.env`.
3. Run initial bulk ingestion:
   `docker compose run --rm ingestion python -m ingestion.case_law.ingest --bulk --max-pages 5`
4. Validate the first 5 pages before continuing to full corpus.
5. Update this file with ingestion stats.

---

## Open items (FCL-independent)

- ET first-tier court code: not yet confirmed from live atom feed (flagged).
  Confirm before building ET-specific queries.
- d-{uuid}/data.xml fetch path: 404 in testing despite API docs saying it should
  work. Flagged to FCL team. Confirm correct programmatic fetch endpoint before
  building change-detection refresh job.
