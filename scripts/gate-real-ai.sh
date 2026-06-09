#!/usr/bin/env bash
# lawapp Real AI Configuration Gate
# Validates ANTHROPIC_API_KEY is a real key (not placeholder) before enabling AI reasoning.
# Usage: bash scripts/gate-real-ai.sh
# Returns: 0 if real AI can be used, 1 if key is absent/placeholder

set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

API_KEY="${ANTHROPIC_API_KEY:-}"

echo "=== lawapp Real AI Gate ==="
echo "Checking ANTHROPIC_API_KEY..."

if [ -z "$API_KEY" ]; then
  echo "FAIL: ANTHROPIC_API_KEY is not set."
  echo "To enable real AI reasoning:"
  echo "  export ANTHROPIC_API_KEY=sk-ant-YOUR_REAL_KEY"
  echo "  Then restart the backend."
  exit 1
fi

if echo "$API_KEY" | grep -qE "^(placeholder|changeme|sk-ant-placeholder|your_key|YOUR_REAL_KEY)$"; then
  echo "FAIL: ANTHROPIC_API_KEY is a placeholder value."
  echo "Current value pattern: ${API_KEY:0:10}..."
  echo "Set a real Anthropic API key to enable AI reasoning."
  exit 1
fi

if ! echo "$API_KEY" | grep -qE "^sk-ant-"; then
  echo "WARN: Key does not match expected Anthropic format (sk-ant-...)."
  echo "Proceeding but verification may fail."
fi

echo "PASS: ANTHROPIC_API_KEY appears to be a real key."
echo "Testing connection..."

python -c "
import os, sys
os.environ['ANTHROPIC_API_KEY'] = '${API_KEY}'
try:
    import anthropic
    client = anthropic.Anthropic(api_key='${API_KEY}')
    # Minimal test to verify the key format (not a real API call)
    print('PASS: Anthropic SDK loaded successfully.')
    print('NOTE: Full validation requires an actual API call (billed).')
    print('To test the full chain: POST /api/brain/trace with real facts.')
    sys.exit(0)
except ImportError:
    print('FAIL: anthropic package not installed.')
    sys.exit(1)
except Exception as e:
    print(f'FAIL: {e}')
    sys.exit(1)
" 2>&1

echo ""
echo "To activate real AI in Docker:"
echo "  1. Add to .env:  ANTHROPIC_API_KEY=sk-ant-YOUR_KEY"
echo "  2. Restart:      docker compose up -d --force-recreate backend"
echo "  3. Verify:       curl http://localhost:8000/health | jq .ai_provider"
