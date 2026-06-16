# Pre-Beta Operational Runbook

**lawapp  -  UK Employment Claim Co-Pilot**
**Phase:** 6E | Date: 2026-06-01
**Status:** CONTROLLED BETA NOT YET READY  -  see blockers below

---

## Current Status

Run `python scripts/check_beta_readiness.py` for the current readiness state.

Controlled beta requires ALL items in this runbook to be complete.
**Do not launch to real users until `controlled_beta_ready=true`.**

---

## Step 1  -  DPIA DPO Review [BLOCKED: human review required]

**Owner:** Data Protection Officer (DPO)
**Document:** `docs/dpia-artefact.md`
**Checklist:** `docs/dpia-review-checklist.md`

1. DPO reads `docs/dpia-artefact.md` in full
2. DPO works through every item in `docs/dpia-review-checklist.md`
3. DPO signs the checklist (physical or digital signature)
4. DPO updates `docs/compliance-signoff.json`:
   ```json
   "dpia": {
     "reviewed_by_dpo": true,
     "reviewer_name": "<DPO Full Name>",
     "review_date": "<YYYY-MM-DD>",
     "review_scope": "Full DPIA review per checklist v6D",
     "evidence_reference": "<Meeting note / file reference>"
   }
   ```
5. Commit the updated `compliance-signoff.json`
6. Verify: `GET /admin/compliance-status` shows `reviewed_by_dpo: true`

---

## Step 2  -  Privacy Notice Legal Review [BLOCKED: human review required]

**Owner:** Legal Counsel
**Document:** `docs/privacy-notice-draft.md`
**Checklist:** `docs/privacy-review-checklist.md`

1. Legal counsel reads `docs/privacy-notice-draft.md` in full
2. Legal works through every item in `docs/privacy-review-checklist.md`
3. Legal revises the notice as needed
4. Legal updates `docs/compliance-signoff.json`:
   ```json
   "privacy_notice": {
     "legally_reviewed": true,
     "reviewer_name": "<Lawyer Full Name>",
     "review_date": "<YYYY-MM-DD>",
     "review_scope": "Full privacy notice review per checklist v6D",
     "evidence_reference": "<Engagement letter / file reference>"
   }
   ```
5. Commit the updated `compliance-signoff.json`
6. Verify: `GET /admin/compliance-status` shows `legally_reviewed: true`

---

## Step 3  -  Configure Production Environment

**Owner:** Platform / DevOps
**Template:** `docs/env-production.template`

1. Copy `docs/env-production.template` to `.env` (never commit `.env`)
2. Fill in all `<REQUIRED: ...>` values:
   - `POSTGRES_PASSWORD`  -  strong random password
   - `ADMIN_API_KEY`  -  strong random string
   - `ENCRYPTION_KEY`  -  Fernet key (generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
   - `LAWAPP_AUTH_MODE=jwt`
   - `JWT_SECRET`  -  long random secret (`python -c "import secrets; print(secrets.token_urlsafe(64))"`)
   - `JWT_ISSUER`  -  your auth service URI
   - `JWT_AUDIENCE`  -  e.g. `lawapp-api`
   - `APP_BASE_URL`  -  your deployment URL
   - `ALLOWED_ORIGINS`  -  comma-separated allowed origins
   - `PAYMENT_MODE=disabled` (recommended for beta)
   - `DEPLOYMENT_MODE=production`
3. Verify startup: `docker compose up`  -  look for "Startup config OK" in logs

---

## Step 4  -  Run All Quality Gates

```bash
# Legal accuracy gate (mandatory)
python scripts/run_legal_accuracy.py

# Rules verification gate (mandatory)
python scripts/check_rules_verification.py

# Full integration regression
bash scripts/run_full_regression.sh

# Production readiness check
python scripts/check_beta_readiness.py
```

All must exit 0 before proceeding.

---

## Step 5  -  Verify Controlled Beta Ready

With production environment configured:

```bash
curl -H "X-Admin-Key: $ADMIN_API_KEY" \
  https://your-app-url/admin/production-readiness | jq .controlled_beta_ready
```

Expected: `true`

If `false`, check `controlled_beta_blockers` in the response for remaining items.

---

## Step 6  -  Controlled Beta Scope and Limits

Before launching:
- [ ] Define invited user list (controlled beta = invited users only)
- [ ] Confirm scope: unfair dismissal + unpaid wages, England and Wales only
- [ ] Confirm support contact for beta users
- [ ] Confirm monitoring/alerting is in place (Phase 7)
- [ ] Confirm no live payment is enabled (`PAYMENT_MODE=disabled` or `mock`)
- [ ] Confirm solicitor referral is local-only (no live partner integration)

---

## Step 7  -  Post-Launch Monitoring

- Monitor `/health` endpoint
- Monitor `GET /admin/production-readiness` for any status changes
- Monitor `GET /admin/retention-status` for data accumulation
- Run `scripts/run_retention.py --apply` periodically per retention policy

---

## Phase 7 Blockers (do not attempt in pre-beta)

These items remain blocked and are NOT required for controlled beta:
- JWKS/RS256 JWT verification
- Real HSM/KMS key management
- Full SAR (Subject Access Request) process
- Solicitor referral live integration
- Full OAuth/JWT user auth (beyond HS256)
- Stripe live payment

---
*Runbook version: 6E | Last updated: 2026-06-01*
