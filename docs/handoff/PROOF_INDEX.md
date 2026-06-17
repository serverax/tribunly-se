# Proof Index

Generated: 2026-06-17  
Commands run this session unless marked historical.

## Git verification

```powershell
cd F:\lawapp
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -5
git fetch origin
git rev-parse origin/release/lawapp-clean-snapshot
git rev-parse origin/feat/seo-command
git log -1 --oneline origin/release/lawapp-clean-snapshot
git log -1 --oneline origin/feat/seo-command
```

## Path checks (release checkout)

| Path | Exists on release | Exists on feat/seo-command |
|------|-------------------|----------------------------|
| `docs/08_SEO_COMMAND_HANDOFF.md` | Created this session | No (was local 160015a only) |
| `reports/seo_track_a_proof.txt` | No | Yes |
| `backend/seo/agents/` | No | No (AGENTS_ABSENT_OK) |
| `backend/ai` | No | No |

```powershell
Test-Path backend/ai                    # False
Test-Path backend/seo/agents            # False (release)
Test-Path docs/08_SEO_COMMAND_HANDOFF.md  # True after this commit
Test-Path reports/seo_track_a_proof.txt     # False on release
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

**Release @ 804a232:**

```powershell
python -m pytest tests/test_single_brain_architecture.py tests/test_build_order_gates.py -q
# 16 passed, 33 warnings in 15.11s
```

**feat/seo-command @ 263baa3 (worktree):**

```powershell
python -m pytest tests/test_single_brain_architecture.py tests/test_seo_command_track_a.py -q
# 28 passed, 33 warnings in 21.26s

python -m pytest tests/test_seo_command_track_a.py -q
# 15 passed
```

## DB corpus (live verified)

```powershell
# Port 5435 reachable: True
$env:PGPASSWORD='lawapp'
psql -h localhost -p 5435 -U lawapp -d lawapp -t -c "SELECT COUNT(*), COUNT(embedding), MAX(embedding_dim) FROM corpus_chunks;"
# 978 | 978 | 1024
```

## Evidence files (by topic)

| Topic | Pathology |
|-------|-----------|
| Embed hardening | `reports/prod_embed_hardening_cursor.txt` |
| Beta gate bundle | `reports/beta_gate_evidence_unified.txt` |
| Beta promotion review | `reports/BETA_PROMOTION_REVIEW.md` |
| Ingestion 084 | `reports/ingestion_084_cursor.txt` |
| SEO Track A | `reports/seo_track_a_proof.txt` (feat branch) |
| ADR-000 | `docs/adr/ADR-000-langgraph-gate.md` |
| SEO spec | `docs/SEO_COMMAND_SPEC.md` (feat branch) |
| Session handoff | `docs/handoff/*.md`, `docs/08_SEO_COMMAND_HANDOFF.md` |

## Ingestion verify script

```powershell
$env:DATABASE_URL="postgresql://lawapp:lawapp@localhost:5435/lawapp"
python scripts/proof/verify_ingestion_084.py
# NOT re-run this session — historical PASS at 97a405b/1e10075
```

## Stash / local-only commits

```powershell
git stash list
# stash@{0}: On feat/seo-command: wip-all

git show 160015a --stat
# docs/08_SEO_COMMAND_HANDOFF.md (local commit, not on origin)

git rev-parse fda7afca
# fatal: unknown revision
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
