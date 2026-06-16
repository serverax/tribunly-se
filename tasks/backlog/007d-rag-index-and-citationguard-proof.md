# 007d  -  RAG Index and CitationGuard Proof

**Owner agents:** db-rag-ingestion-agent → ai-brain-citationguard-agent → qa-release-gatekeeper
**Stage:** 3–5 of legal-data chain · **State:** backlog · **Depends on:** 007c

## Goal
Prove the indexed corpus is retrievable and that the brain's CitationGuard enforces real corpus UUIDs end-to-end.

## Required proof
- **Index:** pgvector + BM25 index built over real `corpus_chunks`; index counts.
- **Retrieval:** a real query returns grounded chunks with parent source rows (show query + results).
- **CitationGuard PASS:** a brain answer citing a real `corpus_chunks` UUID validates.
- **CitationGuard FAIL-CLOSED:** a fabricated UUID is rejected / escalated (no fabricated authority passes).
- **Empty-grounding:** insufficient grounding → fail-closed, not invention.

## Full chain assertion (qa-release-gatekeeper)
Confirm the complete chain, no skipped stage:

`source URL → HTTP fetch proof → raw content hash → raw source record → parsed legal row → corpus_chunk → embedding/index → retrieval result → CitationGuard real UUID validation`

## Acceptance
Retrieval + CitationGuard PASS and FAIL proofs shown; chain unbroken. qa-release-gatekeeper issues ACCEPT/REJECT. Any skipped stage = REJECT.

## Hard rules
No model output accepted without a real corpus UUID validation. No fake retrieval. Fail-closed on empty grounding.
