#!/usr/bin/env bash
# lawapp Stripe Configuration Gate
# Validates Stripe keys are real before enabling live payments.
# Usage: bash scripts/gate-stripe.sh [--test|--live]
# Returns: 0 if Stripe is properly configured, 1 otherwise

set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

MODE="${1:---test}"

echo "=== lawapp Stripe Gate ($MODE) ==="

SECRET_KEY="${STRIPE_SECRET_KEY:-}"
PUBLIC_KEY="${STRIPE_PUBLIC_KEY:-}"
WEBHOOK_SECRET="${STRIPE_WEBHOOK_SECRET:-}"

FAIL=0

# Check STRIPE_SECRET_KEY
if [ -z "$SECRET_KEY" ] || echo "$SECRET_KEY" | grep -qE "placeholder|YOUR_KEY|PLACEHOLDER"; then
  echo "FAIL: STRIPE_SECRET_KEY is not set or is a placeholder."
  FAIL=1
else
  if [ "$MODE" = "--live" ]; then
    if ! echo "$SECRET_KEY" | grep -q "sk_live_"; then
      echo "FAIL: STRIPE_SECRET_KEY must start with sk_live_ for live mode."
      FAIL=1
    else
      echo "PASS: STRIPE_SECRET_KEY is a live key."
    fi
  else
    if ! echo "$SECRET_KEY" | grep -qE "sk_test_|sk_live_"; then
      echo "FAIL: STRIPE_SECRET_KEY must start with sk_test_ or sk_live_."
      FAIL=1
    else
      echo "PASS: STRIPE_SECRET_KEY is set (test/live format)."
    fi
  fi
fi

# Check STRIPE_WEBHOOK_SECRET
if [ -z "$WEBHOOK_SECRET" ] || echo "$WEBHOOK_SECRET" | grep -qE "placeholder|whsec_PLACEHOLDER"; then
  echo "FAIL: STRIPE_WEBHOOK_SECRET is not set or is a placeholder."
  FAIL=1
else
  if ! echo "$WEBHOOK_SECRET" | grep -q "whsec_"; then
    echo "WARN: STRIPE_WEBHOOK_SECRET does not start with whsec_ — may be invalid."
  else
    echo "PASS: STRIPE_WEBHOOK_SECRET is set."
  fi
fi

# Check payment mode
PAYMENT_MODE="${PAYMENT_MODE:-}"
if [ "$MODE" = "--live" ] && [ "$PAYMENT_MODE" != "stripe_live" ]; then
  echo "FAIL: PAYMENT_MODE must be 'stripe_live' for live payments. Current: $PAYMENT_MODE"
  FAIL=1
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "GATE PASSED — Stripe appears configured."
  echo ""
  echo "To apply in Docker:"
  echo "  Add to .env:  PAYMENT_MODE=stripe_test (or stripe_live)"
  echo "  Restart:      docker compose up -d --force-recreate backend"
  echo "  Verify:       curl http://localhost:8000/api/payment/status | jq ."
  exit 0
else
  echo "GATE FAILED — Stripe not properly configured."
  echo ""
  echo "Required environment variables:"
  echo "  STRIPE_SECRET_KEY=sk_test_YOUR_KEY   (from Stripe dashboard)"
  echo "  STRIPE_WEBHOOK_SECRET=whsec_YOUR_KEY  (from Stripe webhook settings)"
  echo "  STRIPE_PUBLIC_KEY=pk_test_YOUR_KEY"
  echo "  PAYMENT_MODE=stripe_test"
  exit 1
fi
