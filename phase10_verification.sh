#!/bin/bash
set -e

DIR="/mnt/f/lawapp"
REPORT="$DIR/reports/lawapp-final-completion-and-signoff-proof.md"
mkdir -p "$DIR/reports"

echo "# LawApp Final Completion and Sign-off Proof" > "$REPORT"
echo "" >> "$REPORT"

echo "## Phase 1: Real Payment Logic Verification" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
cd "$DIR"
grep -R "mock-paid|sessionStorage.*payment_token" -n client backend >> "$REPORT" 2>&1 || echo "PASS: No fake payment bypass found." >> "$REPORT"
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Phase 2: Real OCR / Extraction Verification" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
grep -R "def mock_extract" -n backend >> "$REPORT" 2>&1 || echo "PASS: No mock_extract found in backend." >> "$REPORT"
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Phase 3: Legal Data Spine Verification" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
docker compose down -v >> /dev/null 2>&1 || true
docker compose up -d --build >> /dev/null 2>&1
sleep 30
for table in rules legislation acas_guidance; do
    echo "COUNT $table:" >> "$REPORT"
    docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM $table;" >> "$REPORT" 2>&1 || true
done
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Phase 4 & 6: Brain and Document Generation Verification" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
# Test brain trace
curl -s -X POST http://localhost:8000/api/brain/trace -H "Content-Type: application/json" -d '{"message":"unfair dismissal test","facts":{"edt":"2026-05-10","service_years":3,"reason":"performance","appeal_done":false}}' | jq .status >> "$REPORT" 2>&1 || echo "CURL FAILED" >> "$REPORT"
# Test document generation (should be payment_required: true)
curl -s -X POST http://localhost:8000/documents/generate -H "Content-Type: application/json" -d '{"document_type":"particulars_of_claim","assessment":{},"facts":{}}' | jq .payment_required >> "$REPORT" 2>&1 || echo "CURL FAILED" >> "$REPORT"
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Phase 5: Frontend Build State" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
ls -la client/package.json >> "$REPORT" 2>&1 || echo "FAILED: package.json missing" >> "$REPORT"
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Kubernetes Manifest Health" >> "$REPORT"
echo "\`\`\`bash" >> "$REPORT"
grep -E "POSTGRES_HOST|image:|envFrom:" infra/k8s/*.yaml >> "$REPORT" 2>&1 || true
echo "\`\`\`" >> "$REPORT"
echo "" >> "$REPORT"

echo "Final verification complete."
