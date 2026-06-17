# Agents and subagents state

Generated: 2026-06-17T23:00:00Z
Repo: serverax/lawapp
Branch: release/lawapp-clean-snapshot
Commit at write: 4f6ec91
Owner directive: STOP all agents; documentation only; no push unless owner approves.

## Policy (mandatory for new sessions)

| Rule | Status |
|------|--------|
| SEO Track B | **NOT APPROVED** — do not create `backend/seo/agents/`, orchestrator, or specialist roster |
| SEO Track C | **NOT STARTED** — blocked until Track B boundary and owner sign-off |
| Second reasoning runtime | **FORBIDDEN** — ADR-000; `brain.py` only; no LangGraph stack |
| Subagent `6e5e6e51` (LangGraph / bootstrap) | **PERMANENTLY BLOCKED** — never resume, never scaffold `backend/ai/`, `backend/core/langgraph/`, or `POST /api/v1/legal/reason` |
| RAG retrieve repair subagent `fda7afca` | **STOP** — do not resume without explicit owner approval; do not commit or push repair WIP |
| Autonomous agent spawn on `release/lawapp-clean-snapshot` or `feat/seo-command` | **DO NOT** — no bootstrap agents, no parallel coding agents on RAG/SEO without owner tasking |

## Significant subagent runs (this session arc)

| Title | Subagent ID (optional) | Focus | Outcome | Pushed | Resume |
|-------|------------------------|-------|---------|--------|--------|
| Gate D recovery | 7f29543e | Ingestion 084 verification, evidence bundle | Recovery / proof path documented; Gate D PASS evidence in git history (97a405b era) | Prior commits only; not part of this STOP pass | Only if owner re-opens ingestion verification |
| SEO Track A | ce07c144 | Read-only SEO command spine on `feat/seo-command` | Track A work exists on feature branch (remote `feat/seo-command` per prior handoff); **no `backend/seo/agents/`** on release | Feature branch pushes historical; **release line not SEO-extended** | SEO docs/read-only only until owner lifts STOP |
| RAG repair | fda7afca | 1024-dim retrieve alignment (`retrieve.py`, RAG microservice, compose, tests) | **INCOMPLETE — abandoned at owner STOP**; dirty tree on release (see below) | **NO** | **NEVER** without owner; do not commit repair |
| Handoff / sync | 9cc246a9 | `docs/handoff/` snapshots, owner STOP finalization | Handoff docs updated; agent state captured in this file | Local commit only when owner allows; **no push in this task** | Docs-only handoff OK |
| Rogue LangGraph / bootstrap | 6e5e6e51 | Attempted second runtime / agent bootstrap | **BLOCKED** per ADR-000 and project rules | **NO** | **NEVER** |

## What each agent class was doing

- **Gate D recovery (7f29543e):** Restore confidence in migration 084 / ingestion proof after drift; outcome tied to committed evidence scripts and pytest gates, not to uncommitted RAG repair.
- **SEO Track A (ce07c144):** Implement read-only SEO command module and tests on `feat/seo-command`; **did not** build Track B agent roster; Track A is the only SEO code path approved historically and remains gated by owner STOP for further SEO work.
- **RAG repair (fda7afca):** Align semantic/hybrid retrieve and RAG service query embeddings with 1024-dim `corpus_chunks`; **stopped mid-edit** — must not be resumed or committed without owner.
- **Handoff (9cc246a9):** Consolidate session state for humans and next agent; no code changes beyond `docs/handoff/` in this final step.
- **Rogue LangGraph (6e5e6e51):** Would have reintroduced forbidden paths; treat as permanently rejected.

## In-flight work to abandon (do not commit)

Owner STOP: leave the following **uncommitted** on `release/lawapp-clean-snapshot` (verified `git status` at handoff write):

| Path | Role |
|------|------|
| `backend/core/retrieve.py` | RAG repair WIP |
| `backend/services/lawapp-rag-service/main.py` | RAG service repair WIP |
| `backend/services/lawapp-rag-service/requirements.txt` | RAG service deps WIP |
| `backend/services/lawapp-rag-service/ollama_embed.py` | Untracked embed helper (repair) |
| `docker-compose.override.yml` | Local stack tweak for repair |
| `.env.example` | Local env guidance touched during repair |
| `tests/integration/test_semantic_retrieval.py` | Repair-related test edits |
| `tests/test_rag_1024_retrieval_repair.py` | Untracked repair test |

Also modified outside `docs/handoff/` (not staged in agent handoff commit): `docs/08_SEO_COMMAND_HANDOFF.md`.

**Do not** run repair pytest, do not `git add` the RAG files above, do not push.

## SEO agent roster (doc 07 / SEO command spec)

| Track | Status | Notes |
|-------|--------|-------|
| Track A | **Done** (on `feat/seo-command`, not release) | Read-only spine; admin/dashboard; **no agents directory** |
| Track B | **NOT STARTED** | **NOT APPROVED** — orchestrator + six specialists **NOT BUILT** |
| Track C | **NOT STARTED** | Blocked behind Track B |

Reference: `docs/07_PROJECT_HANDOVER.md`, `docs/08_SEO_COMMAND_HANDOFF.md`, `docs/SEO_COMMAND_SPEC.md` (feature branch).

## How a new session should start (anti-drift)

1. **Checkout** `release/lawapp-clean-snapshot` unless owner explicitly tasks SEO-only doc work on `feat/seo-command`.
2. **Do not** spawn subagents to implement LangGraph, `backend/ai/`, SEO Track B agents, or RAG repair unless owner removes STOP and names the task.
3. **Read** this file and `docs/handoff/HANDOFF.md` before any code.
4. **Prefer** single-threaded, owner-scoped tasks; no parallel “bootstrap” agents on release or feat/seo-command.
5. **Confirm** `backend/ai/` absent (`Test-Path backend/ai` → False) and `backend/seo/agents/` absent before coding.

## Parallel agent drift history

- **`backend/ai/` reappearing:** Forbidden second-runtime tree has been recreated by parallel agents in past sessions; removed per ADR-000; must not return.
- **Protection:** `.gitignore` includes `backend/ai/` so accidental commits are harder; **not a substitute for review** — agents must not create the directory at all.
- **LangGraph subagent 6e5e6e51:** Canonical “do not resume” example for bootstrap drift.

## Push and remote

- This handoff pass: **local commit only** (`docs/handoff/`), **NO PUSH**.
- RAG repair and SEO Track B: **not started / not committed** on release at STOP time.

## Pointers

- Session snapshot: `docs/handoff/HANDOFF.md`
- Architecture: `docs/handoff/ARCHITECTURE_STATE.md`
- Next tasks: `docs/handoff/NEXT_TASKS.md`
- Known issues: `docs/handoff/KNOWN_ISSUES.md`
