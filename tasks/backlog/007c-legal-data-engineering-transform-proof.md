# 007c — Legal Data Engineering Transform Proof

**Owner agent:** legal-data-engineer-agent
**Stage:** 2 of legal-data chain · **State:** backlog · **Depends on:** 007b (raw manifest)

## Goal
Transform validated raw input into structured, effective-dated, fully-cited lawapp data and PROVE quality. No web scraping.

## Required proof
1. Raw input manifest used.
2. Parser used (CLML / Akoma Ntoso / ACAS text).
3. DB row count before.
4. DB row count after.
5. Sample inserted row.
6. `source_url` present.
7. `authority_ref` present.
8. `jurisdiction` present.
9. `effective_from`/`effective_to` where applicable.
10. `last_verified_at` present.
11. `content_hash` present where relevant.
12. `corpus_chunks` count.
13. Embedding count.
14. One retrieval query proof.
15. One CitationGuard real-UUID proof.

## Deliverables
- `legislation` / `acas_guidance` / `case_law` rows (case_law licence-gated).
- `corpus_chunks` (each with parent legal source row).
- pgvector embeddings.
- Effective-dated `rules` rows (all 5 required fields).
- `source_freshness` report.

## Acceptance
All 15 proofs present; no rules row missing required fields; no orphan corpus_chunk. Hands to 007d.

## Hard rules
No fake DB rows, no mock legal rows as proof, no invented authority_ref, no hardcoded legal values in app code.
