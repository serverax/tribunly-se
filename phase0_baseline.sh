#!/bin/bash
set -e

DIR="/mnt/f/lawapp"
REPORT="$DIR/reports/lawapp-completion-before-state.md"
mkdir -p "$DIR/reports"

echo "# LawApp Completion Before State" > "$REPORT"
echo "" >> "$REPORT"

echo "## Git Status" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
cd "$DIR" || exit 1
git status --short >> "$REPORT" 2>&1 || true
git log -1 --oneline >> "$REPORT" 2>&1 || true
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Docker Clean Start" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
docker compose down -v >> "$REPORT" 2>&1 || true
docker compose up -d --build >> "$REPORT" 2>&1
sleep 15
docker compose ps >> "$REPORT" 2>&1
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Backend Health" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
curl -s -i http://localhost:8000/health >> "$REPORT" 2>&1 || echo "CURL FAILED" >> "$REPORT"
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Backend Logs (First 50 lines)" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
docker compose logs backend --tail=50 >> "$REPORT" 2>&1 || true
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Database Table Counts" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
docker compose exec -T db psql -U lawapp -d lawapp -c "\dt" >> "$REPORT" 2>&1 || true
for table in rules legislation acas_guidance case_law_chunks; do
    echo "COUNT $table:" >> "$REPORT"
    docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM $table;" >> "$REPORT" 2>&1 || true
done
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Pytest State" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
timeout 120 python -m pytest -q >> "$REPORT" 2>&1 || echo "PYTEST FAILED OR TIMED OUT" >> "$REPORT"
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Frontend Test State" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
timeout 60 npm --prefix client test >> "$REPORT" 2>&1 || echo "NPM TEST FAILED OR TIMED OUT" >> "$REPORT"
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Kubernetes Pod State" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
kubectl get pods -A | grep lawapp >> "$REPORT" 2>&1 || echo "KUBECTL FAILED OR NO PODS" >> "$REPORT"
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "Baseline capture complete."
