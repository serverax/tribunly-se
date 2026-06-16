#!/usr/bin/env bash
# prove_workflow_abc.sh  -  repeatable local proof of Workflow A/B/C.
# Runs pytest + authed HTTP E2E + DB verification + outbox lifecycle + frontend
# static wiring. Exits non-zero on ANY missing proof. No manual interpretation.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

BASE="${BASE:-http://localhost:8000}"
PSQL() { docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
ING="docker compose run --rm -e POSTGRES_PASSWORD=lawapp ingestion"
fail=0
ok()   { echo "  PASS: $*"; }
bad()  { echo "  FAIL: $*"; fail=1; }
step() { echo; echo "########## $* ##########"; }

# keep DB auth consistent for compose run -e invocations
docker compose exec -T db psql -U lawapp -d lawapp -c "ALTER USER lawapp PASSWORD 'lawapp';" >/dev/null 2>&1

step "1. PYTEST (Workflow A/B/C + outbox + agentic)"
$ING python -m pytest -q \
  tests/test_constructive_dismissal.py tests/test_evidence_intake.py \
  tests/test_schedule_of_loss.py tests/ingestion/test_rag_corpus_citations.py \
  tests/test_outbox.py tests/test_outbox_worker.py tests/test_brain_outbox.py \
  tests/test_openrouter_config.py tests/test_agents_schema_validation.py \
  tests/test_agent_pii_boundary.py \
  && ok "pytest suite green" || bad "pytest suite"

step "2. MINT JWT"
UID_USER="11111111-1111-1111-1111-111111111111"
TOKEN=$(docker compose exec -T backend python -c "import jwt,os,datetime;s=os.environ['JWT_SECRET'];c={'sub':'$UID_USER','exp':datetime.datetime.utcnow()+datetime.timedelta(hours=1)};i=os.environ.get('JWT_ISSUER');a=os.environ.get('JWT_AUDIENCE');c.update({k:v for k,v in [('iss',i),('aud',a)] if v});print(jwt.encode(c,s,algorithm='HS256'))" 2>/dev/null | tr -d '\r')
[ -n "$TOKEN" ] && ok "JWT minted" || bad "JWT mint"

step "3. CREATE CASE (POST /cases)"
CASE=$(curl -s -X POST "$BASE/cases" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"claim_type":"unfair_dismissal","jurisdiction":"EW","assessment":{"status":"ok"},"key_dates":{"edt":"2026-05-10"}}')
CASE_ID=$(echo "$CASE" | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('case_id') or d.get('id') or '')" 2>/dev/null)
[ -n "$CASE_ID" ] && ok "case_id=$CASE_ID" || bad "create case: $CASE"

step "4. UPLOAD synthetic dismissal letter PDF (multipart)"
# Generate a valid, text-extractable PDF in-repo (relative path so Windows curl
# can read it). The upload endpoint accepts PDF/JPEG/PNG/TIFF only.
python - <<'PY'
text=b"BT /F1 12 Tf 50 700 Td (Your dismissal takes effect on 10 May 2026. Reason for dismissal is gross misconduct. Appeal within 5 days.) Tj ET"
objs=[b"<< /Type /Catalog /Pages 2 0 R >>",
 b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
 b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
 b"<< /Length %d >>\nstream\n%s\nendstream"%(len(text),text),
 b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
pdf=b"%PDF-1.4\n"; offs=[]
for i,o in enumerate(objs,1):
    offs.append(len(pdf)); pdf+=b"%d 0 obj\n%s\nendobj\n"%(i,o)
x=len(pdf); pdf+=b"xref\n0 %d\n0000000000 65535 f \n"%(len(objs)+1)
for off in offs: pdf+=b"%010d 00000 n \n"%off
pdf+=b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF"%(len(objs)+1,x)
open(".proof_upload.pdf","wb").write(pdf)
PY
UPRESP=$(curl -s -X POST "$BASE/cases/$CASE_ID/uploads" -H "Authorization: Bearer $TOKEN" \
  -F "doc_type=dismissal_letter" -F "file=@.proof_upload.pdf;type=application/pdf")
UPLOAD_ID=$(echo "$UPRESP" | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('upload_id') or d.get('id') or '')" 2>/dev/null)
[ -n "$UPLOAD_ID" ] && ok "upload_id=$UPLOAD_ID" || bad "upload: $UPRESP"

step "5. EXTRACT (AEE)"
EX=$(curl -s -X POST "$BASE/cases/$CASE_ID/uploads/$UPLOAD_ID/extract" -H "Authorization: Bearer $TOKEN")
echo "  extract resp: $(echo "$EX" | head -c 200)"
echo "$EX" | grep -qiE "fact_count|extraction_method|status" && ok "extract returned structured result" || bad "extract result"

step "6. DB: unconfirmed document_facts must exist (not auto-applied)"
NF=$(PSQL "SELECT count(*) FROM document_facts WHERE upload_id='$UPLOAD_ID'::uuid AND status='unconfirmed';")
[ "${NF:-0}" -ge 1 ] && ok "unconfirmed document_facts=$NF" || bad "no unconfirmed document_facts (=$NF)"

step "7. evidence_parsed outbox event pending -> processed"
EVN=$(PSQL "SELECT count(*) FROM outbox_events WHERE event_type='evidence_parsed' AND payload->>'upload_id'='$UPLOAD_ID';")
[ "${EVN:-0}" -ge 1 ] && ok "evidence_parsed published ($EVN)" || bad "evidence_parsed not published (=$EVN)"
$ING python -m backend.core.outbox_worker --once >/dev/null 2>&1 || true
PROC=$(PSQL "SELECT count(*) FROM outbox_events WHERE event_type='evidence_parsed' AND payload->>'upload_id'='$UPLOAD_ID' AND status='processed';")
[ "${PROC:-0}" -ge 1 ] && ok "evidence_parsed processed ($PROC)" || bad "evidence_parsed not processed (=$PROC)"

step "8. APPLY-CONFIRMED (confirmed facts must be explicit)"
AC=$(curl -s -X POST "$BASE/cases/$CASE_ID/uploads/$UPLOAD_ID/apply-confirmed" -H "Authorization: Bearer $TOKEN")
echo "  apply-confirmed resp: $(echo "$AC" | head -c 160)"
echo "$AC" | grep -qiE "applied|case_id|extraction_status" && ok "apply-confirmed responded" || bad "apply-confirmed"

step "9. FAIL-CLOSED: image upload with no extractable text yields no usable facts"
# 1x1 PNG (accepted type, no OCR available -> no facts -> fail-closed).
python - <<'PY'
import base64
open(".proof_empty.png","wb").write(base64.b64decode(
 "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="))
PY
UP2=$(curl -s -X POST "$BASE/cases/$CASE_ID/uploads" -H "Authorization: Bearer $TOKEN" -F "doc_type=other" -F "file=@.proof_empty.png;type=image/png")
UID2=$(echo "$UP2" | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('upload_id') or d.get('id') or '')" 2>/dev/null)
EX2=$(curl -s -X POST "$BASE/cases/$CASE_ID/uploads/$UID2/extract" -H "Authorization: Bearer $TOKEN")
echo "$EX2" | grep -qiE "fail_closed|no_usable_facts|\"fact_count\": ?0|no_facts" && ok "fail-closed on no usable facts" || bad "no fail-closed: $(echo "$EX2"|head -c 120)"

step "10. Workflow B live API (constructive dismissal)"
CD=$(curl -s -X POST "$BASE/api/workflows/constructive-dismissal" -H "Content-Type: application/json" \
  -d '{"facts":{"repudiatory_acts":[{"date":"2026-03-01","event":"pay cut","breach_kind":"express"}],"resignation_date":"2026-03-05","resignation_letter_cites_breach":true}}')
echo "$CD" | grep -qE '"citations"' && echo "$CD" | grep -qE 's\.95' && ok "CD returns DB-verified s.95 citation" || bad "CD citations: $(echo "$CD"|head -c 120)"

step "11. Workflow C deterministic hybrid RAG (grounded, cited)"
RAG=$(curl -s -X POST "$BASE/api/rag/hybrid-search" -H "Content-Type: application/json" \
  -d '{"query":"unfair dismissal fair reason ERA 1996 s98 ACAS","claim_type":"unfair_dismissal"}')
echo "$RAG" | grep -qE '"insufficient_grounding":false' && echo "$RAG" | grep -qiE "Employment Rights Act 1996" && ok "hybrid RAG grounded + cited" || bad "hybrid RAG: $(echo "$RAG"|head -c 120)"

step "12. FRONTEND static wiring"
for p in intake constructive_dismissal saved_case assessment; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/pages/$p.html")
  [ "$code" = "200" ] && ok "$p.html 200" || bad "$p.html HTTP $code"
done
curl -s "$BASE/pages/constructive_dismissal.html" | grep -q "api/workflows/constructive-dismissal" && ok "CD page wired to real API" || bad "CD page not wired"
curl -s "$BASE/pages/intake.html" | grep -q "constructive_dismissal.html" && ok "intake links to CD page" || bad "intake missing CD link"
curl -s "$BASE/pages/saved_case.html" | grep -qE "extracted_unconfirmed|extraction_status" && ok "saved_case confirmation render targets" || bad "saved_case confirmation missing"
curl -s "$BASE/pages/constructive_dismissal.html" | grep -qE 'id="error"|Could not assess' && ok "CD fail-closed/error render target" || bad "CD error state missing"
curl -s "$BASE/pages/constructive_dismissal.html" | grep -qiE "not a solicitor|not legal advice|self-help" && ok "CD legal-boundary notice" || bad "CD boundary notice missing"
! curl -s "$BASE/pages/constructive_dismissal.html" | grep -qiE "mockResult|fakeData|TODO_MOCK" && ok "no mock result objects in CD page" || bad "mock objects present"

rm -f .proof_upload.pdf .proof_empty.png 2>/dev/null || true
echo
if [ "$fail" -ne 0 ]; then echo "WORKFLOW ABC PROOF: FAILED"; exit 1; fi
echo "WORKFLOW ABC PROOF: PASSED"
