# LawApp  -  Repair Now List

**No shipping**  -  repairs before any deploy  
**Branch:** `release/lawapp-clean-snapshot` @ `12f835f`  
**Synthesized:** 2026-06-16 from check-in report, repair backlog, Track A/B/C completion, PROJECT_STATUS, and fresh read-only verification  
**Fresh verification (2026-06-16):** Docker **12/12 healthy**; `reports/legal_accuracy_track_b.txt` **not present** (beta gate uses StubReasoningModel  -  PASS in `reports/legal_accuracy_beta_cursor.txt`); latest k6 artifact **`reports/k6_100k_readiness_cursor.txt`  -  FAIL** (assess 94.48% `http_req_failed` @ 50 VU)

---

## P0  -  Blocks honest beta or CI

Honest beta means: no overstated coverage, no silent infra waivers, no stale operator docs, no unauthenticated mutating UI paths.

| ID | Area | Symptom | Root cause (if known) | Repair action | Acceptance criteria / test command | Artifact | Effort | Status |
|----|------|---------|------------------------|---------------|-----------------------------------|----------|--------|--------|
| **P0-001** | Load / rate limits | k6 assess path **FAIL** @ 50 VU | SlowAPI 30/min vs load | LAWAPP_LOAD_TEST_MODE + assess limit env | k6 assess tag thresholds (Docker) | `reports/k6_100k_readiness_post_repair.txt` | **M** | **PARTIAL** |
| **P0-002** | Local LLM / infra | Ollama unreachable in dev | cluster DNS default | compose profile + host.docker.internal + docs/ops/OLLAMA_LOCAL.md | streaming pytest PASS | `reports/ollama_local_proof.txt` | **M** | **PARTIAL** |
| **P0-003** | Legal accuracy honesty | stub-only PASS | StubReasoningModel default | `--live` profile on run_legal_accuracy.py | live PASS or OLLAMA_NOT_REACHABLE artifact | `reports/legal_accuracy_live.txt` | **M** | **PARTIAL** |
| **P0-004** | RAG corpus depth | Corpus **889 chunks** (881 embedded)  -  functional but **<<1000** stretch; 7 ACAS URLs **404** | Licensed-source-limited ingest; no fake rows for missing ACAS pages | Run legal-data pipeline for alternate ACAS URLs + legislation deltas; re-sync embeddings | DB: `corpus_chunks >= 1000`; hybrid-search `insufficient_grounding: false` on beta queries | `reports/rag_corpus_1000_proof.txt` | **L** | **OPEN** |
| **P0-005** | Frontend auth | `assessment.html` uses raw `fetch()` on mutating routes (`POST /cases`, payments, documents, handoff) - **not** `fetchWithAuth` | Mixed auth pattern; credentials-only may miss JWT | Wire all mutating calls through `LAWAPP_AUTH.fetchWithAuth`; add E2E for JWT mode | grep shows no raw `fetch` on protected POSTs; manual/E2E case create works in `auth_mode=jwt` | `reports/frontend_auth_wiring_proof.txt` | **S** | **FIXED** |
| **P0-006** | Operator docs | `tasks/PROJECT_STATUS.md` **stale** | Not updated after Track A+B | Rewrite PROJECT_STATUS from check-in facts | Doc HEAD matches `git rev-parse --short HEAD` | (doc update) | **S** | **FIXED** |
| **P0-007** | QA gate | No formal **qa-release-gatekeeper ACCEPT/REJECT** after Track A+B evidence pack | Gatekeeper pass not re-run on completion reports | Run source-command-qa-review / gatekeeper over Track A+B artifacts | Written ACCEPT or REJECT with cited commands | `docs/qa/GATEKEEPER_TRACK_AB_VERDICT.md` | **S** | **OPEN** |
| **P0-008** | Pytest waiver | Track A7 **PASS*** with Ollama streaming infra skip  -  full generative proof still waived | Host/container cannot reach chat model | Same as P0-002; treat waiver as **OPEN** until streaming test passes | `pytest tests/ -q` → 0 failed, streaming test **passed** (not skipped) | `reports/pytest_full_no_waivers.txt` | **M** | **OPEN** |

---

## P1  -  Blocks production readiness (engineering)

Engineering work the repo can do without owner prod credentials. Does **not** include deploy/secrets (Track C).

| ID | Area | Symptom | Root cause (if known) | Repair action | Acceptance criteria / test command | Artifact | Effort | Status |
|----|------|---------|------------------------|---------------|-----------------------------------|----------|--------|--------|
| **P1-001** | DB go-live gate | `GO_LIVE_MODE=production` **FAIL**  -  **13 modules** remain `partial` in DB catalogue | Scope-cut in product ≠ DB promotion; by design until legal-data pipeline completes per module | **Either** promote modules individually (rules+corpus+review) **or** change production gate to match permanent 11-topic product scope | `GO_LIVE_MODE=production bash scripts/proof/prove_database_integrity.sh` → **PASS** with documented policy | `reports/proof_database_integrity_production.txt` | **L** | **OPEN** |
| **P1-002** | Observability | OTEL **partial**: `POST /assess` with `use_model=false` does **not** persist `brain_traces`; full path via `/api/brain/trace` only | Assess shortcut bypasses Brain persistence | Route assess through Brain orchestrator or persist trace on all assess responses | Same `trace_id` in HTTP response + `brain_traces` row for `/assess` | `reports/otel_assess_trace_proof.txt` | **M** | **OPEN** |
| **P1-003** | Accessibility | a11y audit **PASS*** with **4 open findings** (A1–A4): nav aria-label, scope-cut page reachable, focus trap, wizard step SR | Audit-only in Track B6; fixes deferred | Fix A1–A4 in `client/public`; re-audit | Static + axe pass on intake/landing; constructive_dismissal banner or redirect | `reports/a11y_remediation_proof.txt` | **M** | **OPEN** |
| **P1-004** | Compose topology | **Not in compose:** citation-guard, ingestion-worker, LLM gateway, crawler  -  manifests exist only | Partial local stack vs K8s target architecture | Add compose profiles or document required sidecars; prove health wiring to monolith | Service map: each critical path **REAL+WIRED** or explicit STUB with fail-closed | `reports/service_map_compose_gap.txt` | **M** | **OPEN** |
| **P1-005** | Bootstrap / ingest | `db-bootstrap` image may lack `ingestion.sync_corpus_chunks` on fresh clone (QA-001 note: rebuild pending) | Bootstrap container exited on missing module in older image | Rebuild `db-bootstrap` + `ingestion` images; prove cold-start bootstrap | Fresh `docker compose up` → corpus >0 without manual ingest | `reports/bootstrap_cold_start_proof.txt` | **S** | **OPEN** |
| **P1-006** | ACAS ingest | **7/20** ACAS topic URLs returned **404** during Track B ingest | Source URLs moved or retired | Scraper finds replacement URLs; re-ingest; log HTTP status per URL | `track_b_acas_ingest.log` shows 0 skipped 404s **or** documented alternates | `reports/acas_404_remediation.log` | **M** | **OPEN** |
| **P1-007** | Rate-limit architecture | Production-scale assess blocked by **global 30/min** SlowAPI | Single bucket for anonymous assess under load | Separate tiers: anonymous vs authenticated; higher limits for entitled users; Redis-backed limiter | k6 with auth session passes assess thresholds at 50 VU | `reports/rate_limit_design.md` + k6 PASS | **L** | **OPEN** |
| **P1-008** | Docker pytest | Container **full suite run** not re-proven post–Track A (collect-only PASS: 1858, 0 import errors) | Track B relied on Track A baseline | `docker compose run --rm backend python -m pytest tests/ -q` | Exit 0; counts within ±5% of host suite | `reports/pytest_docker_full.txt` | **M** | **OPEN** |
| **P1-009** | Scope-cut UX | `constructive_dismissal.html` still reachable while module **scope-cut** (finding A2) | Static page not gated by beta-scope.js | Banner, redirect to intake, or remove from sitemap | Page shows scope-cut notice or 302 to intake | `reports/ui_scope_cut_pages_proof.txt` | **S** | **OPEN** |
| **P1-010** | Backlog doc drift | `docs/qa/CURSOR_REPAIR_BACKLOG.md` last updated **2026-06-14**  -  predates Track A/B fixes | Not reconciled with check-in | Merge statuses from check-in; close FIXED items; link this doc | Backlog table matches check-in P0/P1/P2 table | (doc update) | **S** | **OPEN** |

---

## P2  -  Important cleanup

Does not block controlled beta if P0 waivers are documented; required for maintainability and public launch polish.

| ID | Area | Symptom | Root cause (if known) | Repair action | Acceptance criteria / test command | Artifact | Effort | Status |
|----|------|---------|------------------------|---------------|-----------------------------------|----------|--------|--------|
| **P2-001** | Deprecation | `datetime.utcnow()` warnings across services (~30+ hits) | Legacy datetime API | Replace with `datetime.now(timezone.utc)` in hygiene PR | `pytest -W error::DeprecationWarning tests/ -q` clean for touched modules | `reports/datetime_utcnow_cleanup.txt` | **M** | **OPEN** |
| **P2-002** | Architecture | Dual trees `services/` vs `backend/services/`  -  operator confusion | Historical refactor incomplete | Publish ownership matrix **or** consolidate to single tree | `docs/architecture/SERVICE_TREE.md` + service-map skill output | `reports/service_tree_matrix.md` | **M** | **OPEN** |
| **P2-003** | Ops docs | Alembic expected by operators but project uses SQL migrations | Never adopted Alembic | Runbook section in ops guide (QA-008 DOCUMENTED → formalize) | No alembic upgrade attempts in onboarding | `docs/ops/MIGRATIONS.md` | **S** | **OPEN** |
| **P2-004** | Ops docs | psql proof scripts inconsistently documented (backend vs db container) | Mixed docs | Standardize all proof on `docker compose exec -T db psql` | grep proof scripts → all use `db` service | (code/doc PR) | **S** | **OPEN** |
| **P2-005** | DB config | Intermittent password mismatch (`.env` vs volume init)  -  MITIGATED not eliminated | Multiple password sources | Single documented password source + startup connect probe in README | Fresh clone compose up without manual override | `docs/ops/LOCAL_DB.md` | **S** | **OPEN** |
| **P2-006** | OCR test | Track A noted transient OCR integration failure (fixed in report)  -  not re-verified in Track B | One-off assert fix | Re-run targeted test in CI | `pytest backend/tests/test_upload_ocr_integration.py -q` → PASS | (existing pytest log) | **S** | **OPEN** |
| **P2-007** | Evidence hygiene | Multiple overlapping report filenames (`*_cursor.txt`, pre/post commit)  -  hard to find canonical | Ad-hoc recovery session naming | Add `reports/EVIDENCE_INDEX.md` pointer table | Index lists canonical artifact per gate | `reports/EVIDENCE_INDEX.md` | **S** | **OPEN** |
| **P2-008** | Merge readiness | Branch not on `main`; merge blocked until gates + owner approval | Release branch workflow | Owner decision doc after P0/P1 + gatekeeper ACCEPT | PR to main with checklist | (PR) | **S** | **OPEN** |

---

## Owner-only (Track C)  -  NOT autonomous

**Do not execute from agent sessions.** Prepare runbooks only; owner explicit approval required.

| ID | Area | Symptom | Root cause (if known) | Repair action | Acceptance criteria / test command | Artifact | Effort | Status |
|----|------|---------|------------------------|---------------|-----------------------------------|----------|--------|--------|
| **C-001** | Secrets / G2 | Leaked PAT rotation **NOT EXECUTED** | Prior security report G2 | Owner revokes PAT; rotate CI secrets; re-scan tree | Secret scan clean; CI green | `reports/secret_scan_post_rotation.txt` | **S** | **OPEN**  -  **OWNER** |
| **C-002** | Secrets | Production secrets unprovisioned (JWT, ENCRYPTION_KEY, ADMIN_API_KEY, Stripe live) | Dev keys in local override only | Owner provisions vault/K8s secrets; no placeholder dev keys in prod manifests | Deploy with prod secrets; health ok | K8s secret manifest (redacted) | **M** | **OPEN**  -  **OWNER** |
| **C-003** | K8s deploy | Production deploy **unproven**  -  manifests only, no live pod/ingress/TLS | No cluster access in engineering sessions | Owner: build/push image; Talos apply; smoke `/health`, RAG, brain trace, auth | All `lawapp-*` pods Ready; ingress TLS | `reports/k8s_smoke_proof.txt` | **L** | **OPEN**  -  **OWNER** |
| **C-004** | Payments | Stripe **live** webhook unproven  -  compose uses test mode | Owner-only live keys | Live webhook + £1 test + refund; entitlement bypass negative tests | Webhook signature verified; no bypass | `reports/stripe_live_proof.txt` | **M** | **OPEN**  -  **OWNER** |
| **C-005** | DR | Backup/restore drill **NOT EXECUTED** | No staging restore evidence | Owner: pg_dump prod; restore isolated; verify row counts | corpus_chunks + rules counts match | `reports/backup_restore_drill.txt` | **M** | **OPEN**  -  **OWNER** |
| **C-006** | Product / legal | Marketing/legal sign-off **pending** | Beta scope copy not owner-signed | Owner review: 11-topic notice, disclaimers, no false coverage claims | Signed approval recorded | `docs/product/BETA_SIGNOFF.md` | **S** | **OPEN**  -  **OWNER** |
| **C-007** | Load (prod) | k6 assess fail may need **prod rate-limit policy** not just test env | SlowAPI + ingress limits in prod unknown | Owner + platform: set prod limits; optional WAF/rate rules | Staging k6 PASS under prod-like limits | `reports/k6_staging_post_track_c.txt` | **M** | **OPEN**  -  **OWNER** |

---

## Waivers in force (do not treat as PASS)

| Waiver | Track | Expires when |
|--------|-------|--------------|
| Ollama streaming test skip | A7 | P0-002 / P0-008 closed |
| RAG 889 vs 1000 | B1 | P0-004 closed or scope explicitly reduced |
| k6 assess 94% fail @ 50 VU | B3 | P0-001 / P1-007 / C-007 closed |
| a11y A1–A4 audit-only | B6 | P1-003 closed |
| 13 DB-partial modules (product scope-cut) | B2 | P1-001 policy decided |
| Legal accuracy stub-only PASS | A8 | P0-003 closed |

---

## Suggested repair order (engineering only)

1. **P0-006**  -  Fix stale PROJECT_STATUS (15 min, unblocks everyone)  
2. **P0-005**  -  Frontend auth wiring (honest JWT beta)  
3. **P0-001 + P1-007**  -  k6 / rate-limit profile (paired)  
4. **P0-002 + P0-003 + P0-008**  -  Ollama local + live legal accuracy + streaming pytest  
5. **P0-007**  -  Gatekeeper verdict on Track A+B  
6. **P1-002**  -  Assess → brain_traces persistence  
7. **P1-003 + P1-009**  -  a11y + scope-cut pages  
8. **P0-004 + P1-006**  -  Corpus expansion + ACAS 404s  
9. **P1-001**  -  Production DB gate policy (promote vs gate rule)  
10. **P1-004 + P1-005 + P1-008**  -  Compose/bootstrap/docker pytest parity  

Track C (**C-001–C-007**): owner executes only after engineering P0/P1 and explicit approval.

---

## Source documents

| Path | Role |
|------|------|
| `docs/qa/CURSOR_CHECKIN_REPORT.md` | Primary synthesis (2026-06-15) |
| `docs/qa/CURSOR_REPAIR_BACKLOG.md` | Legacy backlog (needs P1-010 merge) |
| `reports/TRACK_A_BETA_FINISH_COMPLETION.md` | Track A DoD |
| `reports/TRACK_B_COMPLETION.md` | Track B DoD |
| `reports/TRACK_C_OWNER_HANDOFF.md` | Owner runbook |
| `tasks/PROJECT_STATUS.md` | **Stale**  -  superseded by check-in until P0-006 |

---

*Honest status: controlled beta is **GO WITH RISK** per Track A+B with documented waivers. Public production is **NO-GO**. This list is repair-only  -  no deploy, no secret rotation, no shipping.*

