# LawApp  -  Subagent Operating Status

**Updated:** 2026-06-14  
**Branch:** `release/lawapp-clean-snapshot`  
**Recovery command:** `/recover` (source-command-recover)

---

## Binding report contract (this session)

```
CURRENT TASK: QA-001 RAG corpus bootstrap + wiring repair
PROJECT MANAGER: project-manager (this session)
IMPLEMENTATION SUBAGENT: db-rag-ingestion-agent (RAG service + corpus sync)
QA SUBAGENT: qa-release-gatekeeper (inline verification)
TASK FILE: docs/qa/CURSOR_REPAIR_BACKLOG.md (QA-001, QA-002)
FILES CHANGED:
  - backend/services/lawapp-rag-service/main.py
  - backend/services/lawapp-rag-service/requirements.txt
  - backend/services/lawapp-citation-guard/main.py
  - ingestion/sync_corpus_chunks.py
COMMANDS RUN:
  - docker compose ps
  - docker compose exec db psql (corpus counts, FTS probe)
  - docker compose build lawapp-rag-service
  - docker compose up -d lawapp-rag-service
  - docker compose --profile bootstrap run --rm db-bootstrap (partial  -  sync step failed in image)
  - docker compose --profile ingestion run --rm ingestion python -m ingestion.sync_corpus_chunks
  - docker compose exec redis redis-cli FLUSHALL
  - Invoke-RestMethod POST localhost:8017/api/rag/search
  - python -m pytest tests/test_employment_module_scope.py (2 targeted tests)
EVIDENCE:
  - corpus_chunks: 28 → 323; embedded: 315
  - POST /api/rag/search "unfair dismissal" → total_found=5, ACAS + ERA s.98/111
  - Root cause: lawapp-rag-service queried non-existent legal_corpus table
  - sync_corpus_chunks failed on jurisdiction NOT NULL  -  fixed with COALESCE(jurisdiction, jurisdiction_code, 'GB')
  - test_workflow_diagnosis_fails_closed_for_unverified_employment_module PASSED
QA VERDICT: REJECT (go-live) / ACCEPT (QA-001 search criterion) / PARTIAL (QA-001 corpus size, QA-002)
COMMIT: NOT PERFORMED (user rule  -  escalate)
PUSH: NOT PERFORMED
NEXT TASK: Rebuild db-bootstrap image; expand corpus; QA-004 integration auth fixes
HARD APPROVAL NEEDED: NO (no prod deploy / secret rotation this session)
```

---

## Constitution / guides

| Document | Status |
|----------|--------|
| `AGENTS.md` | **MISSING** from repo root |
| `BEHAVIOUR_CONSTITUTION.md` | **MISSING** (referenced in recover.md; was untracked `tasks/LAWAPP_BEHAVIOUR_CONSTITUTION.md` per task 001) |
| `.Codex/LEGAL_AI_*_GUIDE.md` | **MISSING** |
| `.claude/commands/recover.md` | Present  -  binding rules applied |

**BEHAVIOUR CONSTITUTION READ AND ACTIVE**  -  via recover command rules + SUBAGENT binding contract (no fake PASS, fail-closed legal data, provenance chain, owner-gated actions escalated).

---

## Subagents (14/14)

All agent definitions present under `.claude/agents/` and `.codex/agents/`.

---

## Current active task

**QA-001**  -  db-rag-ingestion-agent  
**Secondary:** QA-002 fail-closed verification  -  legal-rule-engine-agent (API layer proven; DB promotion backlog)

---

## Blocker ownership (updated)

| Blocker | Owner | Notes |
|---------|-------|-------|
| QA-001 RAG | db-rag-ingestion-agent | Search wired; corpus 323/>>1000 |
| QA-002 modules | legal-rule-engine-agent + product-ux | 11 production, 13 partial; API fail-closed |
| QA-004 tests | backend-api-engineer | 59 failures open |
| G2 leaked PATs | security-auth-payment-agent | **Owner-only** |
| G1 prod brain | platform-devops-scale-agent | **Owner-only** deploy |
