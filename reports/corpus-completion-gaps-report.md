# Corpus Completion / Gaps Report

**Date:** 2026-06-05  **Domain:** employment_uk

Status vocabulary: DONE AND PROVEN · IMPLEMENTED BUT PARTIAL · NOT STARTED ·
PREPARED, INACTIVE · BLOCKED BY OWNER · FAILED AND NEEDS FIX.

> Headline: **UK employment legal corpus foundation is done and proven for
> legislation/rules/core guidance. Corpus depth expansion continues.** Not "complete".

## DONE AND PROVEN
- UK employment **legislation** corpus foundation (194 rows, 53 distinct sections,
  194/194 embedded, 194/194 hashed).
- **Domain-pack driven** ingestion (`domains/employment_uk/`, loaded by `domain_loader`).
- **legal_sources** registry + provenance columns across every legal row.
- **rules / citation / effective-date** proof (32 rules; caps tied to official UKSI).
- **Increase of Limits Orders** (UKSI) 2021–2026, effective-dated, cited, hashed source text.
- **Embeddings + RAG citation resolution** (citations resolve to real DB rows).
- **FCL fail-closed gate** (0 rows, BLOCKED BY OWNER).
- **Chunked, resumable, idempotent ingestion** + per-batch checkpoints; no duplicate rows.

## IMPLEMENTED BUT PARTIAL
- **ACAS standalone guidance breadth**  -  9 documents (Code + disciplinary, grievance,
  dismissal, notice, early conciliation, settlement, redundancy, unfair dismissal).
  Next: deeper sub-pages of multi-page ACAS guides (only first page captured per guide).
- **GOV.UK tribunal-procedure depth**  -  17 documents incl. employment-tribunals,
  redundancy, dismissal, grievance, whistleblowing. Next: ET1/ET3 procedural detail,
  current tribunal fees/procedure pages.

## NOT STARTED
- **Increase of Limits Orders pre-2021** (2019/2020 and earlier) for older backdated caps.
- **Deeper backdated cap history** beyond 2021 (week's-pay / comp-award / basic-award).
- **Full document-generation workflow** (intake exists; generation partial).
- **UK Parliament Bills API reform-watch ingestion** (table present, monitoring-only;
  not yet populated  -  by design, not legal authority).

## PREPARED, INACTIVE
- **Equality Act 2010**  -  declared in `sources.yaml` (`active:false`); ingest when the
  discrimination (Vento) workflow is activated.

## BLOCKED BY OWNER
- **Find Case Law bulk ingestion**  -  pending computational-analysis approval/licence.
  Pipeline/gate/schema prepared; `FCL_BULK_LICENCE_GRANTED=false`; 0 fake rows.

## FAILED AND NEEDS FIX
- None currently. (ACAS duplicate-row defect found via the chunked run was fixed by
  migration 030 + a unique constraint; proof now gates against duplicates.)

## Next corpus-depth priorities (in order)
1. Pre-2021 Increase of Limits Orders for older backdated claims.
2. ACAS multi-page guide depth (follow in-page sub-sections).
3. GOV.UK ET1/ET3 + tribunal procedure/fees pages.
4. UK Parliament Bills API reform-watch (monitoring only).
5. Equality Act 2010 activation (with discrimination workflow).
6. Keep FCL blocked until licence; keep all proof scripts green after each change.
