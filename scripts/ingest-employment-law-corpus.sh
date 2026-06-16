#!/usr/bin/env bash
# ingest-employment-law-corpus.sh (addendum §6)
# Ingest the authentic UK employment-law corpus into the lawapp DB:
#   legislation.gov.uk (CLML) + ACAS + GOV.UK Content API + local fastembed backfill.
# Find Case Law BULK ingestion fails closed unless FCL_COMPUTATIONAL_ANALYSIS_APPROVED=true.
# Exits non-zero on any ingestion failure. No || true, no fake success.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

ING="docker compose run --rm ingestion"
PSQL="docker compose exec -T db psql -U lawapp -d lawapp"
fail=0

echo "############ 1. Legislation (legislation.gov.uk CLML) ############"
$ING python -m ingestion.legislation.ingest || { echo "legislation ingest FAILED"; fail=1; }

echo "############ 2. ACAS official guidance ############"
$ING python -m ingestion.acas.ingest || { echo "acas ingest FAILED"; fail=1; }

echo "############ 3. GOV.UK Content API guidance (incl. tribunal procedure) ############"
$ING python -m ingestion.govuk.ingest || { echo "govuk ingest FAILED"; fail=1; }

echo "############ 4. Embedding backfill (fastembed bge-small-en-v1.5, 384-dim, local) ############"
$ING python -m ingestion.embeddings.embedder || { echo "embedding backfill FAILED"; fail=1; }

echo "############ 5. Find Case Law BULK  -  external licence gate ############"
if [ "${FCL_COMPUTATIONAL_ANALYSIS_APPROVED:-false}" = "true" ]; then
  $ING python -m ingestion.case_law.ingest || { echo "case_law ingest FAILED"; fail=1; }
else
  echo "BLOCKED_EXTERNAL_LICENCE  -  BULK FIND CASE LAW INGESTION"
  echo "  (set FCL_COMPUTATIONAL_ANALYSIS_APPROVED=true to enable; legislation/ACAS/GOV.UK corpus is sufficient without it)"
fi

echo "############ 6. DB row counts ############"
$PSQL -c "SELECT 'legislation' AS source, count(*) AS rows, count(embedding) AS embedded FROM legislation
          UNION ALL SELECT 'acas_guidance', count(*), count(embedding) FROM acas_guidance
          UNION ALL SELECT 'official_guidance', count(*), count(embedding) FROM official_guidance
          ORDER BY source;"

if [ "$fail" -ne 0 ]; then
  echo "INGEST FAILED (see above)"
  exit 1
fi
echo "INGEST COMPLETE"
