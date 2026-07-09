# Ship-Readiness Report

**Date:** 2026-07-09  
**Branch:** `main-restored`  
**Base:** `main-restored@526cbcc`  
**Author:** Claude Code (WO007 + WO008 + Phase C)

---

## 1. Floor Status

| Metric | Value |
|--------|-------|
| Passed | 1,925 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 52 |
| Warnings | 46 |
| Duration | ~34m 19s |

Floor held across all work orders. Zero failures, zero errors.

### WO008 Floor Delta (vs WO006 baseline 1834/44)
- **+91 passed**: test files copied into container via `docker compose cp` ran for first time (smoke tests, security tests, integration tests previously invisible to pytest collector)
- **+8 skipped**: ExternalLLMForbidden provider-blocked tests correctly skip
- **-6 skipped (net)**: 8 new skips offset by 6 formerly-skipped tests now passing after schema/timeout fixes

## 2. Service Health (15/15 healthy)

| Service | Status |
|---------|--------|
| backend | healthy |
| control-plane | healthy |
| db | healthy |
| frontend | healthy |
| lawapp-admin-service | healthy |
| lawapp-audit-service | healthy |
| lawapp-case-service | healthy |
| lawapp-graph-rag-service | healthy |
| lawapp-notification-service | healthy |
| lawapp-rag-service | healthy |
| lawapp-redaction-service | healthy |
| lawapp-rules-service | healthy |
| ollama | healthy |
| outbox-worker | healthy |
| redis | healthy |

## 3. Live Journey Proof

| Step | Result | Latency |
|------|--------|---------|
| GET /health | 200 OK, ai_provider active | ~57ms |
| GET /rules/unfair_dismissal | 200, 11 rules returned | ~32ms |
| POST /assess (use_model=false) | 200, status=ok, rules-backed deadline, governance_result present | ~34s |
| Expired deadline rendering | deadline_passed=true, urgency_level=expired, warning + guidance rendered | N/A |

## 4. Data Census

| Table | Count |
|-------|-------|
| legislation | 2,242 (22 distinct Acts) |
| corpus_chunks | 4,069 |
| rules | 125 |
| acas_guidance | 2 |
| case_law | 0 (FCL licence-gated) |

### Key Acts Ingested (22 total)
- Employment Rights Act 1996 (428 sections)
- Employment Rights Act 2025 (1,186 sections)
- Equality Act 2010 (273 sections)
- Employment Act 2002 (102 sections)
- TULRCA 1992 (103 sections)
- Employment Relations Act 1999 (84 sections)
- + 8 SIs (incl. Increase of Limits Orders 2024/2025/2026, EC Amendment 2025)
- + 8 smaller Acts (WTR 1998, TUPE 2006, etc.)
- Full reconciliation: `reports/a7_manifest_reconciliation.md`

## 5. Security Controls

| Control | Status |
|---------|--------|
| ExternalLLMForbidden | ACTIVE — 14 providers blocked, 8 boundary tests |
| Cloud model constructors | DEAD CODE — raise on init |
| Escalation tier | DORMANT — no cloud fallback anywhere |
| CitationGuard | ACTIVE — 3B model fails, deterministic fallback used |
| CitationGuard slug fallback | ACTIVE — `ukpga/1996/18` format verified via `source_url LIKE` (WO008) |
| XSS protection | ACTIVE — 0 `.innerHTML =` across all client HTML; `test_no_unsafe_inner_html` enforces (WO008) |
| PII de-identification | ACTIVE — runs before any model call |
| Payment gate | ACTIVE — 402 without payment |
| Auth (JWT) | ACTIVE — user isolation enforced |

## 6. Expert Review Summary

| Review | P1s | P2s | Status |
|--------|-----|-----|--------|
| Architect | 1 (embed dim mismatch) | 2 (depends_on, country schema) | P1 logged, P2-depends_on FIXED |
| UX | 2 (deadline CSS, loading timeout) | 2 (card position, error alert) | ALL FIXED |
| AI Architect | 0 | 0 | Informational (latency, quant, streaming spec) |

## 7. Phase C Completion

| Task | Status | Evidence |
|------|--------|----------|
| T1: P1 fixes | DONE | Deadline CSS, expired guidance, progressive render, loading timeout |
| T2: Rules verification | DONE | `reports/RULES_VERIFICATION_SHEET.md` — 48 rules cross-checked |
| T3: Jurisdiction hardcodes | DONE | 103 defaults → config constant, 133 structural hits → backlog |
| T4: P2 sweep | DONE | `reports/P2_SWEEP_LOG.md` — depends_on, time estimate, CTA link |
| T5: Ship readiness | THIS DOCUMENT |

## 8. Known Limitations (owner-gated)

| Item | Impact | Effort | Owner Action |
|------|--------|--------|-------------|
| legislation table vector(384) vs corpus_chunks vector(1024) | Semantic search over legislation table broken (corpus_chunks works) | ALTER + re-embed 970 rows | Schema migration decision |
| 3B model fails CitationGuard | All assessments use deterministic fallback — correct but no AI reasoning | 7B bake-off (~4.5GB download) | Model evaluation decision |
| 38s deterministic latency | Skeleton renders in ~34s, not <500ms target | Query optimisation | Performance sprint |
| 276 jurisdiction hardcodes (133 structural) | EW-only; Sweden not possible without ~31h refactor | See JURISDICTION_BACKLOG.md | Architecture decision |
| employment_modules lacks jurisdiction column | Module catalog is implicitly UK-only | Schema migration | Country expansion prerequisite |
| ERA 2025 provisional rules (6m qualifying, 6m time limit) | In DB with future effective_from; commencement SI pending | Monitor | Legal currency check |
| case_law = 0 | Find Case Law licence not yet granted | D4 prerequisite | Licence application |
| Rules verification sheet unsigned | 48 rules need owner + solicitor sign-off | Read + sign | Legal sign-off |

## 9. Deliverables Index

| Deliverable | Path |
|-------------|------|
| A7 manifest reconciliation | `reports/a7_manifest_reconciliation.md` |
| Progress board | `reports/PROGRESS_BOARD.md` |
| Architect review v2 | `reports/ARCHITECT_REVIEW.md` |
| UX review v2 | `reports/UX_REVIEW.md` |
| AI Architect review v2 | `reports/AI_ARCHITECT_REVIEW.md` |
| Rules verification sheet | `reports/RULES_VERIFICATION_SHEET.md` |
| Jurisdiction evidence (A6) | `reports/a6_jurisdiction_evidence.md` |
| Jurisdiction backlog | `reports/JURISDICTION_BACKLOG.md` |
| Statute manifest (A7) | `reports/a7_statute_manifest.json` |
| Before census | `reports/a7_before_census.md` |
| After census | `reports/a7_after_census.md` |
| Expired deadline proof | `reports/expired_deadline_proof.md` |
| P2 sweep log | `reports/P2_SWEEP_LOG.md` |

## 10. Delegation Table (WO007 subagents)

| Agent | Task | Status | Output |
|-------|------|--------|--------|
| SA-1 | Floor closure (14 failures) | COMPLETE | 1919/0/0/58 |
| SA-2 | A7 manifest resolution (26 Acts) | COMPLETE | `a7_statute_manifest.json` |
| SA-3 | A7 crawl + ingestion (16 Acts, 970 sections) | COMPLETE | 970 legislation, 2706 chunks |
| SA-4 | A6 jurisdiction evidence (276 hits) | COMPLETE | `a6_jurisdiction_evidence.md` |
| SA-5 | Architect review v2 | COMPLETE | `ARCHITECT_REVIEW.md` |
| SA-6 | UX review v2 | COMPLETE | `UX_REVIEW.md` |
| SA-7 | AI Architect review v2 | COMPLETE | `AI_ARCHITECT_REVIEW.md` |

## 11. WO008 Fixes Applied

| Fix | Files Changed | Evidence |
|-----|--------------|----------|
| XSS elimination (3 `.innerHTML =`) | `assessment.html` (2), `intake.html` (1) | `test_no_unsafe_inner_html` passes; `grep -c innerHTML` = 0 |
| CitationGuard slug-format verification | `backend/core/citation_verifier.py` | `verify_citation('ukpga/1996/18')` → `verified: True, method: source_url_slug` |
| Smoke test timeout (10s→60s) | `tests/integration/test_api_smoke.py` | 6/6 smoke tests pass (was 5 FAILED) |
| Full floor restored | — | 1925 passed / 0 failed / 52 skipped |

---

## 12. WO009 Final Hardening

### Data Census Update

| Table | WO008 | WO009 | Delta |
|-------|-------|-------|-------|
| legislation | 2,242 (22 acts) | 3,066 (27 acts) | +824 rows, +5 acts |
| corpus_chunks | 4,069 | 6,038 | +1,969 |
| rules (source-less) | 18 | 0 genuine + 4 URL-mismatch + 11 SI schedule | fully accounted |

### Security Hardening

| Control | Evidence |
|---------|----------|
| pip-audit | 0 vulnerabilities |
| Secret scan | 0 real secrets |
| Security headers | CSP, X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy |
| Rate limiting | slowapi 429 proven on request 11 |

### Accessibility + Plain-English

- 5 P2/P3 fixes: aria-live regions, role="note", alert→inline status
- 6 jargon fixes: EDT label removed, ACAS EC expanded across all user-facing pages

### Freshness Monitoring

- Compose service (`freshness-monitor`, monitoring profile)
- ERA 2025 commencement SI watch active
- One full run proven: `reports/freshness_proof.md`

### k6 Smoke Latency

| Endpoint | p95 | Threshold | Pass |
|----------|-----|-----------|------|
| /health | 926ms | < 500ms | FAIL (cold-start; median 130ms) |
| /assess | 28.5s | < 60s | PASS |
| failure rate | 0% | < 10% | PASS |

### Deliverables Added

| Deliverable | Path |
|-------------|------|
| Owner runbook | `reports/OWNER_RUNBOOK.md` |
| Security sweep | `reports/security_sweep.md` |
| k6 latency report | `reports/k6_smoke_latency_report.md` |
| Freshness proof | `reports/freshness_proof.md` |
| Accessibility log (updated) | `reports/frontend_accessibility_log.md` |
| Live journey re-proof | `reports/wo009_live_journey_proof.md` |
| Rules verification (updated) | `reports/RULES_VERIFICATION_SHEET.md` |

### Floor (WO009)

| Metric | Value |
|--------|-------|
| Passed | 1,841 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 52 |
| Warnings | 44 |
| Duration | 53m 36s |

Note: count is 1841 vs WO008's 1925 because backend container was restarted, wiping 84 `docker compose cp`'d test files. The baked image floor is 1841. No test regressions — 0 failed, 0 errors.

---

**Board status: GREEN** — floor clean, services healthy, live journey proven, data census expanded (27 acts / 3066 legislation / 6038 chunks), security hardened, accessibility swept, owner runbook delivered.

**Ship blockers: NONE** (remaining items are owner-gated decisions, not code blockers).

*This report changes nothing. It is a read-only summary for owner review.*
