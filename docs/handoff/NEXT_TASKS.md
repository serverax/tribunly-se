
# Next tasks (snapshot)

## Immediate priority: verify RAG 1024 repair (not fresh repair)

RAG 1024-dim repair appears shipped at `4209216`; verification should be re-run before beta promotion.

### Required proof checklist

1. **Query embedding dimension is 1024** — Ollama `bge-large-en-v1.5` via `ollama_embed.py`; no 384-dim fallback.
2. **Retrieval uses `corpus_chunks`** — `retrieve_semantic` gates on `corpus_chunks.embedding`, not `legislation.embedding`.
3. **`/api/rag/search` returns non-zero cited results** for:
   - unfair dismissal time limit
   - compensatory award cap
   - qualifying period
   - ACAS early conciliation
4. **ADR-000 tests still pass** — `tests/test_single_brain_architecture.py`, `tests/test_build_order_gates.py`.
5. **Forbidden path grep still clean:**
   - no LangGraph active runtime (`rg langgraph backend/` → 0 matches)
   - no `/api/v1/legal/reason`
   - no `backend/ai/`
   - no second legal orchestration path

### Verification commands (when owner authorises)

```powershell
$env:DATABASE_URL="postgresql://lawapp:lawapp@localhost:5435/lawapp"
$env:POSTGRES_PASSWORD="lawapp"
python -m pytest tests/test_rag_1024_retrieval_repair.py tests/test_single_brain_architecture.py tests/test_build_order_gates.py -q
python scripts/proof/verify_ingestion_084.py
# curl POST http://localhost:8017/api/rag/search for each query above; capture to reports/
```

## Other priorities (after verification)

1. Reconnect kubectl/VPN and verify AKS namespaces (lawapp-api, lawapp-rag, lawapp-ai, lawapp-security, lawapp-monitoring) and pod health.
2. Refresh beta gate evidence and `reports/BETA_PROMOTION_REVIEW.md` after verification PASS.
3. SEO Track B only when owner lifts STOP; use `docs/08_SEO_COMMAND_HANDOFF.md` as command boundary.
4. Clear or gitignore `_wt_feat/` if not intentional workspace artifact.

## Blocking issues

- No cluster API from this workstation.
- Beta promotion review not refreshed after `4209216` verification re-run.

## Required before next phase

- RAG 1024 verification checklist PASS on target environment.
- Verified ingestion/RAG metrics and human-review queue smoke on target environment.

## Phase alignment

- Current work aligns with Phase 3 verification and pre-beta hardening toward Phase 4 beta readiness.

## Immediate next steps

- Owner authorises verification run per checklist above.
- Do not push until owner instructs.
