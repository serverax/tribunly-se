#!/usr/bin/env bash
# refresh_legal_materialized_views.sh — refresh the current-chunks materialized view.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp (service 'db')"
docker compose exec -T db psql -U lawapp -d lawapp -c "ALTER USER lawapp PASSWORD 'lawapp';" >/dev/null 2>&1
P(){ docker compose exec -T db psql -U lawapp -d lawapp -c "$1"; }
# CONCURRENTLY requires the unique index (mv_current_chunks_hash_idx) created in migration 034.
if P "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_current_employment_legal_chunks;" 2>/dev/null; then
  echo "refreshed CONCURRENTLY"
else
  P "REFRESH MATERIALIZED VIEW mv_current_employment_legal_chunks;"
  echo "refreshed (non-concurrent)"
fi
echo "########## row counts by jurisdiction_code ##########"
P "SELECT jurisdiction_code, source_type, count(*) FROM mv_current_employment_legal_chunks GROUP BY jurisdiction_code, source_type ORDER BY 1,2;"
ni=$(docker compose exec -T db psql -U lawapp -d lawapp -t -c "SELECT count(*) FROM mv_current_employment_legal_chunks WHERE jurisdiction_code='NI';" | tr -d ' \r\n')
[ "${ni:-0}" -eq 0 ] && echo "OK: materialized view excludes unsupported NI rows" || { echo "FAIL: NI rows leaked into materialized view"; exit 1; }
echo "MATERIALIZED VIEW REFRESH: OK"
