# 08 — SEO Command: Session Handoff

**Repo:** `github.com/serverax/lawapp` (local `F:\lawapp`)  
**SEO branch:** `feat/seo-command` @ `263baa3` (`origin/feat/seo-command`)  
**Release baseline:** `release/lawapp-clean-snapshot` @ `804a232`  
**Date:** 2026-06-17

---

## Canonical handoff location

**Project-wide session handoff lives at `docs/handoff/`** (committed on `release/lawapp-clean-snapshot`):

| Document | Contents |
|----------|----------|
| [`docs/handoff/HANDOFF.md`](handoff/HANDOFF.md) | One-page project status |
| [`docs/handoff/ARCHITECTURE_STATE.md`](handoff/ARCHITECTURE_STATE.md) | ADR-000, brain, RAG, forbidden paths |
| [`docs/handoff/RELEASE_STATE.md`](handoff/RELEASE_STATE.md) | Release embed proof, RAG blockers |
| [`docs/handoff/SEO_COMMAND_STATE.md`](handoff/SEO_COMMAND_STATE.md) | Track A/B/C, G1-G6, push status |
| [`docs/handoff/NEXT_TASKS.md`](handoff/NEXT_TASKS.md) | Prioritized next work |
| [`docs/handoff/KNOWN_ISSUES.md`](handoff/KNOWN_ISSUES.md) | Open issues |
| [`docs/handoff/PROOF_INDEX.md`](handoff/PROOF_INDEX.md) | Commands and proof files |

This file (`docs/08_SEO_COMMAND_HANDOFF.md`) is the SEO-specific entry point and cross-link hub.

---

## Summary (verified 2026-06-17)

- **Track A DONE** on `feat/seo-command` @ `263baa3`: read-only SEO spine, admin dashboard, migration 087, datasources.
- **`backend/seo/agents/` absent** — Track A boundary intact.
- **Track B NOT STARTED — NOT APPROVED.** Do not create agents until owner approves.
- **Track C NOT STARTED.**
- **Pytest (feat @ 263baa3):** 28 passed (`test_single_brain_architecture.py` + `test_seo_command_track_a.py`).
- **ADR-000 intact:** no `backend/ai/`, no LangGraph, no `/api/v1/legal/reason`.
- **Proof report:** `reports/seo_track_a_proof.txt` (on feat branch only, not on release).
- **Spec:** `docs/SEO_COMMAND_SPEC.md` (feat branch; not on release).

### Push / local commit note

- `origin/feat/seo-command` = `263baa3` (pushed).
- Local commit `160015a` (`docs: SEO Command session handoff`) was **not pushed**; content merged into this file + `docs/handoff/`.

---

## Hard gates G1-G6 (active)

Source: `docs/SEO_COMMAND_SPEC.md` §0 (on feat branch).

- **G1** — Never push or deploy to `main`. Work on `feat/seo-command`.
- **G2** — Never rotate, generate, print, echo, or log live secrets.
- **G3** — No legal substance auto-published.
- **G4** — Legal figures from `rules` table with citation only.
- **G5** — No user case data in SEO module.
- **G6** — No paid spend.

---

## Track checkpoint

| Track | Status | Evidence |
|-------|--------|----------|
| A — read-only spine | **DONE** | `6ce4eac`, `263baa3`, `reports/seo_track_a_proof.txt` |
| B — agent roster | **NOT STARTED** | No `backend/seo/agents/`; owner approval required |
| C — gated execution | **NOT STARTED** | No execute path beyond gate unit tests |

---

## Path map (spec vs repo)

| Spec | Live (feat branch) |
|------|---------------------|
| `client/admin/seo/` | `client/public/admin/seo/` |
| `docs/07_SEO_COMMAND_INTEGRATION_ORDER.md` | `docs/SEO_COMMAND_SPEC.md` |
| Migration 085 | `087_seo_command_tables.sql` |

---

## Env ref names (G2 — never log values)

`GSC_OAUTH_TOKEN_REF`, `GSC_SITE_URL`, `GA4_PROPERTY_ID`, `GA4_CREDENTIALS_REF`, `PSI_API_KEY_REF`, `SEO_CRAWL_BASE_URL`, `SEO_CRAWL_ALLOWED_HOST`

Live GSC/GA4 pulls: NOT VERIFIED (STOP behaviour in unit tests only).

---

## Release cross-facts (from `docs/handoff/RELEASE_STATE.md`)

- Corpus: **978/978 @ 1024-dim** (live DB verified on release line).
- Beta promotion: **NO** (RAG retrieve alignment still open on release).
- SEO work does **not** block release RAG repair; keep branches separate per G1.

---

## Next action

**Obtain explicit owner approval** before crossing Track A → Track B boundary.  
Do **not** create `backend/seo/agents/` until approved.

See [`docs/handoff/NEXT_TASKS.md`](handoff/NEXT_TASKS.md) §B.

---

## How to resume

```powershell
git checkout feat/seo-command
git pull origin feat/seo-command    # only if owner wants remote sync
python -m pytest tests/test_seo_command_track_a.py tests/test_single_brain_architecture.py -q
```

Read:

1. This file
2. `docs/handoff/SEO_COMMAND_STATE.md`
3. `reports/seo_track_a_proof.txt` (checkout feat branch)
4. `docs/SEO_COMMAND_SPEC.md` (checkout feat branch)

After owner approval → implement Track B per spec §5-7. Stop again at Track B boundary before Track C.
