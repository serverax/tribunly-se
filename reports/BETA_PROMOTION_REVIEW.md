# Beta Promotion Review

Generated: 2026-06-18T02:02:21+01:00  
Repo: serverax/lawapp  
Branch: `release/lawapp-clean-snapshot`  
Code HEAD: `4209216`  
Evidence report: `reports/rag_1024_retrieval_repair.txt` (refreshed 2026-06-18)

---

## Beta readiness

### **PASS** (subject only to owner promotion decision)

All RAG 1024-dim verification checks passed on the live local Docker stack. No code defects block beta promotion on the release line.

---

## What is now proven

| Area | Evidence | Status |
|------|----------|--------|
| Corpus embeddings | 978/978 @ 1024-dim, `bge-large-en-v1.5` | **PASS** |
| Retrieval plane | `corpus_chunks` canonical; semantic leg not gated on `legislation.embedding` | **PASS** |
| Query embeddings | 1024-dim; dimension mismatch fails closed | **PASS** |
| RAG microservice | `/api/rag/search` — 4/4 queries, 5 cited hits each | **PASS** |
| Targeted tests | 27 pytest passed (repair + ADR-000 + semantic integration) | **PASS** |
| ADR-000 / single brain | No `backend/ai`, no LangGraph runtime, no `/api/v1/legal/reason` | **PASS** |
| Gate D (ingestion 084) | Historical PASS @ `verify_ingestion_084.py`; corpus counts re-confirmed | **PASS** |
| Case OS beta | Historical PASS (`reports/case_os_beta_ship_cursor.txt`) | **PASS** |
| Grounding / CitationGuard | Historical PASS (unified bundle) | **PASS** |

Full checklist: see `reports/rag_1024_retrieval_repair.txt`.

---

## What remains not started / blocked

| Item | Status | Notes |
|------|--------|-------|
| SEO Track B | **Not approved** | Owner decision required before any Track B work |
| LangGraph / second runtime | **Blocked** | ADR-000 binding; `backend/ai` absent by design |
| Agent / subagent automation | **Stopped** | See `docs/handoff/AGENTS_AND_SUBAGENTS_STATE.md` |
| SEO Track A proof on release | **Not on branch** | `reports/seo_track_a_proof.txt` on `feat/seo-command` only |
| Kubernetes production deploy | **Unverified** | kubectl unreachable from this workstation (historical) |
| Source table 1024 migration | **Deferred** | `legislation`/`acas_guidance` still vector(384); non-blocking while corpus_chunks is canonical |

---

## Risks and caveats

1. **Operator env:** Host scripts must use `POSTGRES_PASSWORD=lawapp` or `DATABASE_URL=postgresql://lawapp:lawapp@localhost:5435/lawapp` — `.env` default `change_this_password` drifts from Docker volume password.
2. **Ollama dependency:** RAG vector leg requires Ollama with `bge-large-en-v1.5` (or aliased model) at `LAWAPP_OLLAMA_BASE_URL`.
3. **Source-table embeddings:** Empty 384-dim `legislation.embedding` is expected; do not repoint ingestion embedder to source tables without a migration plan.
4. **Remote cluster:** Production pod health not verified in this pass; local Docker proof only.
5. **SEO scope:** Beta legal product is ready; SEO command tracks are separate and not part of this promotion gate.

---

## Promotion recommendation

**Recommend owner approve beta promotion** on `release/lawapp-clean-snapshot` at code `4209216` (or later docs-only commits on the same line).

Conditions:
- Promotion is a release/process decision, not a further engineering gate on RAG 1024.
- Do not enable SEO Track B, LangGraph, or background agents without explicit owner approval.
- Re-run `reports/rag_1024_retrieval_repair.txt` checklist after any RAG/embedding code change.

---

## Evidence files

| File | Purpose |
|------|---------|
| `reports/rag_1024_retrieval_repair.txt` | RAG 1024 verification (this pass) |
| `reports/beta_gate_evidence_unified.txt` | Historical gate bundle |
| `reports/ingestion_084_cursor.txt` | Gate D historical |
| `reports/seo_track_a_proof.txt` | feat/seo-command only |
| `docs/handoff/PROOF_INDEX.md` | Index of all proof artifacts |
