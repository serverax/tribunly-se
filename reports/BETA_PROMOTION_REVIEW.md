# Beta Promotion Review

Generated: 2026-06-17  
Repo: serverax/lawapp  
Branch: `release/lawapp-clean-snapshot`  
Evidence run base: `1e10075` (pre-commit; see commit SHA below after push)

---

## Gate status (reference: `reports/beta_gate_evidence_unified.txt`)

| Gate | Description | Status | Notes |
|------|-------------|--------|-------|
| C | Case OS beta audit | **PASS** | `reports/case_os_beta_ship_cursor.txt` |
| D | Ingestion 084 dual-plane | **PASS** (live re-verified) | `verify_ingestion_084.py` exit 0; embedded=978 dim=1024 |
| E | Grounding / CitationGuard | **PASS** | Unified bundle |
| F | i18n + domain fail-closed | **PASS** | Unified bundle |
| SB | Single Brain ADR-000 | **PASS** | 16 pytest passed; no `backend/ai` |

---

## Embed hardening results

| Check | Result |
|-------|--------|
| corpus_chunks count | 978 |
| embedded rows | 978 / 978 |
| legislation-path embedded (primary + secondary + SI) | 885 |
| dimension sample | **1024 only** (978 rows) |
| model | bge-large-en-v1.5 |
| sync_corpus_chunks idempotent | added=0 |
| re-embed duration | ~155 min (972 chunks, Ollama local) |

**Partial gaps:**
- Source `legislation` table still `vector(384)`, 0 embeddings — `retrieve_semantic` uses BM25 fallback
- RAG service `/api/rag/search` returns 0 hits — query embedder still 384-dim fastembed vs 1024 corpus

---

## ADR-000 clean

| Check | Result |
|-------|--------|
| `tests/test_single_brain_architecture.py` + `tests/test_build_order_gates.py` | **16 passed** |
| `backend/ai/` present | **NO** |
| LangGraph / legal/reason in backend | **0 grep hits** |

---

## Beta ready recommendation

### **NO** (conditional — corpus embed proven; retrieval stack not fully aligned)

**Evidence for YES (corpus plane):**
- All 978 `corpus_chunks` carry 1024-dim `bge-large-en-v1.5` embeddings
- Direct pgvector retrieval against corpus returns ranked 1024-dim hits
- `retrieve_hybrid` returns grounded authorities (score 1.0) on test query
- ADR-000 enforcement green

**Evidence blocking YES:**
- Brain `retrieve_semantic` gates on `legislation.embedding` (still empty / 384 schema) — semantic leg not using new corpus embeddings
- RAG microservice vector search dimension mismatch (384 query vs 1024 index) — live `/api/rag/search` empty
- Host `.env` password drift (`change_this_password` vs volume `lawapp`) — documented, requires operator alignment

---

## Owner actions remaining

1. **DB password:** Set local `.env` `POSTGRES_PASSWORD=lawapp` or use `DATABASE_URL=postgresql://lawapp:lawapp@localhost:5435/lawapp` for all host proof scripts.
2. **Source table migration:** Apply 1024-dim to `legislation` / `acas_guidance` OR repoint `backend/core/retrieve.py` semantic leg to `corpus_chunks`.
3. **RAG service:** Switch `_vector_search` query embedding to Ollama `bge-large-en-v1.5` (1024) — remove fastembed 384 path for prod.
4. **Ollama prod alias:** Document `ollama cp mxbai-embed-large bge-large-en-v1.5` in deploy runbook when direct pull fails.
5. **Re-run Gate D proof** after RAG retrieve fix: `verify_ingestion_084.py` + hybrid search integration test.

---

## Commit / push

See git log after commit on `release/lawapp-clean-snapshot` (never `main`).
