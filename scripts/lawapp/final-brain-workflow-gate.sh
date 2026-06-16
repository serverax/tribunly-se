#!/usr/bin/env bash
# Brain workflow gate  -  Brain is the only legal-answer path; trace persists; local LLM only.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"; . scripts/lawapp/_gate_lib.sh

hdr "Brain workflow"
p=$(brain_pod); [ -z "$p" ] && { fail "no running brain pod"; gate_result "final-brain-workflow-gate"; }

# 1. /health 200 + db connected
body=$(KT exec -n "$NS_AI" "$p" -- python3 -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/health',timeout=8).read().decode())" 2>/dev/null)
echo "$body" | grep -q '"db":"connected"' && pass "brain DB connected" || fail "brain DB not connected"

# 2. ai_provider is local ollama (NO external LLM by default)
echo "$body" | grep -q '"provider":"ollama"' && pass "AI provider = local ollama" || fail "AI provider is NOT local ollama"

# 3. /api/brain/trace runs the 19-step algorithm AND persists to brain_traces
before=$(psql_rag "select count(*) from brain_traces")
trace_json=$(KT exec -n "$NS_AI" "$p" -- python3 -c "
import urllib.request,json,os
B='http://localhost:8000'
def call(m,pth,b=None,h=None):
 d=json.dumps(b).encode() if b is not None else None
 r=urllib.request.Request(B+pth,data=d,method=m); r.add_header('Content-Type','application/json')
 [r.add_header(k,v) for k,v in (h or {}).items()]
 try: x=urllib.request.urlopen(r,timeout=60); return x.read().decode()
 except Exception as e: return '{\"error\":\"%s\"}'%e
e='gate_'+os.urandom(4).hex()+'@lawapp.test'
call('POST','/auth/register',{'email':e,'password':'Gate!pass123'})
tok=json.loads(call('POST','/auth/token',{'email':e,'password':'Gate!pass123'})).get('access_token')
print(call('POST','/api/brain/trace',{'message':'Dismissed after 3 years, no warning. Unfair?','facts':{'years_service':3,'dismissed':True},'jurisdiction':'EW'},{'Authorization':'Bearer '+tok}))
" 2>/dev/null)
after=$(psql_rag "select count(*) from brain_traces")
echo "$trace_json" | grep -q '"trace_id"' && pass "brain trace created (trace_id present)" || fail "no trace_id in brain response"
if [ "${after:-0}" -gt "${before:-0}" ] 2>/dev/null; then pass "brain trace persisted (brain_traces $before -> $after)"; else fail "brain trace NOT persisted ($before -> $after)"; fi

# 4. trace shows citation_verification stage (CitationGuard in the runtime path)
echo "$trace_json" | grep -qi 'citation' && pass "CitationGuard stage present in trace" || fail "no CitationGuard stage in trace"

gate_result "final-brain-workflow-gate"
