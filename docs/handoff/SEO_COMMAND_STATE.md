# SEO Command State

Generated: 2026-06-17  
Branch: `feat/seo-command` @ `263baa3` (origin matches)

## Branch verification

| Ref | SHA | Message |
|-----|-----|---------|
| `origin/feat/seo-command` | `263baa3` | chore(seo): Track A proof report |
| Parent feature commit | `6ce4eac` | feat(seo): Track A read-only SEO Command spine |
| Branched from release | `1e10075` | (release now @ `804a232`, +1 embed commit) |

**Push status:** `origin/feat/seo-command` exists at `263baa3` — pushed.  
**160015a handoff commit:** local-only (`docs: SEO Command session handoff`); **NOT on origin**. Content preserved in `docs/08_SEO_COMMAND_HANDOFF.md` on release after this session commit.

## Track status

| Track | Scope | Status |
|-------|-------|--------|
| **A** | Read-only spine, dashboard, migration 087, datasources stubs | **DONE** @ `263baa3` |
| **B** | Agent roster under `backend/seo/agents/` | **NOT STARTED — NOT APPROVED** |
| **C** | Gated execution / auto-execute | **NOT STARTED** |

## Hard gates G1-G6 (active)

From `docs/SEO_COMMAND_SPEC.md` §0:

- **G1** — Never push/deploy to `main`; work on `feat/seo-command`
- **G2** — Never rotate/log secrets; missing creds = STOP
- **G3** — No legal substance auto-published
- **G4** — Legal figures from `rules` table only
- **G5** — No user case data in SEO module
- **G6** — No paid spend

## Track A proof

| Check | Result |
|-------|--------|
| `backend/seo/agents/` | **Absent** (required for Track A) |
| `backend/ai/` | **Absent** |
| Migration | `db/migrations/087_seo_command_tables.sql` |
| Admin UI | `client/public/admin/seo/dashboard.html` |
| Proof report | `reports/seo_track_a_proof.txt` (on feat branch only) |
| Pytest (feat worktree @ 263baa3) | **28 passed** (`test_single_brain_architecture.py` + `test_seo_command_track_a.py`) |
| Track A only pytest | **15 passed** |

## Files on feat/seo-command (not on release)

```
backend/seo/          (routes, gate, grounding, datasources, models, data)
client/public/admin/seo/dashboard.html
db/migrations/087_seo_command_tables.sql
docs/SEO_COMMAND_SPEC.md
tests/test_seo_command_track_a.py
reports/seo_track_a_proof.txt
```

## Path diffs from spec

| Spec | Live |
|------|------|
| `client/admin/seo/` | `client/public/admin/seo/` |
| `docs/07_SEO_COMMAND_...` | `docs/SEO_COMMAND_SPEC.md` |
| Migration 085 | `087_seo_command_tables.sql` |

## Env ref names (G2 — values never logged)

`GSC_OAUTH_TOKEN_REF`, `GSC_SITE_URL`, `GA4_PROPERTY_ID`, `GA4_CREDENTIALS_REF`, `PSI_API_KEY_REF`, `SEO_CRAWL_BASE_URL`, `SEO_CRAWL_ALLOWED_HOST`

Live GSC/GA4 pulls: NOT VERIFIED (STOP behaviour covered by unit tests).

## Stash

```text
stash@{0}: On feat/seo-command: wip-all
```

May contain WIP beyond pushed `263baa3` — inspect before Track B work.

## STOP line

Do **not** create `backend/seo/agents/` until explicit owner approval to cross Track A → Track B boundary.
