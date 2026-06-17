# Next Tasks

Generated: 2026-06-17  
Max 5 priorities; phase-aligned.

## A — Release RAG repair (highest priority)

**Branch:** `release/lawapp-clean-snapshot`  
**Phase:** 4 → 5 gate

1. Fix semantic retrieve: repoint `backend/core/retrieve.py` semantic leg to `corpus_chunks` **or** migrate `legislation`/`acas_guidance` to `vector(1024)`.
2. Fix RAG microservice query embedder: Ollama `bge-large-en-v1.5` (1024), remove 384-dim fastembed for prod search.
3. Proof: hybrid search returns hits; `/api/rag/search` non-empty on test query.
4. Re-run: `python scripts/proof/verify_ingestion_084.py` with `DATABASE_URL=postgresql://lawapp:lawapp@localhost:5435/lawapp`
5. Re-run: `python -m pytest tests/test_single_brain_architecture.py tests/test_build_order_gates.py -q`

**Blocking:** beta promotion (owner decision: still NO after embed-only proof).

## B — SEO Track B (after explicit owner approval only)

**Branch:** `feat/seo-command`  
**Phase:** parallel admin module (not beta-critical)

1. Owner sign-off at Track A boundary (checkpoint in `docs/08_SEO_COMMAND_HANDOFF.md`).
2. Create `backend/seo/agents/` per `docs/SEO_COMMAND_SPEC.md` §5-7.
3. Implement orchestrator + specialists; proposals → `seo_actions` with server-side `gate.py`.
4. Proof: pytest + grep (no case data, no auto-execute).
5. Stop at Track B boundary before Track C.

**Status:** NOT APPROVED — do not start.

## C — Beta promotion review (later)

**Branch:** `release/lawapp-clean-snapshot`  
**Phase:** 5

After task A proof:

1. Update `reports/BETA_PROMOTION_REVIEW.md` with retrieve proof.
2. Owner review of unified gate bundle `reports/beta_gate_evidence_unified.txt`.
3. Confirm 11-topic scope fencing still holds in UI/API tests.

## D — Do not do

- Push to `main`
- Deploy to production Kubernetes
- Rotate or print secrets
- Start SEO Track B without approval
- Reintroduce LangGraph / `backend/ai/` / `/api/v1/legal/reason`
- Bulk Find Case Law crawl (licence gate)
- Claim beta-ready while RAG search returns 0 hits

## Immediate next command (new session)

```powershell
cd F:\lawapp
git checkout release/lawapp-clean-snapshot
git pull origin release/lawapp-clean-snapshot   # if owner wants remote sync
$env:DATABASE_URL="postgresql://lawapp:lawapp@localhost:5435/lawapp"
python -m pytest tests/test_single_brain_architecture.py tests/test_build_order_gates.py -q
# Then begin RAG retrieve repair (Task A)
```

For SEO-only resume:

```powershell
git checkout feat/seo-command
git pull origin feat/seo-command
python -m pytest tests/test_seo_command_track_a.py tests/test_single_brain_architecture.py -q
# Wait for owner Track B approval before agents/
```
