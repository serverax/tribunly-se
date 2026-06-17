# Proof Index

Generated: 2026-06-18
HEAD: `4209216` on `release/lawapp-clean-snapshot` (0 ahead / 0 behind origin)

## Git verification

```powershell
cd F:\lawapp
git status --short
git branch --show-current
git rev-parse HEAD
git status -sb
git rev-list --left-right --count origin/release/lawapp-clean-snapshot...HEAD
# 0 0
```

## Path checks (release checkout)

| Path | Exists on release | Exists on feat/seo-command |
|------|-------------------|----------------------------|
| `docs/08_SEO_COMMAND_HANDOFF.md` | Yes | No (was local 160015a only) |
| `reports/seo_track_a_proof.txt` | No | Yes |
| `reports/rag_1024_retrieval_repair.txt` | Yes (local file) | No |
| `backend/seo/agents/` | No | No (AGENTS_ABSENT_OK) |
| `backend/ai` | No | No |
| `backend/services/lawapp-rag-service/ollama_embed.py` | Yes (tracked @ 4209216) | — |
| `tests/test_rag_1024_retrieval_repair.py` | Yes (tracked @ 4209216) | — |

```powershell
Test-Path backend/ai                              # False
Test-Path backend/seo/agents                      # False (release)
Test-Path reports/rag_1024_retrieval_repair.txt   # True
Test-Path reports/seo_track_a_proof.txt           # False on release
```

## Grep (release committed tree)

```powershell
# langgraph in backend runtime
rg langgraph backend/                     # 0 matches

# backend/ai tracked files
git ls-tree -r --name-only origin/release/lawapp-clean-snapshot | Select-String "backend/ai"
# (empty)

# legal/reason — only test negations + proof scripts, not live routes
rg "legal/reason|/api/v1/legal/reason" --glob "*.py"
```

## Pytest

**Release @ 4209216 (historical from repair proof; re-run required):**

```powershell
python -m pytest tests/test_rag_1024_retrieval_repair.py tests/test_single_brain_architecture.py tests/test_build_order_gates.py -q
# 21 passed (reports/rag_1024_retrieval_repair.txt)
```

**feat/seo-command @ 263baa3 (worktree):**

```powershell
python -m pytest tests/test_single_brain_architecture.py tests/test_seo_command_track_a.py -q
# 28 passed, 33 warnings in 21.26s

python -m pytest tests/test_seo_command_track_a.py -q
# 15 passed
```

## DB corpus (live verified historical)

```powershell
# Port 5435 reachable: True
$env:PGPASSWORD='lawapp'
psql -h localhost -p 5435 -U lawapp -d lawapp -t -c "SELECT COUNT(*), COUNT(embedding), MAX(embedding_dim) FROM corpus_chunks;"
# 978 | 978 | 1024
```

## Evidence files (by topic)

| Topic | Path | Status |
|-------|------|--------|
| Embed hardening | `reports/prod_embed_hardening_cursor.txt` | On origin |
| RAG 1024 retrieval repair | `reports/rag_1024_retrieval_repair.txt` | **Exists** (historical PASS @ repair); **re-run pending** before beta promotion |
| `/api/rag/search` API proof | inside `reports/rag_1024_retrieval_repair.txt` | **Refresh required** after `4209216` on current environment |
| Beta gate bundle | `reports/beta_gate_evidence_unified.txt` | Historical @ 97a405b |
| Beta promotion review | `reports/BETA_PROMOTION_REVIEW.md` | Stale; refresh after verification |
| Ingestion 084 | `reports/ingestion_084_cursor.txt` | Historical PASS |
| SEO Track A | `reports/seo_track_a_proof.txt` | On feat branch only |
| ADR-000 | `docs/adr/ADR-000-langgraph-gate.md` | Binding |
| SEO spec | `docs/SEO_COMMAND_SPEC.md` | feat branch |
| Session handoff | `docs/handoff/*.md`, `docs/08_SEO_COMMAND_HANDOFF.md` | This reconcile pass |

## Ingestion verify script

```powershell
$env:DATABASE_URL="postgresql://lawapp:lawapp@localhost:5435/lawapp"
python scripts/proof/verify_ingestion_084.py
# NOT re-run this session — historical PASS at 97a405b; re-run after RAG verification
```

## Stash / local-only commits

```powershell
git stash list
# stash@{0}: On feat/seo-command: wip-all
```

## Handoff bundle

| File | Purpose |
|------|---------|
| `docs/handoff/HANDOFF.md` | One-page project status |
| `docs/handoff/ARCHITECTURE_STATE.md` | ADR, brain, RAG, corpus |
| `docs/handoff/RELEASE_STATE.md` | Release line, embed, blockers |
| `docs/handoff/SEO_COMMAND_STATE.md` | feat/seo-command tracks |
| `docs/handoff/NEXT_TASKS.md` | Prioritized work |
| `docs/handoff/KNOWN_ISSUES.md` | Issues register |
| `docs/handoff/PROOF_INDEX.md` | This file |
| `docs/handoff/AGENTS_AND_SUBAGENTS_STATE.md` | Agent STOP policy |
