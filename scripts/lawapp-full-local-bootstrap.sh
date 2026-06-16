#!/usr/bin/env bash
# lawapp  -  full local bootstrap
# Brings a clean local environment to fully legal-data-ready state.
# Run: bash scripts/lawapp-full-local-bootstrap.sh
# Fails hard on any required step.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== lawapp full local bootstrap ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# Step 1: Clean rebuild
echo "[1/8] Clean Docker rebuild..."
docker compose down -v
docker compose up -d --build

# Step 2: Wait for services
echo "[2/8] Waiting for services to be healthy..."
for i in $(seq 1 30); do
  HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('db',''))" 2>/dev/null || echo "")
  if [ "$HEALTH" = "connected" ]; then
    echo "  backend healthy"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: backend did not become healthy in 60s"
    docker compose logs backend --tail=30
    exit 1
  fi
  sleep 2
done

# Step 3: Verify DB schema (rules must be seeded by migration)
echo "[3/8] Verifying DB schema (rules table)..."
RULES_COUNT=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM rules;" 2>/dev/null | tr -d ' ')
if [ "${RULES_COUNT:-0}" -lt 1 ]; then
  echo "ERROR: rules table empty after clean start  -  seed migration did not apply"
  exit 1
fi
echo "  rules: $RULES_COUNT rows"

# Step 4: Run legislation ingestion
echo "[4/8] Running legislation ingestion..."
docker compose run --rm ingestion python -m ingestion.legislation.ingest 2>&1 | tail -5 || {
  echo "WARNING: legislation ingestion failed  -  corpus will be empty"
}
LEG_COUNT=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM legislation;" 2>/dev/null | tr -d ' ')
echo "  legislation: ${LEG_COUNT:-0} rows"

# Step 5: Run ACAS ingestion
echo "[5/8] Running ACAS ingestion..."
docker compose run --rm ingestion python -m ingestion.acas.ingest 2>&1 | tail -5 || {
  echo "WARNING: ACAS ingestion failed  -  ACAS guidance corpus will be empty"
}
ACAS_COUNT=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM acas_guidance;" 2>/dev/null | tr -d ' ')
echo "  acas_guidance: ${ACAS_COUNT:-0} rows"

# Step 6: Source freshness
echo "[6/8] Source freshness check..."
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM source_freshness;" 2>/dev/null || \
  echo "  source_freshness table not yet populated"

# Step 7: Backend health
echo "[7/8] Backend health..."
curl -s http://localhost:8000/health | python3 -m json.tool

# Step 8: Verify knowledge-graph seed (migration 018 must have populated it)
echo "[8/9] Verifying knowledge-graph seed (legal_nodes/legal_edges)..."
NODES=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM legal_nodes;" 2>/dev/null | tr -d ' ')
EDGES=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM legal_edges;" 2>/dev/null | tr -d ' ')
if [ "${NODES:-0}" -lt 1 ] || [ "${EDGES:-0}" -lt 1 ]; then
  echo "ERROR: legal_nodes/legal_edges empty  -  migration 018 graph seed did not apply"
  exit 1
fi
echo "  legal_nodes: $NODES | legal_edges: $EDGES"

# Step 9: PROOF TEST GATE  -  the founder's bar: "docker compose up to a passing
# test suite". Runs the core proof suite in the ingestion container against the
# freshly-bootstrapped DB. Fails the bootstrap hard if anything is red.
echo "[9/9] Proof test gate (Critic + GraphRAG->ART + local inference + outbox)..."
docker compose --profile ingestion run --rm ingestion python -m pytest -q \
  tests/test_integrity_framework.py \
  tests/test_evolution_gate.py \
  tests/graph_rag/test_graph_rag_art_integration.py \
  tests/graph_rag/test_graph_rag.py \
  tests/test_local_inference.py \
  tests/test_brain_outbox.py \
  || { echo "ERROR: proof test suite RED  -  bootstrap is NOT live per the passing-suite bar"; exit 1; }

echo ""
echo "=== Bootstrap complete ==="
echo "rules: ${RULES_COUNT:-0} | legislation: ${LEG_COUNT:-0} | acas: ${ACAS_COUNT:-0} | nodes: ${NODES:-0} | edges: ${EDGES:-0}"
if [ "${LEG_COUNT:-0}" -lt 1 ] || [ "${ACAS_COUNT:-0}" -lt 1 ]; then
  echo "STATUS: LOCAL DEMO ONLY  -  legal corpus empty; RAG returns insufficient_grounding"
else
  echo "STATUS: LOCAL READY  -  legal corpus populated AND proof suite green"
fi
