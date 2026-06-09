#!/bin/bash
cd /mnt/f/lawapp
mkdir -p reports

echo "1. File Inventory..."
find . -maxdepth 4 -type f | sort > reports/gemini-file-inventory.txt
find . -maxdepth 4 -type f \( -iname "*.md" -o -iname "*.py" -o -iname "*.ts" -o -iname "*.tsx" -o -iname "*.js" -o -iname "*.jsx" -o -iname "*.sql" -o -iname "*.yaml" -o -iname "*.yml" -o -iname "*.json" \) | sort | wc -l > reports/gemini-file-count.txt

find . -type f | sort > reports/gemini-all-files.txt
find backend -type f | sort > reports/gemini-backend-files.txt || true
find client -type f | sort > reports/gemini-client-files.txt || true
find db -type f | sort > reports/gemini-db-files.txt || true
find ingestion -type f | sort > reports/gemini-ingestion-files.txt || true
find infra -type f | sort > reports/gemini-infra-files.txt || true
find tests -type f | sort > reports/gemini-tests-files.txt || true
find scripts -type f | sort > reports/gemini-scripts-files.txt || true
find .github -type f | sort > reports/gemini-github-actions-files.txt || true

find . -type f -empty | sort > reports/gemini-empty-files.txt
find . -type f -size +1M | sort > reports/gemini-huge-files.txt
grep -R "RightsNow|IterLaw|Hermes|Sakina|AIA|Agentire|OpenClaw" . -n --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv > reports/gemini-name-contamination.txt || true

echo "2. Stubs & Fakes..."
grep -R -E "TODO|FIXME|stub|Stub|STUB|mock|Mock|MOCK|fake|Fake|FAKE|placeholder|Placeholder|simulator|Simulator|dummy|Dummy|not implemented|NotImplemented|pass #|return {}|return \[\\]|coming soon|demo only|hardcoded" . -n --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=dist --exclude-dir=build > reports/gemini-stub-fake-register.txt || true

echo "3. API Routes..."
grep -R -E "APIRouter|@app\.|@router\.|FastAPI|Blueprint|route\(" backend -n > reports/gemini-backend-routes-grep.txt || true

echo "4. Client API & Risks..."
grep -R -E "fetch\(|axios|XMLHttpRequest|localStorage|sessionStorage|document\.cookie|innerHTML|dangerouslySetInnerHTML" client -n > reports/gemini-client-risk-grep.txt || true
grep -R -E "localhost|127\.0\.0\.1|/api/|/auth|/cases|/documents|payment|stripe|brain|diagnosis" client -n > reports/gemini-client-api-calls.txt || true

echo "5. DB Greps..."
grep -R -E "CREATE TABLE|ALTER TABLE|CREATE EXTENSION|CREATE INDEX|vector|pgcrypto|rules|cases|documents|users|legal_nodes|legal_edges" db backend ingestion infra -n > reports/gemini-db-schema-grep.txt || true

echo "6. Hardcoded Rules..."
grep -R -E "3 months|three months|6 months|six months|less 1 day|less one day|123543|118223|751|719|9157|2 years|two years|52 weeks|ERA 1996|s\.111|s\.108|s\.124|s\.227" backend client ingestion tests db -n > reports/gemini-hardcoded-legal-values.txt || true

echo "7. Brain Grep..."
grep -R -E "classify|retrieve|reason|govern|grounding|confidence|insufficient_grounding|citation|de-ident|deidentify|anthropic|openai|ollama|router|agent|orchestr" backend ingestion tests -n > reports/gemini-brain-ai-grep.txt || true

echo "8. Graph RAG Grep..."
grep -R -E "graph_rag|GraphRAG|legal_nodes|legal_edges|knowledge_graph|node_type|edge_type|CITES|AMENDS|DEFINES|APPLIES_TO|SUPPORTS|LIMITS" . -n --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv > reports/gemini-graph-rag-grep.txt || true

echo "9. New Tech Grep..."
grep -R -E "semantic_cache|cache|compress|compression|memory|evaluation|eval|mcp|multimodal|ocr|router|wasm|vector|pgvector|envelope|policy|governance|citation" . -n --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv > reports/gemini-new-tech-grep.txt || true

echo "10. WASM Grep..."
grep -R -E "wasm|deadline|validation|assembly|preview" client shared backend tests -n > reports/gemini-wasm-grep.txt || true

echo "11. Document Gen Grep..."
grep -R -E "generate_document|documents/generate|particulars|schedule of loss|schedule_of_loss|docx|pdf|template" backend client tests -n > reports/gemini-document-generation-grep.txt || true

echo "12. Payment Grep..."
grep -R -E "stripe|payment|checkout|webhook|simulator|paid|tier" backend client tests -n > reports/gemini-payment-grep.txt || true

echo "13. Secrets & Security Grep..."
grep -R -E "SECRET|KEY|PASSWORD|TOKEN|sk-|pk_|BEGIN PRIVATE|DATABASE_URL|JWT_SECRET|ANTHROPIC_API_KEY|OPENAI_API_KEY|STRIPE_SECRET" . -n --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv > reports/gemini-secret-grep.txt || true
grep -R -E "innerHTML|dangerouslySetInnerHTML|eval\(|exec\(|subprocess|os\.system|shell=True|raw SQL|execute\(f|format\(" . -n --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv > reports/gemini-dangerous-code-grep.txt || true

echo "14. Encryption Grep..."
grep -R -E "encrypt|decrypt|Fernet|AES|KMS|ENCRYPTION_KEY|facts_encrypted|storage_ref|Article 9|DPIA|retention" backend db tests docs -n > reports/gemini-encryption-gdpr-grep.txt || true

echo "15. Ingestion Grep..."
grep -R -E "legislation\.gov\.uk|caselaw\.nationalarchives|acas|CLML|Akoma|LegalDocML|content_hash|source_freshness|last_verified_at|throttle|rate" ingestion backend db tests -n > reports/gemini-ingestion-grep.txt || true

echo "16. CI/CD & Observability Grep..."
grep -R -E "docker build|kubectl|helm|ghcr|registry|pytest|npm|deploy|rollout|kubeconfig|secret" .github scripts -n > reports/gemini-cicd-grep.txt || true
grep -R -E "logging|logger|trace_id|request_id|metrics|prometheus|health|ready|liveness|audit" backend infra tests -n > reports/gemini-observability-grep.txt || true

echo "17. Tests & Run Commands..."
docker compose down -v || true
docker compose up -d --build || true
sleep 10
docker compose ps > reports/gemini-docker-ps.txt || true
docker compose logs backend --tail=200 > reports/gemini-docker-backend-logs.txt || true
curl -s -i http://localhost:8000/health > reports/gemini-health.txt || true
curl -s http://localhost:8000/openapi.json > reports/gemini-openapi.json || true

docker compose exec -T db psql -U lawapp -d lawapp -c "\dt" > reports/gemini-db-dt.txt || true
docker compose exec -T db psql -U lawapp -d lawapp -c "\d legal_nodes" > reports/gemini-db-legal-nodes.txt || true
docker compose exec -T db psql -U lawapp -d lawapp -c "\d legal_edges" > reports/gemini-db-legal-edges.txt || true
docker compose exec -T db psql -U lawapp -d lawapp -c "select count(*) from rules;" > reports/gemini-db-rules-count.txt || true
docker compose exec -T db psql -U lawapp -d lawapp -c "select count(*) from legislation;" > reports/gemini-db-leg-count.txt || true
docker compose exec -T db psql -U lawapp -d lawapp -c "select count(*) from case_law;" > reports/gemini-db-case-count.txt || true

python -m pytest -q --tb=short > reports/gemini-pytest-full-output.txt || true
python -m pytest --collect-only -q > reports/gemini-pytest-collect.txt || true
npm --prefix client install || true
npm --prefix client test > reports/gemini-client-test-output.txt || true

kubectl get ns > reports/gemini-k8s-namespaces.txt || true
kubectl get pods -A > reports/gemini-k8s-pods-all.txt || true

echo "Done gathering evidence."
