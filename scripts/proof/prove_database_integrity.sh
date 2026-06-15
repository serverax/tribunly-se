#!/usr/bin/env bash
set -euo pipefail

REPORT="${REPORT:-reports/proof_database_integrity.txt}"
mkdir -p "$(dirname "$REPORT")"
: > "$REPORT"

log() {
  printf '%s\n' "$*" | tee -a "$REPORT"
}

find_python() {
  for candidate in python3 python python.exe py; do
    if command -v "$candidate" >/dev/null 2>&1 && PYTHONPATH="${PYTHONPATH:-.}" "$candidate" -c "import psycopg2" >/dev/null 2>&1; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

run_sql() {
  local label="$1"
  local sql="$2"
  log ""
  log "## $label"
  docker compose exec -T db psql -U lawapp -d lawapp -v ON_ERROR_STOP=1 -c "$sql" | tee -a "$REPORT"
}

run_empty_gate() {
  local label="$1"
  local sql="$2"
  log ""
  log "## $label"
  local output
  output="$(docker compose exec -T db psql -U lawapp -d lawapp -v ON_ERROR_STOP=1 -t -A -c "$sql")"
  if [[ -n "$output" ]]; then
    printf '%s\n' "$output" | tee -a "$REPORT"
    log "FAIL: $label"
    return 1
  fi
  log "PASS: $label"
}

GO_LIVE_MODE="${GO_LIVE_MODE:-beta}"
log "go_live_mode=$GO_LIVE_MODE"

log ""
log "## schema readiness"
PY_BIN="$(find_python)" || {
  log "FAIL: No Python interpreter available for schema readiness proof"
  exit 1
}
SCHEMA_DATABASE_URL="${SCHEMA_DATABASE_URL:-postgresql://lawapp:lawapp@localhost:5435/lawapp}"
DATABASE_URL="$SCHEMA_DATABASE_URL" PYTHONPATH="${PYTHONPATH:-.}" "$PY_BIN" scripts/proof/prove_schema_readiness.py | tee -a "$REPORT"

docker compose ps | tee -a "$REPORT"
run_sql "tables" "\\dt"
run_sql "pgvector extension" "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"
run_sql "source freshness" "SELECT * FROM source_freshness;"
run_sql "rules" "SELECT rule_key, value_numeric, value_text, effective_from, effective_to FROM rules ORDER BY rule_key, effective_from;"
run_sql "core tables" "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('users','cases','documents','payment_events','rules','legislation','acas_guidance','case_law_documents','corpus_chunks') ORDER BY table_name;"
run_sql "missing rule provenance" "SELECT rule_key FROM rules WHERE authority_ref IS NULL OR authority_ref='' OR effective_from IS NULL;"
run_sql "employment module DB coverage" "SELECT claim_type, count(*) AS rule_count FROM rules GROUP BY claim_type ORDER BY claim_type;"
run_sql "employment module catalogue" "SELECT module_key, status, db_backed_required FROM employment_modules ORDER BY module_key;"
run_sql "employment module readiness" "SELECT module_key, status, verified_rule_count FROM employment_module_readiness ORDER BY module_key;"
run_sql "employment module count gate" "SELECT CASE WHEN count(*) = 24 THEN 'PASS' ELSE 'FAIL' END AS module_count_gate, count(*) AS module_count FROM employment_modules;"
run_empty_gate "exactly 24 employment modules" "SELECT 'module_count=' || count(*) FROM employment_modules HAVING count(*) <> 24;"
run_empty_gate "all employment modules require DB backing" "SELECT module_key FROM employment_modules WHERE db_backed_required IS DISTINCT FROM true ORDER BY module_key;"
if [[ "$GO_LIVE_MODE" == "production" ]]; then
  run_empty_gate "all required employment modules are production-ready for go-live" "SELECT module_key || ':' || status FROM employment_modules WHERE status <> 'production' ORDER BY module_key;"
else
  log ""
  log "## beta go-live: partial modules allowed with fail-closed product scope"
  run_empty_gate "beta: partial modules must have verified DB rules" "SELECT module_key FROM employment_module_readiness WHERE status = 'partial' AND verified_rule_count = 0 ORDER BY module_key;"
  run_empty_gate "beta: production module count matches supported scope" "SELECT 'production_count=' || count(*) FROM employment_modules WHERE status = 'production' HAVING count(*) <> 11;"
fi
run_empty_gate "production employment modules have verified DB rules" "SELECT module_key || ':verified_rule_count=' || verified_rule_count FROM employment_module_readiness WHERE status = 'production' AND verified_rule_count = 0 ORDER BY module_key;"

log ""
log "PASS: database integrity proof completed"
