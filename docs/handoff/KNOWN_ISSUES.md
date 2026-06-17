# Known Issues

Generated: 2026-06-17

## Open bugs

| ID | Issue | Severity | Branch |
|----|-------|----------|--------|
| RAG-001 | RAG service 384-dim query vs 1024 corpus — empty search hits | P0 | release |
| RAG-002 | `retrieve_semantic` uses empty `legislation.embedding` (384 schema) | P0 | release |
| ENV-001 | Host `.env` password `change_this_password` vs Docker volume `lawapp` | P1 | local dev |
| SEO-001 | `160015a` SEO handoff commit not pushed to origin | P2 | feat/seo-command |
| GIT-001 | SSH identity file warning on `git fetch` | P2 | local |
| REF-001 | Commit `fda7afca` (RAG repair) not found in repo | Info | — |

## Technical debt

- Source tables (`legislation`, `acas_guidance`) still `vector(384)` while `corpus_chunks` is 1024
- `provision` canonical schema vs legacy corpus dual-plane (owner Q1/Q5)
- Release branch behind `main` on deploy/otel/pyjwt fixes (baseline is release, not main)
- Stash `wip-all` on feat/seo-command may contain unmerged work
- Temporary worktree `_wt_feat` removal failed (Permission denied) — manual cleanup if folder remains

## Failing tests

None on scoped release pytest this session (16/16 pass).  
Full suite NOT re-run this session.

## Missing integrations

- Live GSC/GA4 credential wiring for SEO datasources (feat branch)
- RAG retrieve alignment with 1024 corpus (release)
- K8s prod health — NOT VERIFIED this session

## Data ingestion gaps

- `legislation` table: 0 embeddings at source level
- NI jurisdiction chunks: 0 (historical reports)
- Corpus below 1000 stretch target (978 chunks — acceptable for beta evidence, noted in prior gates)

## Legal data verification

- CitationGuard enforced on Brain path (tests pass)
- SEO Track A: no case data in `backend/seo/` (grep proof on feat)
- Unverified live Brain answer audit NOT re-run this session

## Unstable pipeline components

- Ollama embed batch limits required adaptive truncation in reembed script
- Docker Desktop API intermittent 500 (recovered 2026-06-17 per gate bundle note)

## Beta / production gates (owner decisions)

| Gate | Status |
|------|--------|
| Beta promotion | **NO** |
| SEO Track B | **NOT APPROVED** |
| Public production | **NO-GO** (historical gatekeeper verdict) |

## Pytest warnings

`PytestCacheWarning` on `.pytest_cache` path (WinError 183) — cosmetic; tests still pass.
