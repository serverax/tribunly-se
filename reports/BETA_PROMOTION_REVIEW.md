# Beta Promotion Review

Generated: 2026-06-18T15:45:00Z  
Repo: serverax/lawapp  
Branch: `release/lawapp-clean-snapshot`  
Code HEAD: pending (`fix: repair beta diagnosis and JWT readiness gates`)  
Prior HEAD: `97aeae4`  
Evidence report: `reports/rag_1024_retrieval_repair.txt` (refreshed 2026-06-18)

---

## Beta readiness

### **PASS** (conditional — owner promotion decision)

All targeted beta gate tests pass on fixed code. RAG 1024-dim verification remains green. Diagnosis alias and JWT readiness gates repaired.

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
| Diagnosis alias | `POST /api/diagnosis` matches `/assess` shape | **PASS** |
| JWT readiness | `tests/integration/test_phase6c_jwt.py` 34/34 | **PASS** |
| Payment gating | `tests/security/test_payment_access.py` 16/16 | **PASS** |
| Gate D (ingestion 084) | Historical PASS @ `verify_ingestion_084.py`; corpus counts re-confirmed | **PASS** |
| Case OS beta | Historical PASS (`reports/case_os_beta_ship_cursor.txt`) | **PASS** |
| Grounding / CitationGuard | Historical PASS (unified bundle) | **PASS** |

Full checklist: see `reports/rag_1024_retrieval_repair.txt`.

---

## Fixes applied (this pass)

| Gate | Root cause | Fix |
|------|------------|-----|
| Diagnosis alias `domain_unavailable` | `diagnosis_endpoint` called `assess_endpoint()` directly; FastAPI `Header()` default object became `domain_code` | Pass `x_lawapp_domain` from request header into `assess_endpoint` |
| JWT admin routes 404 | Static `/admin/{page_name}` catch-all matched `/admin/production-readiness` before JSON API routes | Restrict static admin route to `/admin/{page_name}.html` |

---

## What remains not started / blocked

| Item | Status | Notes |
|------|--------|-------|
| `controlled_beta_ready` | **False by design** | DPIA/privacy not reviewed in `docs/compliance-signoff.json` |
| `production_ready` | **False by design** | HS256-only auth not production-grade (Phase 7A) |
| SEO Track B | **Not approved** | Owner decision required before any Track B work |
| LangGraph / second runtime | **Blocked** | ADR-000 binding; `backend/ai` absent by design |
| Agent / subagent automation | **Stopped** | See `docs/handoff/AGENTS_AND_SUBAGENTS_STATE.md` |
| SEO Track A proof on release | **Not on branch** | `reports/seo_track_a_proof.txt` on `feat/seo-command` only |
| Kubernetes production deploy | **Unverified** | kubectl unreachable from this workstation (historical) |
| Live Docker API smoke | **Pending redeploy** | Running pre-fix image; pytest uses local code |

---

## Risks and caveats

1. **Docker image lag:** Rebuild/restart backend container for live `/assess` and `/api/diagnosis` smoke to match pytest.
2. **Operator env:** Host scripts must use `POSTGRES_PASSWORD=lawapp` or `DATABASE_URL=postgresql://lawapp:lawapp@localhost:5435/lawapp`.
3. **Ollama dependency:** RAG vector leg requires Ollama with `bge-large-en-v1.5` at `LAWAPP_OLLAMA_BASE_URL`.
4. **DPIA gate:** `controlled_beta_ready=false` is honest compliance state, not a test failure.
5. **SEO scope:** Beta legal product gates are green; SEO command tracks are separate.

---

## Promotion recommendation

**Recommend owner approve conditional beta promotion** on `release/lawapp-clean-snapshot` after this fix commit.

Conditions:
- Rebuild Docker backend image before claiming live API parity with pytest.
- `controlled_beta_ready` stays false until DPIA/privacy sign-off (expected).
- Do not enable SEO Track B, LangGraph, or background agents without explicit owner approval.
- Re-run `reports/rag_1024_retrieval_repair.txt` checklist after any RAG/embedding code change.

---

## Evidence files

| File | Purpose |
|------|---------|
| `reports/rag_1024_retrieval_repair.txt` | RAG 1024 verification |
| `reports/TECHNOLOGY_WORKFLOW_VERIFICATION.md` | Full matrix (this pass) |
| `reports/beta_gate_evidence_unified.txt` | Historical gate bundle |
| `reports/ingestion_084_cursor.txt` | Gate D historical |
| `reports/seo_track_a_proof.txt` | feat/seo-command only |
| `docs/handoff/PROOF_INDEX.md` | Index of all proof artifacts |
