#!/usr/bin/env bash
# prove_openrouter_workflow_c.sh  -  proves the Workflow C OpenRouter provider plug
# and the 4 AIA validators WITHOUT a real key (mocked/stub). Exits non-zero on
# any failure. No secret is printed; no network call is made.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
docker compose exec -T db psql -U lawapp -d lawapp -c "ALTER USER lawapp PASSWORD 'lawapp';" >/dev/null 2>&1
fail=0

echo "########## OpenRouter provider plug + 4 AIA validators (mocked) ##########"
docker compose run --rm -e POSTGRES_PASSWORD=lawapp ingestion python -m pytest -q \
  tests/test_openrouter_provider.py \
  tests/test_openrouter_config.py \
  tests/test_agent_pii_boundary.py \
  tests/test_agents_schema_validation.py \
  || fail=1

echo "########## provider is a plug, NOT hardwired (single gateway) ##########"
# Workflow C imports the provider interface, not litellm directly.
if grep -rn "import litellm" backend --include=*.py | grep -v "agentic/litellm_adapter.py" | grep -v "llm_provider.py" | grep -q .; then
  echo "FAIL: litellm imported outside the single adapter/provider"; fail=1
else
  echo "PASS: litellm only imported by the adapter/provider plug"
fi

echo "########## no real OpenRouter key committed ##########"
if grep -rnE "sk-or-v1-[0-9a-fA-F]{20,}" backend client config db scripts ingestion .github 2>/dev/null | grep -q .; then
  echo "FAIL: a real OpenRouter key is present in tracked files"; fail=1
else
  echo "PASS: no real OpenRouter key in tracked files"
fi

if [ "$fail" -ne 0 ]; then echo "OPENROUTER WORKFLOW C PROOF: FAILED"; exit 1; fi
echo "OPENROUTER WORKFLOW C PROOF: PASSED"
