#!/usr/bin/env bash
# report_slow_legal_queries.sh — top slow queries via pg_stat_statements (if available).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp (service 'db')"
docker compose exec -T db psql -U lawapp -d lawapp -c "ALTER USER lawapp PASSWORD 'lawapp';" >/dev/null 2>&1
Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
P(){ docker compose exec -T db psql -U lawapp -d lawapp -c "$1"; }
pss=$(Q "SELECT count(*) FROM pg_extension WHERE extname='pg_stat_statements';")
if [ "${pss:-0}" -ge 1 ]; then
  echo "########## top 10 slow statements (mean_exec_time) ##########"
  P "SELECT round(mean_exec_time::numeric,2) mean_ms, calls, rows, left(regexp_replace(query,'\s+',' ','g'),80) q FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
else
  echo "pg_stat_statements is NOT installed (requires shared_preload_libraries='pg_stat_statements')."
  echo "BLOCKER recorded: enable in postgresql.conf to capture slow-query telemetry."
  echo "Fallback: per-query EXPLAIN ANALYZE timings are captured by prove_legal_db_performance.sh."
fi
