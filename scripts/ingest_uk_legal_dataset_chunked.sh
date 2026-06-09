#!/usr/bin/env bash
# ingest_uk_legal_dataset_chunked.sh — chunked, resumable, idempotent ingestion of
# the UK employment legal dataset. Each source is a separate batch; every batch
# records a checkpoint in corpus_ingestion_runs (rows_ingested, rows_rejected,
# status, failures). Safe to re-run: ingestors upsert, so duplicates are not created.
#
# Design (per chunked-ingestion order):
#   - chunk by source: legislation -> limits_orders(uksi) -> acas -> govuk -> embeddings
#   - rate limits respected inside ingestors (legislation client throttles to ~1 req/s)
#   - one source failing => that batch marked FAILED, others continue
#   - 404 sections are skipped by the ingestor (documented, never faked)
#   - embeddings batched by the embedder; proof fails later if any required embedding missing
#   - resumable: pass --only <source> to run a single batch; re-running is idempotent
#
# Usage:
#   bash scripts/ingest_uk_legal_dataset_chunked.sh            # all batches
#   bash scripts/ingest_uk_legal_dataset_chunked.sh --only acas
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DOMAIN="${LAWAPP_DOMAIN:-employment_uk}"
ONLY=""
[ "${1:-}" = "--only" ] && ONLY="${2:-}"


Q() { docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
ING() { docker compose run --rm -T -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=lawapp ingestion "$@"; }

# table that holds the rows a given batch produces (for before/after delta)
count_table() {
  case "$1" in
    legislation)    echo "legislation WHERE leg_type<>'uksi'";;
    limits_orders)  echo "legislation WHERE leg_type='uksi'";;
    acas)           echo "acas_guidance";;
    govuk)          echo "official_guidance";;
    embeddings)     echo "legislation WHERE embedding IS NOT NULL";;
    *)              echo "legislation";;
  esac
}

run_batch() {
  local name="$1"; shift
  local module="$1"; shift
  [ -n "$ONLY" ] && [ "$ONLY" != "$name" ] && return 0

  local tbl; tbl="$(count_table "$name")"
  local before; before="$(Q "SELECT count(*) FROM $tbl;")"
  echo "================================================================"
  echo "  BATCH: $name  (module: $module)  rows_before=$before"
  echo "================================================================"

  local status="passed" failure="" logf=".ingest_${name}.log"
  if ING python -m "$module" >"$logf" 2>&1; then
    tail -3 "$logf" | sed 's/^/    /'
  else
    status="failed"
    failure="$(tail -1 "$logf" | tr "'" ' ' | cut -c1-300)"
    echo "    [FAILED] $name — see $logf"
    echo "    $failure"
  fi
  rm -f "$logf"

  local after; after="$(Q "SELECT count(*) FROM $tbl;")"
  local delta=$(( ${after:-0} - ${before:-0} ))
  [ "$delta" -lt 0 ] && delta=0
  echo "    rows_after=$after  rows_ingested(delta)=$delta  status=$status"

  # checkpoint
  docker compose exec -T db psql -U lawapp -d lawapp -c \
    "INSERT INTO corpus_ingestion_runs (domain, source_id, run_kind, status, rows_ingested, validation_passed, failures, completed_at) \
     VALUES ('$DOMAIN', '$name', '$name', '$status', $delta, $([ "$status" = passed ] && echo true || echo false), \
     $([ -n "$failure" ] && echo "'[\"$(echo "$failure" | sed 's/"/\\\"/g')\"]'::jsonb" || echo 'NULL'), now());" >/dev/null 2>&1

  [ "$status" = passed ]
}

fail=0
run_batch legislation   ingestion.legislation.ingest        || fail=1
run_batch limits_orders ingestion.rules.seed_limits_orders  || fail=1
run_batch acas          ingestion.acas.ingest               || fail=1
run_batch govuk         ingestion.govuk.ingest              || fail=1
run_batch embeddings    ingestion.embeddings.embedder       || fail=1

echo
echo "########## batch checkpoints (corpus_ingestion_runs) ##########"
docker compose exec -T db psql -U lawapp -d lawapp -c \
  "SELECT source_id, status, rows_ingested, completed_at FROM corpus_ingestion_runs \
   WHERE domain='$DOMAIN' AND run_kind <> 'full' ORDER BY completed_at DESC LIMIT 5;" 2>&1 | head -12

if [ "$fail" -ne 0 ]; then
  echo "CHUNKED INGESTION: ONE OR MORE BATCHES FAILED AND NEEDS FIX (other batches still applied)"
  exit 1
fi
echo "CHUNKED INGESTION: ALL BATCHES OK"
