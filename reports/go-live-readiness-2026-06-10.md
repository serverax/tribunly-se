# LawApp Go-Live Readiness Report  -  2026-06-10

## Release Artifact (immutable)

- Branch: `release/lawapp-clean-snapshot`
- Commit: `970b95c60d1dbce57474a02909b22c5e9f7f75a0`
- Image: `ghcr.io/serverax/lawapp/backend:970b95c60d1dbce57474a02909b22c5e9f7f75a0`
- Digest: `ghcr.io/serverax/lawapp/backend@sha256:4aa2c83478cff2137fe7ed556de0b717ddae90643945fafb521ab05b2103da85`
- Published by the canonical workflow (`ci.yml` build-push), gated on the full
  test chain (integration regression → legal accuracy → rules verification).

## Gate Results (all on the exact release commit)

| Gate | Result | Evidence |
|---|---|---|
| Canonical CI (`lawapp CI  -  Test, Build, Push`) | PASS | run 27295129368 |
| Docker endpoint proof | PASS | run 27295129293 |
| Full Docker-backed pytest suite | PASS  -  1647 passed, 0 failed, 48 skipped | `reports/full-pytest-suite-result.md` |
| Legal accuracy gate | PASS (8 citations, grounding 1.0, rules-sourced deadline, out-of-scope refusal) | `scripts/run_legal_accuracy.py` |
| Rules verification gate | PASS  -  23 rules: 18 verified, 2 case-law-verified, 3 prospective-exempt, 0 failed | `scripts/check_rules_verification.py` |
| Ruff release gate (E9,F63,F7,F82 over backend/tests/ingestion/services/shared) | PASS | checked-in policy in `pyproject.toml` |
| Client XSS sweep | CLEAN  -  no `innerHTML` / `insertAdjacentHTML` / `document.write` in `client/public` | grep sweep |
| Secret scan (working tree) | CLEAN | `scripts/security/scan-secrets-history.sh` |
| Secret scan (git history) | **FAIL  -  owner action**: PAT patterns in 4 historical commits (3611c37, 6c5882e, a0968b0, e165295) | same script, `SCAN_HISTORY=1` |

## Code Defects Fixed (this release)

1. `client/public/pages/constructive_dismissal.html`  -  all dynamic `innerHTML`
   replaced with safe DOM construction; citation URLs validated (http/https only).
2. `backend/api/main.py`  -  `datetime.utcnow()` NameError in document generation;
   statutory caps now loaded from the rules table (fail closed; the hardcoded
   £123,543 cap is gone from app code); upload-dir failure no longer crashes the
   API at import (uploads fail closed with 503).
3. `backend/core/brain.py`  -  cost-governor return path uses real locals.
4. `backend/core/employment_assessment.py`  -  compensatory cap fails closed when
   the rule is missing; tribunal deadlines corrected to the statutory
   3-months-less-1-day rule (was overstating the deadline by one day).
5. `backend/domains/employment/compliance.py`  -  signoff file path fixed
   (was silently reporting un-reviewed state from the wrong path).
6. `Dockerfile.ingestion`  -  missing `stripe` dependency (made the canonical
   in-container suite collect and pass; it had been failing only in-container).

## Runtime / Cluster Repairs

- `ollama-inference` DaemonSet: PSA-compliant (emptyDir instead of hostPath),
  control-plane toleration (all-control-plane Talos cluster), working model
  preload hook. 2/3 pods Running with `qwen2.5:3b-instruct-q6_K` loaded
  (3rd pending on the full node  -  non-blocking, service has endpoints).
- `llm-inference-service` selector fixed (had 0 endpoints).
- `lawapp-reasoning-worker`: was a placeholder command crash-looping 822 times;
  now runs the real `backend.core.outbox_worker` daemon with the correct DB
  secret. Clean start confirmed.
- DB migrations applied to the spine DB (`lawapp-rag`) and staging DB
  (`iterlaw-ai`); `outbox_events` and later tables now exist.
- Staging `lawapp-secrets.DATABASE_URL` placeholder corrected.
- `iterlaw-ai` backend: writable upload volume + `LAWAPP_UPLOAD_DIR` set.
- `lawapp-api`/`lawapp-ai` set to `DEPLOYMENT_MODE=development` for the
  controlled-beta scope (the release image fail-closes `production` mode until
  real Stripe live + KMS config exists  -  see owner actions).

## Staging Proof (deployed artifact = release digest)

All four deployments run `backend:970b95c...` and are Ready:

- `iterlaw-ai/lawapp-backend`  -  /health ok, db connected, ollama_local active
- `lawapp-api/lawapp-backend`  -  /health 200 ok, /ready 200 ready
- `lawapp-ai/lawapp-brain`  -  full 19-step brain run: 23 trace steps,
  CitationGuard stage present, `final_status: ok`, `brain_traces` persisted
  (14 → 15), JWT register/login exercised end-to-end
- `lawapp-ai/lawapp-reasoning-worker`  -  outbox daemon running clean
- E2E product smoke (`/api/diagnosis`): claim_type=unfair_dismissal,
  deadline 2026-03-31 (3 months − 1 day from EDT 2026-01-01), `source=rules`,
  4 citations, `pii_in_output=[]`
- Public path via TLS ingress (`staging.lawapp.ai` host): /health and all
  primary frontend pages (/, intake, dashboard, constructive_dismissal) HTTP 200

## Release Path (canonical, consolidated)

- `ci.yml` is the single authoritative release workflow: tests → legal gates →
  build-push (immutable SHA tag; `latest` alias only on master; digest recorded).
- `deploy-staging.yml` refuses non-immutable tags (must be 40-char SHA or
  sha256 digest).
- Duplicate/stale workflows (`lawapp-ci`, `lawapp-ci-cd`, `build-images`,
  `lawapp-build-images`, `lawapp-deploy-talos`) deprecated to manual dispatch.

## OWNER-ONLY ACTIONS BEFORE PUBLIC LAUNCH

These cannot be completed by an agent and block public (not controlled-beta) launch:

1. **Rotate/revoke the historical GitHub PAT(s)** flagged by the history scan,
   then approve (or decline) a history rewrite + force-push. No rewrite has
   been performed.
2. **DPO review of the DPIA** (`docs/dpia-artefact.md`, checklist
   `docs/dpia-review-checklist.md`) → update `docs/compliance-signoff.json`
   with reviewer name/date/scope/evidence.
3. **Privacy/legal review + publication of the privacy notice**
   (`docs/privacy-notice-draft.md`) → same signoff file.
4. **DNS**: `staging.lawapp.ai` / production domain do not resolve publicly;
   create DNS records (ingress IPs 138.201.202.174 / 138.201.253.245) and
   confirm TLS certificate issuance for the final domain.
5. **Payment scope decision**: currently `stripe_test` (lawapp-api) /
   `disabled` (brain). Public paid launch requires live Stripe keys, webhook
   signature proof, and switching `DEPLOYMENT_MODE=production` (which then
   also requires `AWS_KMS_KEY_ARN` for `KEY_MANAGEMENT_MODE=aws_kms`).
6. **Production secrets hygiene**: `lawapp-postgres-secret` in `lawapp-api`
   contains a placeholder password (`PUT_...`)  -  set a real one and align the
   instance; remove stale `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` keys from
   `iterlaw-ai/lawapp-secrets` (local-Ollama-only policy; the code never reads
   them, but they should not exist).
7. **Cluster capacity**: node `talos-h93-b9x` is at its 110-pod limit and is
   the only untainted node; several dead pods from other tenants occupy slots.
   Clean up foreign namespaces or raise capacity.
8. **Backups/monitoring/retention**: confirm backup + restore proof and
   alerting for the chosen launch scope.

## Verdict

- **Controlled beta (payment disabled/test, staging domain): READY** once
  owner completes items 1–3 (secret rotation decision + compliance signoff)
  and item 4 (DNS)  -  everything technical is deployed and proven on the
  immutable release artifact.
- **Public production launch: NOT READY** until all owner actions above are
  complete (live payment + KMS + production mode + compliance + DNS/TLS).
