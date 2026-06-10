> **STALE — HISTORICAL ONLY (banner added 2026-06-10).** This document predates the current release state. The active source of truth is [docs/GO_LIVE_HANDOFF_2026-06-10.md](../docs/GO_LIVE_HANDOFF_2026-06-10.md) and branch `release/lawapp-clean-snapshot`. Do not use this file for release decisions.

# LawApp — Project Status

**Updated:** 2026-06-06
**Branch:** `recovery/lawapp-autonomous-stabilisation`
**Current freeze:** [001-current-state-freeze-and-status](review/001-current-state-freeze-and-status.md)
**Overall verdict:** 🔴 **REJECT CURRENT STATE** (not releasable; blockers below)

---

## Headline

Architecture is real and largely wired — not a stub farm. But the live production brain is down (DB password mismatch), credentials remain in git history, CI gates are red, and the legal-data provenance chain is not proven end-to-end. **Not acceptable for release.**

---

## Blockers (must clear to move toward ACCEPT)

| # | Blocker | Severity | Autonomy |
|---|---|---|---|
| G1 | Brain `/health` 503 — **re-diagnosed: deployed monolith image stale** (NOT a password issue: rules-engine works with same creds; HEAD source connects locally). Source hardened (/livez). | BLOCKER | **Owner/CI** (rebuild+redeploy monolith from HEAD) |
| G2 | Leaked GitHub PATs in git history | HIGH | Working tree clean + scanner gate proven; **Owner** (rotate PAT + history rewrite/force-push) |
| G3 | CI red: WASM integrity + pip-audit-local | ✅ **FIXED & PROVEN** | confirm on next CI run |
| G10 | Legal data provenance chain | 🟡 runtime chain PROVEN (provenance + retrieval + CitationGuard fail-closed); embeddings=0 + fresh 007a–d pending | **Agent-actionable** |

## Open (non-blocking)

G4 worker stub · G5 document_service GET 501 · G6 client XSS sweep · G7 non-home UI verify · G8 10k load test · G9 live corpus reconfirm (after G1).

---

## Solid (do not regress)

- LOCAL OLLAMA ONLY enforced — 30 policy/sovereign tests green.
- 8 real+wired services; 7/8 live HTTP 200.
- Rules-first, fail-closed retrieval; CitationGuard vs real corpus UUIDs; no hardcoded legal values.
- Security suite: 134 passed. Ownership + payment integrity + PII de-id.
- Professional home UI live. docker compose valid. build-images CI green.

---

## Task ledger

| Task | State |
|---|---|
| 001-current-state-freeze-and-status | ✅ done → REJECT verdict (in `review/`) |
| 007a-uk-employment-law-source-fetch-plan | 📋 backlog |
| 007b-uk-employment-law-source-fetch-proof | 📋 backlog |
| 007c-legal-data-engineering-transform-proof | 📋 backlog |
| 007d-rag-index-and-citationguard-proof | 📋 backlog |

---

## Data pipeline acceptance rule (binding)

No legal-data task is accepted unless it passes the full chain:

`source URL → HTTP fetch proof → raw content hash → raw source record → parsed legal row → corpus_chunk → embedding/index → retrieval result → CitationGuard real UUID validation`

`qa-release-gatekeeper` **must reject** any ingestion claim that skips a stage.

Delegation sequence for legal data work:
`uk-employment-law-scraper-agent → legal-data-engineer-agent → db-rag-ingestion-agent → ai-brain-citationguard-agent → qa-release-gatekeeper`

---

## Next

1. **Owner:** reconcile live DB password (G1) → unblocks 8/8 smoke + G9.
2. **Agent:** repair CI gates (G3); draft history-scrub plan (G2).
3. **Agent:** execute 007a–007d legal-data provenance chain (G10).
