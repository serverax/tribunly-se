# 007a — UK Employment-Law Source Fetch Plan

**Owner agent:** uk-employment-law-scraper-agent
**Stage:** 1 of legal-data chain · **State:** backlog · **Type:** plan (no fetch yet)

## Goal
Produce a documented plan for fetching real UK employment-law sources — no transformation, no DB rows.

## Deliverables
- Target source inventory: legislation.gov.uk (ERA 1996 + relevant SIs, CLML/XML endpoints), ACAS guidance pages/docs, Find Case Law sample/single docs.
- Per-source: URL pattern, format (CLML/XML, Akoma Ntoso, HTML/text), rate-limit rule, licence/access note.
- Find Case Law licence/application status documented (bulk vs single/sample permitted).
- Raw storage layout: file paths + `raw_source_records` schema (`source_url`, `source_type`, `http_status`, `content_length`, `content_hash`, `fetched_at`, `licence_note`).
- Fetch script design (command shape), not yet executed.

## Acceptance
Plan reviewed; no fetch executed; licence posture explicit. Hands to 007b.

## Hard rules
No fake sources, no invented citations, no DB writes, no corpus_chunks. Fetch success ≠ ingestion complete.
