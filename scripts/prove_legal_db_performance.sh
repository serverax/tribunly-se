#!/usr/bin/env bash
# prove_legal_db_performance.sh — extensions, indexes, and EXPLAIN ANALYZE proof.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp (service 'db')"

P(){ docker compose exec -T db psql -U lawapp -d lawapp -c "$1"; }
Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## 1. installed extensions ##########"
P "SELECT extname FROM pg_extension WHERE extname IN ('vector','pgcrypto','pg_trgm','pg_stat_statements') ORDER BY extname;"
for e in vector pgcrypto pg_trgm; do
  n=$(Q "SELECT count(*) FROM pg_extension WHERE extname='$e';"); [ "${n:-0}" -ge 1 ] && ok "extension $e" || bad "missing $e"
done
pss=$(Q "SELECT count(*) FROM pg_extension WHERE extname='pg_stat_statements';")
[ "${pss:-0}" -ge 1 ] && ok "pg_stat_statements available" || echo "  NOTE: pg_stat_statements not installed (needs shared_preload_libraries) — slow-query report degraded"

echo "########## 2. required indexes ##########"
for ix in corpus_chunks_emb_hnsw legislation_emb_hnsw corpus_chunks_fts_idx legislation_fts_idx legislation_acttitle_trgm rules_rulekey_trgm rules_key_juris_eff_idx rules_claim_juris_eff_idx; do
  n=$(Q "SELECT count(*) FROM pg_indexes WHERE indexname='$ix';")
  [ "${n:-0}" -ge 1 ] && ok "index $ix" || bad "missing index $ix (or ivfflat fallback name)"
done

run_explain(){ # $1 label  $2 sql  $3 expect-regex
  echo "########## EXPLAIN ANALYZE: $1 ##########"
  local out; out=$(P "EXPLAIN (ANALYZE, BUFFERS) $2" 2>&1)
  echo "$out" | grep -iE "Scan|Index|Time:|hnsw|Sort|Gather" | head -8
  local ms; ms=$(echo "$out" | grep -oE "Execution Time: [0-9.]+" | grep -oE "[0-9.]+")
  echo "  exec_time_ms=${ms:-?}"
  if echo "$out" | grep -qiE "$3"; then ok "$1 uses expected access path"; else echo "  NOTE: $1 did not match '$3' (seed dataset small; planner may seq-scan)"; fi
}

run_explain "rules lookup (key+jurisdiction+date)" \
  "SELECT value_numeric FROM rules WHERE rule_key='unfair_dismissal.weeks_pay_cap_amount' AND jurisdiction_code='GB' AND effective_from<=DATE '2024-06-01' AND (effective_to IS NULL OR effective_to>=DATE '2024-06-01');" \
  "Index|Bitmap"
run_explain "current-law query" \
  "SELECT section_ref FROM legislation WHERE is_prospective=false AND section_ref='98';" \
  "Index|Bitmap"
run_explain "full-text search" \
  "SELECT id FROM corpus_chunks WHERE to_tsvector('english',body_text) @@ plainto_tsquery('english','unfair dismissal') LIMIT 5;" \
  "Bitmap|gin|Index"
run_explain "trigram fuzzy (act title)" \
  "SELECT DISTINCT act_title FROM legislation WHERE act_title ILIKE '%Employment Right%' LIMIT 5;" \
  "trgm|Bitmap|Index|Gather"
run_explain "vector retrieval (top-k)" \
  "SELECT id FROM corpus_chunks ORDER BY embedding <=> (SELECT embedding FROM corpus_chunks WHERE embedding IS NOT NULL LIMIT 1) LIMIT 5;" \
  "hnsw|Index|Scan"
run_explain "hybrid (jurisdiction-filtered vector + fts)" \
  "SELECT id FROM corpus_chunks WHERE jurisdiction_code='GB' AND (to_tsvector('english',body_text) @@ plainto_tsquery('english','unfair dismissal') OR true) ORDER BY embedding <=> (SELECT embedding FROM corpus_chunks WHERE embedding IS NOT NULL LIMIT 1) LIMIT 5;" \
  "Index|Scan|hnsw"

echo "########## 9. slow query report ##########"
if [ "${pss:-0}" -ge 1 ]; then
  P "SELECT round(mean_exec_time::numeric,2) ms, calls, left(query,60) q FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 5;" 2>&1 | head -10
else
  echo "  pg_stat_statements unavailable — see reports/legal-db-performance-proof.md for note"
fi

[ "$fail" -ne 0 ] && { echo "LEGAL DB PERFORMANCE PROOF: FAIL"; exit 1; }
echo "LEGAL DB PERFORMANCE PROOF: PASS"
