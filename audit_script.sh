#!/bin/bash
cd /mnt/f/lawapp

echo "=== PHASE 0: ENVIRONMENT PROOF ==="
pwd
git status --short
git branch --show-current
git log -1 --oneline
find . -maxdepth 3 -type f | wc -l
find . -maxdepth 3 -type f \( -name "package.json" -o -name "requirements.txt" -o -name "pyproject.toml" -o -name "Dockerfile" -o -name "docker-compose.yml" -o -name "*.sql" -o -name "*.yaml" -o -name "*.yml" \)

echo "=== PHASE 1: INVENTORY ==="
find . -type f | sort > /tmp/lawapp_all_files.txt
wc -l /tmp/lawapp_all_files.txt
grep -Ei "(TODO|FIXME|stub|mock|placeholder|fake|dummy|not implemented|pass$|return None|console.log|hardcoded|test only)" -R . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv | wc -l

echo "=== PHASE 2: ROUTES ==="
grep -R "app\.\|router\.\|@.*route\|FastAPI\|APIRouter\|express.Router\|@router" backend server api . --include="*.py" --include="*.js" --include="*.ts" 2>/dev/null | head -n 50

echo "=== PHASE 3: FRONTEND WIRING ==="
grep -R "fetch(\|axios\|XMLHttpRequest\|href=\|action=" client frontend web app --include="*.js" --include="*.ts" --include="*.html" --include="*.tsx" --include="*.jsx" 2>/dev/null | head -n 50

echo "=== PHASE 4: DB SCHEMA ==="
grep -R "CREATE TABLE\|ALTER TABLE\|CREATE EXTENSION\|CREATE INDEX\|vector\|pgcrypto\|rules\|cases\|documents\|users" . --include="*.sql" --include="*.py" --include="*.ts" --include="*.js" | head -n 50
docker compose exec -T db psql -U lawapp -d lawapp -c "\dt" 2>&1 || echo "DB not accessible"
docker compose exec -T db psql -U lawapp -d lawapp -c "\dx" 2>&1 || echo "DB extensions not accessible"

echo "=== PHASE 5: RULES AND DEADLINES ==="
grep -R "3 months\|three months\|less 1 day\|less one day\|111(2)\|207B\|123543\|118223\|751\|719\|9157\|qualifying_period\|time_limit\|compensation_cap\|weeks_pay" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv | head -n 50

echo "=== PHASE 6: RAG AND REASONING ==="
grep -R "classify\|retrieve\|rag\|vector\|embedding\|grounding\|confidence\|govern\|insufficient_grounding\|citations\|structured assessment\|de-ident" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv | head -n 50

echo "=== PHASE 7: AI PROVIDERS ==="
grep -R "ANTHROPIC\|OPENAI\|GEMINI\|Claude\|OpenAI\|Gemini\|model\|llm\|api_key\|prompt" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv | head -n 50

echo "=== PHASE 8: INGESTION ==="
grep -R "legislation.gov.uk\|caselaw.nationalarchives.gov.uk\|acas\|CLML\|Akoma\|LegalDocML\|atom.xml\|data.xml\|contenthash\|last_verified_at\|source_freshness" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv | head -n 50

echo "=== PHASE 9: WASM ==="
grep -R "wasm\|deadline\|validation\|assembly\|preview\|wasm-bindgen\|AssemblyScript" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv | head -n 50

echo "=== PHASE 10: AUTH AND ISOLATION ==="
grep -R "jwt\|JWT\|token\|Authorization\|Bearer\|password\|bcrypt\|hash\|session\|current_user\|user_id\|owner" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv | head -n 50

echo "=== PHASE 11: ENCRYPTION ==="
grep -R "encrypt\|decrypt\|Fernet\|AES\|pgcrypto\|facts_encrypted\|storage_ref\|PII\|personal data\|de-ident\|redact\|Article 9\|GDPR" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv | head -n 50
grep -R "ANTHROPIC_API_KEY=\|OPENAI_API_KEY=\|STRIPE_SECRET_KEY=\|JWT_SECRET=\|ENCRYPTION_KEY=" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv || true

echo "=== PHASE 12: PAYMENT ==="
grep -R "stripe\|payment\|checkout\|webhook\|paid\|payment_tier\|create-session\|simulator" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv | head -n 50

echo "=== PHASE 13: DOCUMENT GENERATION ==="
grep -R "particulars\|schedule of loss\|document generation\|generate_document\|download\|template\|docx\|pdf\|markdown\|witness\|chronology\|ET1" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv | head -n 50

echo "=== PHASE 15: TESTS ==="
python -m pytest -q --tb=short 2>&1 || echo "Pytest failed or not found"

echo "=== PHASE 17: K8S ==="
kubectl get all -A 2>&1 || echo "kubectl not available"
