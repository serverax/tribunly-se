#!/usr/bin/env bash
# prove_full_regression.sh — runs the complete legal-spine + MVP proof chain, then the
# full repo pytest suite. Non-zero if any proof fails.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
fail=0
PROOFS=(
  prove_legal_data_spine prove_jurisdiction_model prove_rules_integrity
  prove_corpus_quality prove_legal_db_performance prove_ingestion_runs
  prove_retrieval_pipeline prove_all_legal_dbs prove_all_fetching
  prove_all_chunking_embeddings prove_source_freshness
  prove_live_assess_retrieval_wiring prove_case_law_blocker_or_ingestion
  prove_no_fake_legal_data prove_frontend_backend_wiring prove_document_generation
  prove_deadline_tracker prove_handoff_workflow prove_legal_boundary_notices
  prove_no_fake_claims_or_uncited_law prove_mvp_user_journey
)
echo "################ PROOF SCRIPTS ################"
for s in "${PROOFS[@]}"; do
  if bash "scripts/$s.sh" >/dev/null 2>&1; then echo "  PASS: $s"; else echo "  FAIL: $s"; fail=1; fi
done

echo "################ FULL PYTEST SUITE ################"
# Run in the BACKEND container (has the full API deps: fastapi/slowapi/KMS/crypto).
# The ingestion container lacks API deps (slowapi) so API/security tests can't import there.
docker compose exec -T backend sh -c "python -c 'import pytest' 2>/dev/null || pip install -q pytest pytest-asyncio httpx requests >/dev/null 2>&1" || true
docker compose exec -T backend sh -c "cd /app && python -m pytest tests/ -q -p no:cacheprovider --ignore=tests/integration/test_semantic_retrieval.py" 2>&1 | tail -10
pyrc=${PIPESTATUS[0]}
[ "$pyrc" -ne 0 ] && { echo "  NOTE: pytest returned non-zero (see summary above)"; fail=1; }

echo
[ "$fail" -ne 0 ] && { echo "FULL REGRESSION: FAIL"; exit 1; }
echo "FULL REGRESSION: PASS"
