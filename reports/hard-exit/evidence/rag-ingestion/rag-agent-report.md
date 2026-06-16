# T-004  -  RAG Ingestion / Embedding & Retrieval Proof

**Agent:** db-rag-ingestion-agent
**Date:** 2026-06-07
**Target DB:** lawapp-rag / lawapp-postgres-0  -  db=`lawapp`, user=`lawapp_user` (in-cluster)
**Result:** `HARD EXIT RESULT: PASS`

---

## Summary

| Item | Value |
|------|-------|
| Chunks embedded this run | **798** (NULL → embedded) |
| Total corpus_chunks | 890 |
| with_embedding (after) | **890 / 890** (0 NULL) |
| Model | **BAAI/bge-small-en-v1.5** (stored `bge-small-en-v1.5`), fastembed 0.8.0 ONNX |
| Dimension | **384** (`vector(384)`, matches migration 016 + 92 existing rows) |
| Index | **HNSW** `vector_cosine_ops` (m=16, ef_construction=64), pgvector 0.8.2 |
| Placeholder/zero vectors | **0** |
| Chunk → legal_sources orphans | **0** |

Embeddings use the SAME model and dimension as the 92 pre-existing chunks  -  retrieval
is consistent across the whole corpus. All 798 new vectors are real (distinct,
L2-normalised, non-zero), produced from each chunk's `body_text`.

---

## Commands run (key)

1. Inspected schema/model:
   - `psql \d corpus_chunks` → `embedding vector(384)`
   - `select distinct embedding_model where embedding is not null` → `bge-small-en-v1.5`
   - Confirmed `ingestion/embeddings/embedder.py`: `EMBED_MODEL=BAAI/bge-small-en-v1.5`, `EMBED_DIM=384`, fastembed ONNX.
2. Embedding job: `reports/hard-exit/evidence/rag-ingestion/embed_local.py`
   - Run in `/tmp/lawapp-audit-venv` (fastembed 0.8.0 + psycopg2) against DB via
     `kubectl port-forward lawapp-postgres-0 15432:5432`.
   - `UPDATE corpus_chunks SET embedding=...::vector, embedding_model='bge-small-en-v1.5',
     embedding_created_at=now() WHERE id=%s AND embedding IS NULL`  -  ADDITIVE only.
   - Script refuses any all-zero vector (asserts dim==384, norm>1e-9).
3. Index: `CREATE INDEX corpus_chunks_embedding_hnsw_cos ON corpus_chunks USING hnsw
   (embedding vector_cosine_ops) WITH (m=16, ef_construction=64); ANALYZE corpus_chunks;`
4. Retrieval: `reports/hard-exit/evidence/rag-ingestion/retrieve.py`  -  query embedded
   with the same model, pgvector cosine NN (`<=>`), top-5, joined to `legal_sources`.

### Why not run inside a pod
First attempt inside `lawapp-ai/lawapp-brain` (which has fastembed + the model cached at
`/app/fastembed_cache` + DATABASE_URL→lawapp-rag) was **OOM-killed (exit 137)**: the pod
has a 1Gi memory limit and runs the live brain service; loading the ONNX model on top of
it exceeded the ceiling before the first batch committed (0 rows written  -  verified).
Falling back to the local audit venv (model cached on host, DB via port-forward) embedded
all 798 cleanly without touching the running service. No vectors were faked.

---

## Proof files

- `embedding-proof.txt`  -  before (92 embedded / 798 NULL) → after (890 / 0 NULL);
  model `bge-small-en-v1.5` dim 384 for all 890; **0** zero/placeholder vectors;
  vectors distinct (727 distinct cosine distances over 889 comparisons, range 0.12–0.90);
  798 rows have `embedding_created_at` 2026-06-07.
- `vector-index-proof.txt`  -  pgvector 0.8.2; HNSW index DDL; `\d corpus_chunks` showing
  the index; `EXPLAIN ANALYZE` confirms `Index Scan using corpus_chunks_embedding_hnsw_cos`
  (1.3ms exec).
- `retrieval-proof.txt`  -  2 real queries, top-5 each, with chunk_id, cosine distance,
  source_id, source_url, authority_ref, parent source name, chunk_hash, snippet.
- `source-id-return-proof.txt`  -  0 orphans / 0 null source_id / 0 missing url / 0 missing
  hash across 890 chunks; all 10 retrieved chunks mapped to real UK `legal_sources`
  (id 9 ERA 1996, id 10 Equality Act 2010, id 12 ACAS).

---

## Retrieval results (top hit per query)

**Q1 "unfair dismissal qualifying period"** → top hit cos_dist 0.1745 Equality Act 2010
s.129 (time limits); the canonical answer **ERA 1996 s.108** (2-year qualifying period)
returned at rank 2 (cos_dist 0.2070). Also ERA s.98, s.111, ACAS dismissals guidance.

**Q2 "employment tribunal time limit"** → top hits all ERA 1996 tribunal-complaint
sections; includes **ERA 1996 s.27BH "Complaints to employment tribunals: time limits"**
(cos_dist 0.1936). All from legislation.gov.uk.

Every retrieved chunk carries a real `source_id → legal_sources`, real `source_url`
(legislation.gov.uk / acas.org.uk), real `authority_ref`, and `chunk_hash`. No placeholders.

---

## Handoff to ai-brain-citationguard-agent

Real corpus UUID (grounded, embedded, source-linked):

```
corpus_chunk_id : 4f547231-b754-469e-b6d3-a303bee6ef0a
source_id       : 9  (legal_sources: Employment Rights Act 1996)
authority_ref   : Employment Rights Act 1996 s.108
source_url      : http://www.legislation.gov.uk/ukpga/1996/18/section/108
chunk_hash      : de5f5dfcec658b6b6acf342d71be94da85d774d5e3818a0f6eacd2794679bc1b
embedding_model : bge-small-en-v1.5  dim=384
```

This is the unfair-dismissal qualifying-period provision  -  ideal anchor for citation
validation.

---

## Honesty / blockers

- No chunks failed to embed. 798/798 embedded; 0 NULL remain.
- No egress was blocked: the bge model was cached locally; the model also revalidated
  files from HF without error. No OWNER-ACTION needed.
- Index is HNSW (not IVFFlat)  -  appropriate for 890 rows and confirmed used by the planner.
- ADDITIVE only: no DROP/TRUNCATE/DELETE; only `UPDATE ... WHERE embedding IS NULL`.

**Status: PASS**  -  embeddings real and consistent with existing corpus; pgvector HNSW
index built and used; retrieval returns chunk IDs + source IDs + source URLs from official
UK data (ERA 1996, Equality Act 2010, ACAS); no fake retrieval, no placeholder vectors.
