#!/usr/bin/env bash
# End-to-end product gate  -  real auth→Brain answer; G10 provenance present with zero orphan chunks.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"; . scripts/lawapp/_gate_lib.sh

hdr "End-to-end product + G10 provenance"
p=$(brain_pod); [ -z "$p" ] && { fail "no running brain pod"; gate_result "final-end-to-end-product-gate"; }

# 1. Real auth → assessment answer (DB-backed, not static)
ans=$(KT exec -n "$NS_AI" "$p" -- python3 -c "
import urllib.request,json,os
B='http://localhost:8000'
def call(m,pth,b=None,h=None):
 d=json.dumps(b).encode() if b is not None else None
 r=urllib.request.Request(B+pth,data=d,method=m); r.add_header('Content-Type','application/json')
 [r.add_header(k,v) for k,v in (h or {}).items()]
 try: x=urllib.request.urlopen(r,timeout=60); return x.read().decode()
 except Exception as e: return '{\"error\":\"%s\"}'%e
e='e2e_'+os.urandom(4).hex()+'@lawapp.test'
call('POST','/auth/register',{'email':e,'password':'E2e!pass123'})
tok=json.loads(call('POST','/auth/token',{'email':e,'password':'E2e!pass123'})).get('access_token')
print(call('POST','/api/brain/trace',{'message':'Was my dismissal unfair after 3 years?','facts':{'years_service':3,'dismissed':True},'jurisdiction':'EW'},{'Authorization':'Bearer '+tok}))
" 2>/dev/null)
echo "$ans" | grep -q '"trace_id"' && pass "authenticated Brain answer returned" || fail "no authenticated Brain answer"

# 2. G10: provenance tables exist
ex=$(psql_rag "select to_regclass('public.corpus_chunks') is not null and to_regclass('public.legal_sources') is not null")
[ "$ex" = "t" ] && pass "G10 spine tables (legal_sources + corpus_chunks) exist" || fail "G10 spine tables missing"

# 3. G10: corpus_chunks populated AND zero orphans (every chunk has source linkage + hash)
cc=$(psql_rag "select count(*) from corpus_chunks")
if [ "${cc:-0}" -gt 0 ] 2>/dev/null; then
  pass "corpus_chunks populated (count=$cc)"
  orph=$(psql_rag "select count(*) from corpus_chunks where chunk_hash is null or source_url is null")
  if [ "${orph:-1}" = "0" ]; then pass "zero orphan chunks (no null chunk_hash/source_url)"; else fail "orphan chunks present (count=$orph)"; fi
else
  fail "corpus_chunks EMPTY  -  G10 dataset not yet ingested (T-003/T-004 incomplete)"
fi

gate_result "final-end-to-end-product-gate"
