#!/usr/bin/env bash
# prove_source_freshness.sh — source_freshness works, groups by jurisdiction, flags stale.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp"
FRESH_DAYS="${CORPUS_FRESH_DAYS:-120}"
Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
P(){ docker compose exec -T db psql -U lawapp -d lawapp -c "$1"; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## source_freshness exists + returns rows + groups by jurisdiction ##########"
n=$(Q "SELECT count(*) FROM source_freshness;")
[ "${n:-0}" -ge 1 ] && ok "source_freshness rows=$n" || bad "source_freshness empty/broken"
j=$(Q "SELECT count(*) FROM information_schema.columns WHERE table_name='source_freshness' AND column_name='jurisdiction_code';")
[ "${j:-0}" -ge 1 ] && ok "source_freshness exposes jurisdiction_code" || bad "no jurisdiction_code column"
for col in source_name source_type rows_count oldest_verified_at newest_verified_at stale_rows_count last_ingestion_status; do
  c=$(Q "SELECT count(*) FROM information_schema.columns WHERE table_name='source_freshness' AND column_name='$col';")
  [ "${c:-0}" -ge 1 ] && ok "column $col" || bad "missing column $col"
done

echo "########## staleness flagged + currently fresh ##########"
stale=$(Q "SELECT coalesce(sum(stale_rows_count),0) FROM source_freshness;")
echo "  REPORT: total stale rows (> ${FRESH_DAYS}d) = ${stale:-?}"
[ "${stale:-1}" -eq 0 ] && ok "no stale legal rows" || bad "$stale stale rows"

echo "########## freshness table ##########"
P "SELECT source_name, source_type, jurisdiction_code, rows_count, stale_rows_count, last_ingestion_status FROM source_freshness ORDER BY source_name;" 2>&1 | head -12

[ "$fail" -ne 0 ] && { echo "SOURCE FRESHNESS PROOF: FAIL"; exit 1; }
echo "SOURCE FRESHNESS PROOF: PASS"
