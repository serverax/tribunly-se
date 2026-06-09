#!/bin/bash
set -e

DIR="/mnt/f/lawapp/reports/v3_evidence"
mkdir -p "$DIR"
cd /mnt/f/lawapp

echo "--- A. CLEAN START ---" > "$DIR/a_docker_start.txt"
docker compose down -v >> "$DIR/a_docker_start.txt" 2>&1 || true
docker compose up -d --build >> "$DIR/a_docker_start.txt" 2>&1
sleep 15
docker compose ps >> "$DIR/a_docker_start.txt" 2>&1

echo "--- B. BACKEND ROUTE TESTS ---" > "$DIR/b_backend_routes.txt"
curl -s -i http://localhost:8000/health >> "$DIR/b_backend_routes.txt" 2>&1 || echo "CURL FAILED" >> "$DIR/b_backend_routes.txt"
echo -e "\n--- /api/brain/trace ---" >> "$DIR/b_backend_routes.txt"
curl -s -X POST http://localhost:8000/api/brain/trace -H "Content-Type: application/json" -d '{"claim_type":"unfair_dismissal","facts":{"dismissal_date":"2026-05-10","service_years":3,"reason":"performance","appeal_done":false}}' >> "$DIR/b_backend_routes.txt" 2>&1 || echo "CURL FAILED" >> "$DIR/b_backend_routes.txt"

echo "--- C. FRONTEND GREPS ---" > "$DIR/c_frontend_greps.txt"
grep -RIn "TODO\|FIXME\|stub\|mock\|placeholder\|not implemented" client backend >> "$DIR/c_frontend_greps.txt" 2>&1 || true
grep -RIn "3 months\|6 months\|123543\|118223\|751\|719\|9157" client backend >> "$DIR/c_frontend_greps.txt" 2>&1 || true
grep -RIn "we represent\|we will file\|win your case\|guarantee\|solicitor" client backend >> "$DIR/c_frontend_greps.txt" 2>&1 || true

echo "--- D. DATABASE AUDIT ---" > "$DIR/d_db_audit.txt"
docker compose exec -T db psql -U lawapp -d lawapp -c "\dt" >> "$DIR/d_db_audit.txt" 2>&1 || echo "DB FAILED" >> "$DIR/d_db_audit.txt"
docker compose exec -T db psql -U lawapp -d lawapp -c "\dx" >> "$DIR/d_db_audit.txt" 2>&1 || true
for table in rules legislation acas_guidance case_law_chunks legal_nodes legal_edges; do
    echo "COUNT $table:" >> "$DIR/d_db_audit.txt"
    docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM $table;" >> "$DIR/d_db_audit.txt" 2>&1 || true
done
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM source_freshness;" >> "$DIR/d_db_audit.txt" 2>&1 || true

echo "--- I. OCR / UPLOAD GREP ---" > "$DIR/i_ocr_grep.txt"
grep -RIn "mock_extract\|fake confidence\|ocr\|tesseract\|textract\|placeholder" backend ingestion client tests >> "$DIR/i_ocr_grep.txt" 2>&1 || true

echo "--- J. WASM AUDIT ---" > "$DIR/j_wasm_audit.txt"
ls -lh client/public/wasm/ >> "$DIR/j_wasm_audit.txt" 2>&1 || true
grep -RIn "fetchDeadlineRules\|WebAssembly\|computeDeadline" client/public client/wasm >> "$DIR/j_wasm_audit.txt" 2>&1 || true

echo "--- K. KUBERNETES AUDIT ---" > "$DIR/k_k8s_audit.txt"
kubectl get ns | grep lawapp >> "$DIR/k_k8s_audit.txt" 2>&1 || echo "K8S FAILED" >> "$DIR/k_k8s_audit.txt"
kubectl get pods -A | grep lawapp >> "$DIR/k_k8s_audit.txt" 2>&1 || true

echo "--- L. CI/CD AUDIT ---" > "$DIR/l_cicd_audit.txt"
ls -la .github/workflows/ >> "$DIR/l_cicd_audit.txt" 2>&1 || true
grep -RIn "iterlaw\|rightsnow\|hermes" .github infra scripts backend client >> "$DIR/l_cicd_audit.txt" 2>&1 || true

echo "--- M. TEST SUITE AUDIT ---" > "$DIR/m_test_audit.txt"
# Using timeout to prevent hanging test runners
timeout 120 python -m pytest -q >> "$DIR/m_test_audit.txt" 2>&1 || echo "PYTEST TIMED OUT OR FAILED" >> "$DIR/m_test_audit.txt"
timeout 60 npm --prefix client test >> "$DIR/m_test_audit.txt" 2>&1 || echo "NPM TEST TIMED OUT OR FAILED" >> "$DIR/m_test_audit.txt"

echo "Evidence gathering complete."
