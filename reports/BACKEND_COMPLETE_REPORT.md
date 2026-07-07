# Backend Complete Report

Generated: 2026-07-07
Branch: `codex/backend-complete`

## Scope

This report captures the Stage 1 backend completion evidence for Work Order 004:

- backend coverage audit and repair checkpoints
- isolated live-stack proof on a dedicated compose project (`lawapprestorebc`)
- automated backend journey regressions
- backend floor result on the current branch
- parked hard-stop items that remain owner-visible

## Checkpoint Commits

- `e69061d` `fix(documents): route canonical paid drafts through legal templates`
- `b5f5409` `test(assessment): lock canonical deadline contract`
- `fd9e89f` `docs(security): park standalone uploads hard-stop finding`
- `e51f9bd` `test(e2e): codify backend paid journey`
- `9a0f0df` `fix(control-plane): return honest outage copy on retrieval failure`
- `9ca0855` `test(notifications): prove partner referral path is wired`

## Live Stack Proof

The live proof used an isolated compose project name and alternate host ports to avoid cross-project contamination from another local stack:

- project: `lawapprestorebc`
- backend: `http://localhost:8100`
- rules service: `http://localhost:8116`
- rag service: `http://localhost:8117`
- graph rag: `http://localhost:8118`
- redaction service: `http://localhost:8119`
- audit service: `http://localhost:8120`
- db host port: `5540`
- redis host port: `6381`
- ollama host port: `11435`

`docker compose -f docker-compose.yml -p lawapprestorebc ps` reached healthy status for:

- `backend`
- `db`
- `redis`
- `lawapp-rules-service`
- `lawapp-rag-service`
- `lawapp-graph-rag-service`
- `lawapp-redaction-service`
- `lawapp-audit-service`
- `lawapp-case-service`
- `lawapp-admin-service`
- `lawapp-notification-service`
- `outbox-worker`

Additional health evidence:

- backend `GET /health` returned `status=ok`, `db=connected`
- rag service `GET /health` returned `status=ok`
- graph rag `GET /health` returned `status=ok`
- redaction service `GET /health` returned `status=ok`
- redis `redis-cli ping` returned `PONG`
- db `pg_isready -U lawapp -d lawapp` returned `accepting connections`
- isolated `ollama` profile container reached healthy status

## Route Evidence

### Assessment / retrieval

Live `POST /assess` on the isolated backend returned:

- `status: ok`
- `claim_type: unfair_dismissal`
- `jurisdiction: EW`
- canonical `deadline.source: rules`
- `citations`: populated and URL-backed
- `key_weaknesses`: populated

Live `GET /rules/unfair_dismissal` returned the expected rule rows, including:

- `unfair_dismissal.time_limit_months`
- `unfair_dismissal.qualifying_period`
- `unfair_dismissal.compensatory_cap_amount`
- `unfair_dismissal.weeks_pay_cap_amount`

### Payment / documents

Live authenticated `POST /api/documents/generate` on an unpaid saved case returned:

- HTTP `402`
- detail: `Payment required to generate documents`

Automated backend E2E proof (`tests/e2e/test_backend_paid_journey.py`) then proved:

- 402 gate before payment
- deterministic test-mode checkout session creation
- idempotent confirm-test payment
- unlocked paid generation for the paid case
- second case remains locked
- generated Particulars and Schedule downloads contain template markers and cited content

### Honesty / outage copy

`tests/integration/test_outage_copy.py` now proves that retrieval/rules failure returns:

- `status: temporarily_unavailable`
- user-facing copy containing `temporarily unavailable`
- user-facing copy containing `try again`
- never `not_supported`

### Price consistency

Evidence now covers all three surfaces:

- backend config: `backend/api/payment_routes.py:85` => `2999`
- homepage: `client/public/index.html` => `£29.99`
- assessment page: `client/public/pages/assessment.html` => `Unlock Full Documents (£29.99)`

`tests/test_beta_blockers.py -k pricing_consistent_across_surfaces` passed.

## Automated Proof Summary

- `tests/integration/test_canonical_paid_documents.py` => `2 passed`
- `tests/integration/test_assessment_contract_deadline.py` => `2 passed`
- `tests/e2e/test_backend_paid_journey.py` => `1 passed`
- `tests/integration/test_outage_copy.py` => `1 passed`
- `tests/services/test_notification_partner_referral.py` => `1 passed`
- `tests/integration/test_beta_handoff_route_fenced.py` + `tests/integration/test_phase3d_paid_handoff.py -k handoff` => `23 passed`
- `tests/test_beta_blockers.py -k pricing_consistent_across_surfaces` => `1 passed`
- `tests/integration/test_api_smoke.py` (isolated live stack) => `6 passed`

## Coverage Matrix Outcome

Current Stage 1 matrix state:

- partner-referral notifications are now proven `WIRED` against the registry-backed queue path
- beta handoff lead capture is now `FENCED` by default unless an explicit owner override is set
- the matrix now reads `STUB=0` and `BROKEN=0`

Service inventory notes retained in the matrix:

- `lawapp-citation-guard` remains listed as `ORPHAN`
- `lawapp-ingestion-worker` remains listed as `ORPHAN`

These were listed, not deleted, per the audit rule.

## Backend Floor

Full branch floor on the current backend-complete branch:

- `1824 passed, 63 skipped, 6 warnings in 532.16s (0:08:52)`

This meets the branch floor requirement of `>= 1824 passed / 0 failed`.
