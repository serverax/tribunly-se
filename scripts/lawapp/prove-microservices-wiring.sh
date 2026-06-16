#!/usr/bin/env bash
#
# SA-014  -  prove lawapp distributed services are real, reachable and WIRED.
# FAIL-CLOSED: no `|| true`, no `echo PASS`, no continue-on-error. Exits non-zero on any failure.
# Read-only / additive evidence only. Requires kubectl context with lawapp-* namespaces.
#
# Asserts:
#   1. backend /health == 200 and db:connected
#   2. backend /cases unauthenticated == 401
#   3. brain /health == 200
#   4. brain trace persists (brain_traces count increases by >=1)
#   5. brain trace JSON shows RAG (retrieve_legal_evidence) + citation (verify_citations) stages
#   6. a pgvector retrieval returns a real chunk with source_id
#   7. every k8s Service in lawapp-* has non-empty endpoints
#        EXCEPT known-dead llm-inference-service and scaled-0 reasoning-worker (listed/allowed)
#   8. no CrashLoopBackOff among critical (lawapp-ai/api/rag/security) pods
#   9. no unexpected Pending among critical pods
#
set -Eeuo pipefail

NS_AI=lawapp-ai; NS_API=lawapp-api; NS_RAG=lawapp-rag; NS_SEC=lawapp-security
PG_RAG="lawapp-rag/lawapp-postgres-0"   # primary DB (corpus + brain_traces)
ALLOWED_NO_ENDPOINTS="llm-inference-service"   # known DEAD-SERVICE (selector mismatch; documented)

red(){ printf '\033[31m%s\033[0m\n' "$*"; }
grn(){ printf '\033[32m%s\033[0m\n' "$*"; }
hdr(){ printf '\n=== %s ===\n' "$*"; }
fail(){ red "FAIL: $*"; exit 1; }

pod_of(){ kubectl get pods -n "$1" -l "app=$2" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null; }

hdr "1. backend /health == 200, db:connected"
BPOD=$(pod_of "$NS_API" lawapp-backend); [ -n "$BPOD" ] || fail "no backend pod"
BH=$(kubectl exec -n "$NS_API" "$BPOD" -- curl -s -m 10 http://localhost:8000/health)
echo "$BH" | grep -q '"status":"ok"' || fail "backend health not ok: $BH"
echo "$BH" | grep -q '"db":"connected"' || fail "backend db not connected: $BH"
grn "backend /health ok, db connected"

hdr "2. backend /cases unauthenticated == 401"
CODE=$(kubectl exec -n "$NS_API" "$BPOD" -- curl -s -m 10 -o /dev/null -w '%{http_code}' http://localhost:8000/cases)
[ "$CODE" = "401" ] || fail "/cases unauth expected 401, got $CODE"
grn "backend /cases unauth = 401"

hdr "3. brain /health == 200"
RPOD=$(pod_of "$NS_AI" lawapp-brain); [ -n "$RPOD" ] || fail "no brain pod"
RCODE=$(kubectl exec -n "$NS_AI" "$RPOD" -- curl -s -m 10 -o /dev/null -w '%{http_code}' http://localhost:8000/health)
[ "$RCODE" = "200" ] || fail "brain /health expected 200, got $RCODE"
grn "brain /health = 200"

hdr "4+5. brain trace persists AND shows RAG + citation stages"
BEFORE=$(kubectl exec -n lawapp-rag lawapp-postgres-0 -- sh -c 'psql -U lawapp_user -d lawapp -tAc "SELECT count(*) FROM brain_traces;"' | tr -d '[:space:]')
[ -n "$BEFORE" ] || fail "could not read brain_traces count"
TS=$(date +%s); EMAIL="sa014-wire-${TS}@evidence.local"; PW="Test123!pass"
kubectl exec -n "$NS_AI" "$RPOD" -- curl -s -m 10 -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' -d "{\"email\":\"$EMAIL\",\"password\":\"$PW\"}" \
  | grep -q '"user_id"' || fail "register failed"
TOK=$(kubectl exec -n "$NS_AI" "$RPOD" -- curl -s -m 10 -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' -d "{\"email\":\"$EMAIL\",\"password\":\"$PW\"}")
JWT=$(printf '%s' "$TOK" | python3 -c 'import json,sys
try: print(json.load(sys.stdin)["access_token"])
except Exception: pass')
[ -n "$JWT" ] || fail "no JWT (token resp: $TOK)"
# brain trace endpoint is rate-limited (20/min); retry once on 429.
trace_call(){ kubectl exec -n "$NS_AI" "$RPOD" -- curl -s -m 60 -w '\n__HTTP:%{http_code}' -X POST http://localhost:8000/api/brain/trace \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $JWT" \
  -d '{"message":"I was dismissed after 3 years for raising a health and safety complaint.","facts":{"years_service":3},"jurisdiction":"EW"}'; }
RAW=$(trace_call)
HTTP=$(printf '%s' "$RAW" | sed -n 's/.*__HTTP:\([0-9]*\)$/\1/p')
if [ "$HTTP" = "429" ]; then echo "  (429 rate-limited, retrying in 5s)"; sleep 5; RAW=$(trace_call); HTTP=$(printf '%s' "$RAW" | sed -n 's/.*__HTTP:\([0-9]*\)$/\1/p'); fi
[ "$HTTP" = "200" ] || fail "brain trace HTTP $HTTP (body: $(printf '%s' "$RAW" | head -c 200))"
TRACE=$(printf '%s' "$RAW" | sed 's/__HTTP:[0-9]*$//')
TRACE_JSON="$TRACE" python3 <<'PY' || fail "trace JSON missing RAG/citation stages"
import json,os
d=json.loads(os.environ["TRACE_JSON"]); t=d["trace"]
steps={s["step"]:s["status"] for s in t["steps"]}
assert "retrieve_legal_evidence" in steps, "no RAG retrieve stage"
assert "verify_citations" in steps, "no citation verify stage"
assert t.get("rag_sources"), "rag_sources empty"
assert t.get("trace_id"), "no trace_id"
print("  trace_id=%s rag_sources=%s sources=%s citations_verified=%s" % (
    t["trace_id"], t["rag_sources"], t.get("sources_retrieved"), t.get("citations_verified")))
PY
AFTER=$(kubectl exec -n lawapp-rag lawapp-postgres-0 -- sh -c 'psql -U lawapp_user -d lawapp -tAc "SELECT count(*) FROM brain_traces;"' | tr -d '[:space:]')
[ "$AFTER" -gt "$BEFORE" ] || fail "brain_traces did not increase ($BEFORE -> $AFTER)"
grn "brain trace persisted ($BEFORE -> $AFTER) with RAG + citation stages"

hdr "6. pgvector retrieval returns a real chunk with source_id"
SRC=$(kubectl exec -n lawapp-rag lawapp-postgres-0 -- sh -c \
  'psql -U lawapp_user -d lawapp -tAc "SELECT source_id FROM corpus_chunks WHERE embedding IS NOT NULL AND source_id IS NOT NULL ORDER BY embedding <=> (SELECT embedding FROM corpus_chunks WHERE embedding IS NOT NULL ORDER BY id LIMIT 1) LIMIT 1;"' | tr -d '[:space:]')
[ -n "$SRC" ] || fail "pgvector retrieval returned no source_id"
grn "pgvector nearest-neighbour returned real chunk source_id=$SRC"

hdr "7. every lawapp-* k8s Service has endpoints (except known dead/scaled-0)"
EP_FAIL=0
for NS in "$NS_AI" "$NS_API" "$NS_RAG" "$NS_SEC"; do
  while read -r SVC EPS; do
    [ -z "$SVC" ] && continue
    case " $ALLOWED_NO_ENDPOINTS " in *" $SVC "*)
      echo "  ALLOWED-EMPTY: $NS/$SVC (known DEAD-SERVICE, documented)"; continue;; esac
    if [ "$EPS" = "<none>" ] || [ -z "$EPS" ]; then
      red "  NO ENDPOINTS: $NS/$SVC"; EP_FAIL=1
    else
      echo "  ok: $NS/$SVC -> $EPS"
    fi
  done < <(kubectl get endpoints -n "$NS" --no-headers 2>/dev/null | awk '{print $1, $2}')
done
[ "$EP_FAIL" = "0" ] || fail "one or more services have no endpoints"
grn "all required services have endpoints"

hdr "8+9. no CrashLoopBackOff / unexpected Pending in critical namespaces"
for NS in "$NS_AI" "$NS_API" "$NS_RAG" "$NS_SEC"; do
  BAD=$(kubectl get pods -n "$NS" --no-headers 2>/dev/null | awk '$3=="CrashLoopBackOff" || $3=="Pending" || $3=="ImagePullBackOff" || $3=="InvalidImageName" {print $1"="$3}')
  if [ -n "$BAD" ]; then red "  $NS bad pods: $BAD"; fail "critical pod in bad state in $NS"; fi
done
grn "no CrashLoop / unexpected Pending in critical namespaces"

hdr "RESULT"
grn "SA-014 microservices wiring: ALL CRITICAL ASSERTIONS PASSED"
echo "(Known/allowed exclusions: llm-inference-service DEAD-SERVICE, lawapp-reasoning-worker SCALED-0.)"
exit 0
