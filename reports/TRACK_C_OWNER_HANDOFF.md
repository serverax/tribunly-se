# Track C — Owner handoff (prepare only, DO NOT EXECUTE)

Prepared: 2026-06-15 after Track B on `release/lawapp-clean-snapshot`

## G2 — PAT / credential rotation
1. Owner revokes any leaked PAT documented in prior security reports (G2).
2. Rotate GitHub PAT used by CI/autopush; update GitHub Actions secrets only via owner.
3. Re-run secret scan: `rg` + trufflehog on clean tree; artifact in reports/.
4. Agent rule: never print, commit, or rotate live secrets autonomously.

## Production secrets
1. Provision production `.env` / K8s secrets: JWT_SECRET, ENCRYPTION_KEY, ADMIN_API_KEY, POSTGRES_PASSWORD, STRIPE_* (live).
2. Set PAYMENT_MODE=stripe_live only after webhook endpoint verified.
3. Disable LAWAPP_AUTH_MODE=none in production.
4. Verify no placeholder-dev-key values in prod manifests.

## K8s deploy
1. Build/push monolith image from release branch (not main until owner approves).
2. Apply Talos manifests; verify all lawapp-* pods Ready + health endpoints.
3. Run smoke: `/health`, `/api/rag/hybrid-search`, `/api/brain/trace`, auth-gated `/cases`.
4. Confirm Ollama inference service DNS resolves inside cluster.

## Stripe live
1. Create live webhook pointing to `/api/payment/webhook` (signature verification mandatory).
2. Run test-mode checkout proof first; then single live £1 test with immediate refund (owner).
3. Verify entitlement gate cannot be bypassed (security-auth-payment-agent checklist).

## Backup / restore drill
1. Owner runs pg_dump from production RDS/Postgres on maintenance window.
2. Restore to isolated staging cluster; verify corpus_chunks count + rules row counts match.
3. Do NOT execute against production from agent sessions — runbook only.

## Marketing sign-off
1. Product/legal review of landing copy, beta scope notice (11 topics), disclaimers.
2. Confirm partial/scope-cut modules are not advertised as covered.
3. Owner sign-off recorded before public launch.

## Entry criteria for Track C execution
- Track B completion report accepted
- Owner explicit approval for prod-touching steps
- GO_LIVE_MODE=production gate plan for 13 scope-cut modules (remain out of product OR promote individually)
