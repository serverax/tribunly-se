# P2 Sweep Log

**Phase C Task 4** — fix copy/contrast/config P2s, log anything touching legal output/payment/architecture.  
**Date:** 2026-07-08 | **Branch:** cc/convergence

---

## Fixed (config/copy/UX level)

| # | Source | Finding | Fix | File |
|---|--------|---------|-----|------|
| 1 | Architect P2 | Backend `depends_on` missing 5 upstream services (rules, rag, graph-rag, redaction, audit) — cold-start race | Added all 5 to `depends_on` with `service_healthy` condition | docker-compose.yml |
| 2 | UX P3 | No time estimate on intake form page | Added "4 steps · about 5 minutes" inline | intake.html:54 |
| 3 | UX P1 | No loading timeout/progress on /assess call | Added AbortController (120s timeout), "still working" message at 15s, styled timeout error | intake.html:470-512 |
| 4 | UX P3 | Landing page CTA links to case-intake.html instead of intake.html | Fixed href to /pages/intake.html | index.html:68 |

## Fixed in prior commit (Phase C T1, 16797ae)

| # | Source | Finding | Fix |
|---|--------|---------|-----|
| 5 | UX P1 | Deadline CSS class mismatch (`urgent` vs `.deadline-urgent`) | Fixed JS class name |
| 6 | UX P2 | Deadline card at position 4 of 10 | Moved to position 1 |
| 7 | UX P2 | Generic error is bare alert() | Replaced with styled error div |
| 8 | AI Arch | Progressive render / streaming | Implemented skeleton + SSE |

## Logged to backlog (touches legal output / payment / architecture)

| # | Source | Finding | Why not fixed | Backlog location |
|---|--------|---------|---------------|------------------|
| 1 | Architect P1 | legislation table vector(384) vs corpus_chunks vector(1024) — semantic search over legislation broken | Schema ALTER on production table; requires migration + re-embedding of 84 legislation rows | JURISDICTION_BACKLOG.md (related) |
| 2 | Architect P2 | employment_modules table lacks jurisdiction column — second-country needs schema migration | Schema change; legal-data architecture decision | JURISDICTION_BACKLOG.md |
| 3 | AI Arch P1 | 3B model fails CitationGuard — 7B bake-off recommended | Model swap requires download (~4.5GB), GPU evaluation, latency benchmarking — not a config-level change | Noted in AI_ARCHITECT_REVIEW.md |
| 4 | AI Arch | 38s deterministic path needs optimisation for <500ms skeleton | Query caching / connection pooling / retrieval optimisation — performance engineering | Noted in AI_ARCHITECT_REVIEW.md |

## Contrast / copy audit (no issues found)

- `--muted: #5d6b78` on white → ~4.6:1 contrast ratio (WCAG AA pass)
- `.legal-notice` colour `#6a5212` on cream background → adequate for warning banner
- `.btn-accent` text `#2a2008` on gold → high contrast
- Dark mode overrides present (`--muted: #2a2f36` on dark background)
- No broken copy or placeholder text found in live pages

---

*No legal output, payment flow, or architectural changes made in this sweep. All logged items are owner-gated.*
