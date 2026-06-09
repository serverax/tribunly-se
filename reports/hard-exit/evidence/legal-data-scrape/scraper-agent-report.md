# SA-001 Scraper Agent Report — RAW UK Employment-Law Source Acquisition

Agent: uk-employment-law-scraper-agent (acquisition layer only)
Date (UTC): 2026-06-07
Working dir: /mnt/f/lawapp
Evidence dir: reports/hard-exit/evidence/legal-data-scrape/

## Result

HARD EXIT RESULT: PASS

All 9 requested official sources were fetched, returned a real HTTP status, were stored to disk
as raw bytes, and have a recorded byte count + sha256 content hash + manifest entry. No derived
legal data was created.

## What was fetched (real curl HTTP status)

| slug | source_type | HTTP | bytes | sha256 (prefix) | retrieved_at (UTC) |
|------|-------------|------|-------|------------------|--------------------|
| era-1996 | legislation | 200 | 5737381 | 7b977b24 | 2026-06-07T14:44:08Z |
| equality-act-2010 | legislation | 200 | 3556271 | cc1bceab | 2026-06-07T14:44:15Z |
| eta-1996 | legislation | 200 | 1424629 | d0816d9b | 2026-06-07T14:44:21Z |
| acas-dismissals | acas_guidance | 200 | 70008 | 2a0a9511 | 2026-06-07T14:44:24Z |
| acas-disciplinary-grievance | acas_guidance | 200 | 72646 | 6f7787a5 | 2026-06-07T14:44:27Z |
| govuk-et-make-a-claim | govuk_guidance | 200 | 79303 | b0bae507 | 2026-06-07T14:44:29Z |
| acas-early-conciliation | acas_guidance | 200 | 68088 | 8349f87e | 2026-06-07T14:44:32Z |
| govuk-redundancy | govuk_guidance | 200 | 94770 | 5db263df | 2026-06-07T14:44:34Z |
| govuk-holiday-entitlement | govuk_guidance | 200 | 97623 | d8bebf18 | 2026-06-07T14:44:36Z |

## Content authenticity checks (not parsing — sanity only)

- All 3 legislation files are genuine CLML: root `<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation" ...>` with DocumentURI, NumberOfProvisions, RestrictStartDate. NOT error pages.
  - era-1996: NumberOfProvisions=528, version (RestrictStartDate)=2026-04-06, extent E+W+S+N.I.
  - equality-act-2010: NumberOfProvisions=565, version=2026-04-07.
  - eta-1996: NumberOfProvisions=134, version=2026-04-07.
- ACAS/GOV.UK files are genuine HTML documents (verified via `file` and `<title>`/og:title), not blocked/empty pages.

## Failures / anomalies (honest record)

- No fetch failed. All 9 returned HTTP 200.
- `acas-disciplinary-grievance`: requested URL https://www.acas.org.uk/disciplinary-and-grievance-procedures
  301/302-redirected to canonical https://www.acas.org.uk/discipline-and-grievance (followed with `-L`,
  effective_url recorded in manifest and fetch-log.txt). Content is the correct ACAS Discipline & grievance hub.
- No alternative-URL fallback was needed because no source 404'd.

## Explicit scope confirmation

- NO rules table rows created.
- NO corpus_chunks created.
- NO embeddings or vector index entries created.
- NO database rows of any kind created.
- NO parsing of statute/guidance into structured legal data.
- NO invented citations, no fabricated content, no fabricated hashes — every hash was computed
  with `sha256sum` directly from the bytes on disk.
- NO Find Case Law bulk/computational scrape (no licence on record; out of scope).

## Licence / access

- legislation.gov.uk + GOV.UK: Open Government Licence v3.0 (Crown copyright).
- ACAS: Crown copyright / OGL where applicable; single-page fetch only, no bulk scrape performed.

## Evidence files (absolute paths)

- /mnt/f/lawapp/reports/hard-exit/evidence/legal-data-scrape/fetch-plan.md
- /mnt/f/lawapp/reports/hard-exit/evidence/legal-data-scrape/raw-source-manifest.json
- /mnt/f/lawapp/reports/hard-exit/evidence/legal-data-scrape/raw-source-records-proof.txt
- /mnt/f/lawapp/reports/hard-exit/evidence/legal-data-scrape/hash-proof.txt
- /mnt/f/lawapp/reports/hard-exit/evidence/legal-data-scrape/fetch-log.txt
- /mnt/f/lawapp/reports/hard-exit/evidence/legal-data-scrape/raw/ (9 raw files)

## Handoff

Hand source manifest + raw files + hashes to legal-data-engineer-agent for parsing into legal rows.
Acceptance is NOT granted here; it belongs to qa-release-gatekeeper after the full chain passes:
source URL -> HTTP fetch proof -> raw content hash -> raw source record -> parsed legal row ->
corpus_chunk -> embedding/index -> retrieval result -> CitationGuard real UUID validation.
