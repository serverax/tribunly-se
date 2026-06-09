# lawapp — Local Demo Command Pack

**Project:** lawapp — UK Employment Law AI Assistant  
**Environment:** Docker Compose on Windows/WSL  
**Backend:** http://localhost:8000  
**Frontend:** http://localhost:8000  

---

## Step 1: Start the app

```bash
cd /mnt/f/lawapp

# Clean start
docker compose down

# Build and start (DB + Backend)
docker compose up -d --build

# Verify
docker compose ps
```

Expected:
```
lawapp-db-1       Up (healthy)   0.0.0.0:5435->5432/tcp
lawapp-backend-1  Up (healthy)   0.0.0.0:8000->8000/tcp
```

---

## Step 2: Health check

```bash
curl -s http://localhost:8000/health
```

Expected: `{"status":"ok","db":"connected"}`

---

## Step 3: Run Python tests

```bash
python -m pytest tests/brain/ tests/legal_accuracy/ tests/security/ tests/router/ \
  tests/agents/ tests/citation_verification/ tests/evaluation/ tests/cache/ \
  tests/graph_rag/ tests/knowledge_graph/ tests/memory/ tests/mcp/ tests/uploads/ \
  tests/retrieval/ tests/rag/ tests/deadlines/ tests/user_isolation/ \
  tests/document_intelligence/ tests/documents/ tests/payment/ -q --tb=short
```

Expected: `354 passed`

---

## Step 4: Run Playwright E2E tests

```bash
node_modules/.bin/playwright test --reporter=list
```

Expected: `17 passed`

---

## Step 5: Access the frontend

Open your browser: **http://localhost:8000**

---

## Test User Flow

### Register and diagnose

1. Click **"Start free diagnosis"**
2. Step 1 — Select **Unfair dismissal**
3. Step 2 — Fill:
   - Dismissal date (EDT): e.g. `2026-03-01`
   - Employment start date: e.g. `2022-01-01`
   - Reason: **Misconduct**
   - ACAS: tick "I haven't contacted ACAS yet" (or enter Day A/B dates)
4. **Live deadline preview will appear** showing tribunal deadline
5. Step 3 — Select: **No procedure followed**, **No hearing**
6. Step 4 — Enter weekly pay: `£700`
7. Click **"Get my free diagnosis"**
8. Assessment page shows result

### For a DEFINITIVE result (no AI key needed)

Use short service (under 2 years) to get a clear deterministic answer:

- EDT: `2026-03-01`
- Service start: `2025-05-01` (10 months only — QP fails)

Result: `has_viable_claim: no` — full citations, deadline, weaknesses returned without AI model.

### For a complex result (needs real AI key)

- EDT: `2026-03-01`
- Service start: `2022-01-01` (4+ years)

Result with stub model: `insufficient_grounding` (correct — requires real AI)  
Result with real `ANTHROPIC_API_KEY`: full assessment with reasoning

---

## Payment Simulator Instructions

**Mode:** `PAYMENT_MODE=test_simulator` (set in `.env`)

### Get a test token

```bash
curl -s -X POST http://localhost:8000/api/payment/create-session \
  -H "Content-Type: application/json" \
  -d '{"document_type":"particulars_of_claim"}'
```

Response includes `payment_token` starting with `test_`.

### Generate full document

```bash
curl -s -X POST http://localhost:8000/documents/generate \
  -H "Content-Type: application/json" \
  -d '{
    "document_type": "particulars_of_claim",
    "assessment": {"has_viable_claim": "uncertain"},
    "facts": {"edt": "2026-03-01", "service_start_date": "2022-01-01"},
    "payment_token": "test_demo123"
  }' | python -c "import sys,json; d=json.load(sys.stdin); print(d['title']); print(d['content'][:300])"
```

**Note:** `test_` prefix required. No real charge. Clearly labelled demo mode.

---

## User Isolation Proof

```bash
# Register two users
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"userA@demo.local","password":"DemoPass123!"}' | python -c "import sys,json; print(json.load(sys.stdin))"

TOKEN_A=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"userA@demo.local","password":"DemoPass123!"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create case as User A
CASE_ID=$(curl -s -X POST http://localhost:8000/cases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN_A" \
  -d '{"claim_type":"unfair_dismissal","jurisdiction":"EW","assessment":{},"key_dates":{}}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['case_id'])")

echo "Case ID: $CASE_ID"

# Register User B and try to access User A case
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"userB@demo.local","password":"DemoPass123!"}' > /dev/null

TOKEN_B=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"userB@demo.local","password":"DemoPass123!"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -o /dev/null -w "User B access User A case: HTTP %{http_code}\n" \
  -H "Authorization: Bearer $TOKEN_B" \
  "http://localhost:8000/cases/$CASE_ID"
# Expected: HTTP 403
```

---

## Sample Documents Location

Generated sample outputs (pre-generated for demo):
```
reports/samples/particulars_of_claim_sample.md   (5,834 chars)
reports/samples/schedule_of_loss_sample.md        (7,523 chars)
reports/samples/letter_before_action_sample.md    (4,418 chars)
reports/samples/et1_notes_sample.md               (4,937 chars)
```

---

## Rules API (proves no hardcoded legal values)

```bash
curl -s http://localhost:8000/rules/unfair_dismissal | python -m json.tool | grep -A2 "time_limit_months\|qualifying_period\|compensatory_cap"
```

Expected output shows values from DB rules table with ERA 1996 citations.

---

## Brain Trace (19 steps)

```bash
curl -s -X POST http://localhost:8000/api/brain/trace \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I was dismissed after 10 months — qualifying period check",
    "facts": {
      "edt": "2026-03-01",
      "service_start_date": "2025-05-01",
      "jurisdiction": "EW",
      "weekly_pay": 500
    }
  }' | python -c "
import sys, json
d = json.load(sys.stdin)
steps = [s['step'] for s in d['trace']['steps']]
print('Steps:', steps)
print('Assessment:', d.get('assessment',{}).get('status'))
print('has_viable_claim:', d.get('assessment',{}).get('has_viable_claim'))
print('RAG sources:', d['trace']['rag_sources'])
print('Safety passed:', d['trace']['safety_passed'])
"
```
