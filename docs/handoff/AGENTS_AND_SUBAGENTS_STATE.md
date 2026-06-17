# Agents and subagents state

Generated: 2026-06-18T00:06:00Z
Repo: serverax/lawapp
Branch: release/lawapp-clean-snapshot
Commit at write: 6eca1b6 (local; not pushed)
Owner directive: STOP all agents; documentation only; no push unless owner approves.

## 1. Global stop state

- **All agent work is stopped.**
- **No agents or subagents are currently authorised to continue.**
- **No background work should remain running.**
- Any in-flight or partial agent work must be treated as **abandoned** unless the owner explicitly restarts it.
- Do not spawn Task/subagent runners, parallel coding agents, or autonomous recovery loops on `release/lawapp-clean-snapshot` or `feat/seo-command` without explicit owner tasking.

## 2. LangGraph agent state

- **LangGraph work is blocked.**
- **ADR-000 remains binding** (`docs/adr/ADR-000-langgraph-gate.md`).
- **`brain.py` is the only legal reasoning runtime.**
- **No LangGraph runtime is approved.**
- **No second legal orchestration path is approved.**
- Any previous LangGraph/subagent idea must remain **stopped** unless the owner explicitly reopens it.
- Hard block (never resume subagent `6e5e6e51` or replay commits `993b3b5` / `bb004cd`):
  - No `backend/ai/`
  - No `backend/core/langgraph/`
  - No `legal_reason_routes.py`
  - No `POST /api/v1/legal/reason`
  - No `langgraph` / `langchain-core` production deps
- Enforcement: `tests/test_single_brain_architecture.py` must remain green; `rg langgraph backend/` must stay at 0 matches on release.

## 3. SEO agents state

- **SEO Track A is complete only** (on `feat/seo-command` @ `263baa3`, pushed to `origin/feat/seo-command`).
- **SEO Track B is not approved.**
- **`backend/seo/agents/` must not be created.**
- **No SEO agent or specialist may run.**
- **No SEO execution layer may run.**
- SEO agents may not draft, queue, publish, or execute until Track B is explicitly approved by the owner.
- **G1-G6 SEO gates remain binding** (from `docs/SEO_COMMAND_SPEC.md` on feat branch):
  - **G1** — Never push/deploy to `main`; SEO work stays on `feat/seo-command`
  - **G2** — Never rotate/log secrets; missing creds = STOP
  - **G3** — No legal substance auto-published
  - **G4** — Legal figures from `rules` table only
  - **G5** — No user case data in SEO module
  - **G6** — No paid spend
- Track C (gated execution / auto-execute): **NOT STARTED** — blocked behind Track B.
- Reference: `docs/handoff/SEO_COMMAND_STATE.md`, `docs/08_SEO_COMMAND_HANDOFF.md`.

## 4. RAG/retrieval WIP agent state

- Release/RAG repair was identified as the next priority but **must NOT continue in this handoff session**.
- Any in-flight RAG WIP must be **abandoned/stopped now** (subagent `fda7afca`).
- The next session must restart from the handoff docs, **not** from partial hidden agent context.
- **Do not continue** editing retrieval, embeddings, RAG routes, or DB logic in this session.
- Abandon list (do not commit):

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

- Planned proof file `reports/rag_1024_retrieval_repair.txt` was **not created** (repair abandoned before proof).

## 5. Subagent runs

Verified from git history, `docs/handoff/PROOF_INDEX.md`, `docs/handoff/SEO_COMMAND_STATE.md`, and agent session transcripts.

| Purpose | Branch | Subagent ID | Status | Output / proof path | Changed code or docs | Pushed |
|---------|--------|-------------|--------|---------------------|----------------------|--------|
| Gate D live recovery | `release/lawapp-clean-snapshot` | `7f29543e` | **completed** | `reports/beta_gate_evidence_unified.txt`; commit `97a405b` | docs + evidence commits | **Yes** (historical) |
| Prod embed hardening | `release/lawapp-clean-snapshot` | — | **completed** | `reports/prod_embed_hardening_cursor.txt`; commit `804a232` | docs + evidence | **Yes** (on origin release) |
| SEO Track A read-only spine | `feat/seo-command` | `ce07c144` | **completed** | `reports/seo_track_a_proof.txt` (feat branch only) | code + tests + migration 087 | **Yes** (`origin/feat/seo-command` @ `263baa3`) |
| 1024-dim RAG retrieval repair | `release/lawapp-clean-snapshot` | `fda7afca` | **abandoned** | none (planned proof not written) | code WIP uncommitted | **No** |
| Session handoff bundle | `release/lawapp-clean-snapshot` | `9cc246a9` | **completed** | `docs/handoff/*`; commit `4f6ec91` | docs only | **No** (local ahead of origin) |
| Agent handoff STOP state | `release/lawapp-clean-snapshot` | `30d16599`, `c27f611a` | **completed** | commit `dfd4ec9` | docs only | **No** (local ahead of origin) |
| LangGraph / backend/ai bootstrap | `release/lawapp-clean-snapshot` | `6e5e6e51` | **blocked** | ADR-000; commits `993b3b5`/`bb004cd` not on origin | code reverted locally | **No** |
| Ingestion workers | `release/lawapp-clean-snapshot` | `89552fa1` | **abandoned** | no `ingestion/workers/` in repo | none landed | **No** |

If no verified evidence exists for a subagent not listed above: **No verified repo evidence found. Do not infer.**

## 6. Required stop condition

After `AGENTS_AND_SUBAGENTS_STATE.md` and `HANDOFF.md` are committed locally, **STOP EVERYTHING**.

Do **not** continue with: RAG repair, release fixes, SEO Track B, SEO agents, LangGraph, tests beyond handoff verification, deployment, push, cleanup, or code changes.

## New session entry (anti-drift)

1. Read [HANDOFF.md](./HANDOFF.md) and this file first.
2. Confirm `backend/ai/` absent and `backend/seo/agents/` absent.
3. Do not resume subagents `fda7afca` or `6e5e6e51` without explicit owner approval.
4. Wait for owner instruction before any implementation work.

## Parallel agent drift history

- **`backend/ai/` reappearing:** Forbidden second-runtime tree has been recreated by parallel agents in past sessions; removed per ADR-000; must not return.
- **Protection:** `.gitignore` includes `backend/ai/` so accidental commits are harder; **not a substitute for review** — agents must not create the directory at all.
- **LangGraph subagent `6e5e6e51`:** Canonical "do not resume" example for bootstrap drift.
- **No LangGraph/bootstrap on `release/lawapp-clean-snapshot` or `feat/seo-command`** unless owner explicitly reopens ADR-000.

## Push and remote

- Handoff commits `4f6ec91`, `dfd4ec9`, and `6eca1b6`: **local only**; branch ahead of `origin/release/lawapp-clean-snapshot`; **NO PUSH** in this task.
- `804a232` (prod embed): on origin release before local handoff commits.
- RAG repair and SEO Track B: **not started / not committed** on release at STOP time.

## Pointers

- Session snapshot: `docs/handoff/HANDOFF.md`
- Architecture: `docs/handoff/ARCHITECTURE_STATE.md`
- SEO command: `docs/handoff/SEO_COMMAND_STATE.md`
- Next tasks: `docs/handoff/NEXT_TASKS.md`
- Known issues: `docs/handoff/KNOWN_ISSUES.md`
- Proof index: `docs/handoff/PROOF_INDEX.md`
