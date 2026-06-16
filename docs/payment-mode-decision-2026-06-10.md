# Payment Mode Decision  -  2026-06-10

**Decision: Option B  -  paid launch formally disabled. Free-beta-only mode.**

## What was changed

- `lawapp-api` ConfigMap `lawapp-config`: `PAYMENT_MODE` changed
  `stripe_test` → `disabled`; backend restarted and verified
  (`/health` reports `payment_mode: disabled`).
- `iterlaw-ai` staging was already `disabled`  -  unchanged.

## What this means

- No checkout session can be created; document generation behind payment
  returns `payment_required: true` with the unavailable message (fail closed).
- No Stripe keys (test or live) are configured anywhere in the runtime.
- The production startup gate (`backend/core/config_validation.py`)
  intentionally refuses `DEPLOYMENT_MODE=production` without live Stripe  - 
  so production mode remains blocked BY DESIGN under this decision. The
  controlled-beta deployments run `DEPLOYMENT_MODE=development`, which is the
  supported mode for payment-disabled operation.
- The production boot path itself is proven: the release image
  (`970b95c…`) boots cleanly with `DEPLOYMENT_MODE=production` when given the
  full production env (jwt auth, kms_stub + KMS_KEY_ID, Stripe env set)  - 
  verified locally on 2026-06-10. Switching to production for a paid public
  launch requires only real values: live `STRIPE_SECRET_KEY` +
  `STRIPE_WEBHOOK_SECRET`, and a real KMS key (`AWS_KMS_KEY_ARN`) or the
  accepted `kms_stub` + `KMS_KEY_ID` interim.

## Reversal procedure (owner)

1. Obtain live Stripe keys; set `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
   in `lawapp-secrets`.
2. Set `PAYMENT_MODE=stripe_live`, `DEPLOYMENT_MODE=production`,
   `KEY_MANAGEMENT_MODE` + key config.
3. Prove webhook signature verification and a full payment round-trip in
   Stripe test mode first, then run the payment access tests.
