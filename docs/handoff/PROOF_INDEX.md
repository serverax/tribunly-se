# Proof Index

Generated: 2026-06-18T15:45:00Z  
Code HEAD: pending fix commit on `release/lawapp-clean-snapshot`  
Prior HEAD: `97aeae4`

## Git verification

```powershell
cd F:\lawapp
git status --short
git branch --show-current
git rev-parse HEAD
git status -sb
```

## Beta gate fixes (2026-06-18)

| Check | Result |
|-------|--------|
| `tests/test_claim_checker.py` (diagnosis alias) | **PASS** |
| `tests/test_mother_controller.py` (diagnosis alias) | **PASS** |
| `tests/integration/test_phase6c_jwt.py` | **34/34 PASS** |
| RAG 1024 regression suite | **27/27 PASS** |
| Payment + schedule of loss | **16/16 PASS** |
| ADR-000 forbidden paths | **clean** |
| **Verdict** | **PASS** (conditional — Docker redeploy for live smoke) |

## RAG 1024 verification (refreshed 2026-06-18)

| Check | Result |
|-------|--------|
| corpus_chunks embedded | 978/978 @ 1024-dim |
| model | bge-large-en-v1.5 |
| /api/rag/search | 4/4 queries, 5 hits each, citations present |
| targeted pytest | 27 passed |
| ADR-000 / forbidden paths | clean |
| **Verdict** | **PASS** |

Full report: [`reports/rag_1024_retrieval_repair.txt`](../../reports/rag_1024_retrieval_repair.txt)

## Path checks (release checkout)

| Path | Exists on release | Notes |
|------|-------------------|-------|
| `reports/rag_1024_retrieval_repair.txt` | Yes | Refreshed 2026-06-18 PASS |
| `reports/BETA_PROMOTION_REVIEW.md` | Yes | Refreshed 2026-06-18 PASS |
| `reports/seo_track_a_proof.txt` | **No** | On `feat/seo-command` only |
| `docs/08_SEO_COMMAND_HANDOFF.md` | Yes | Release line |
| `backend/seo/agents/` | No | AGENTS_ABSENT_OK |
| `backend/ai` | No | ADR-000 |
| `backend/services/lawapp-rag-service/ollama_embed.py` | Yes | @ 4209216 |

```powershell
Test-Path backend/ai                              # False
Test-Path backend/seo/agents                      # False
Test-Path reports/rag_1024_retrieval_repair.txt   # True
Test-Path reports/seo_track_a_proof.txt           # False on release
```

## Grep (release committed tree)

```powershell
rg langgraph backend/                     # 0 matches
git ls-tree -r --name-only HEAD | Select-String "backend/ai"   # empty
rg "legal/reason|/api/v1/legal/reason" --glob "*.py"
# test negations + verify_grounding.py only
```

## Pytest (release @ 2026-06-18 re-run)

```powershell
$env:POSTGRES_PASSWORD='lawapp'
$env:DATABASE_URL='postgresql://lawapp:lawapp@localhost:5435/lawapp'
python -m pytest tests/test_rag_1024_retrieval_repair.py tests/test_single_brain_architecture.py tests/test_build_order_gates.py tests/integration/test_semantic_retrieval.py -q
# 27 passed
```

## DB corpus (live verified 2026-06-18)

```powershell
$env:PGPASSWORD='lawapp'
psql -h localhost -p 5435 -U lawapp -d lawapp -t -c "SELECT COUNT(*), COUNT(embedding), MAX(embedding_dim) FROM corpus_chunks;"
# 978 | 978 | 1024
```

## Evidence files (by topic)

| Topic | Path | Status |
|-------|------|--------|
| **RAG 1024 verification** | [`reports/rag_1024_retrieval_repair.txt`](../../reports/rag_1024_retrieval_repair.txt) | **PASS** @ 2026-06-18 |
| **Beta promotion review** | [`reports/BETA_PROMOTION_REVIEW.md`](../../reports/BETA_PROMOTION_REVIEW.md) | **PASS** @ 2026-06-18 |
| `/api/rag/search` API proof | inside `reports/rag_1024_retrieval_repair.txt` | **PASS** 4/4 queries |
| Embed hardening | `reports/prod_embed_hardening_cursor.txt` | Historical on origin |
| Beta gate bundle | `reports/beta_gate_evidence_unified.txt` | Historical |
| Ingestion 084 | `reports/ingestion_084_cursor.txt` | Historical PASS |
| SEO Track A | [`reports/seo_track_a_proof.txt`](../../reports/seo_track_a_proof.txt) | **feat/seo-command only** (not on release) |
| ADR-000 | `docs/adr/ADR-000-langgraph-gate.md` | Binding |
| Session handoff | `docs/handoff/*.md` | This bundle |

## Ingestion verify script

```powershell
$env:DATABASE_URL="postgresql://lawapp:lawapp@localhost:5435/lawapp"
python scripts/proof/verify_ingestion_084.py
# Historical PASS; corpus counts re-confirmed in RAG 1024 proof
```

## Handoff bundle

| File | Purpose |
|------|---------|
| [`docs/handoff/HANDOFF.md`](./HANDOFF.md) | One-page project status |
| [`docs/handoff/ARCHITECTURE_STATE.md`](./ARCHITECTURE_STATE.md) | ADR, brain, RAG, corpus |
| [`docs/handoff/RELEASE_STATE.md`](./RELEASE_STATE.md) | Release line, embed, blockers |
| [`docs/handoff/NEXT_TASKS.md`](./NEXT_TASKS.md) | Prioritized work |
| [`docs/handoff/KNOWN_ISSUES.md`](./KNOWN_ISSUES.md) | Issues register |
| [`docs/handoff/PROOF_INDEX.md`](./PROOF_INDEX.md) | This file |
| [`docs/handoff/AGENTS_AND_SUBAGENTS_STATE.md`](./AGENTS_AND_SUBAGENTS_STATE.md) | Agent STOP policy |
