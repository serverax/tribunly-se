#!/usr/bin/env bash
# Kubernetes runtime gate — fails on CrashLoopBackOff, unexpected Pending, not-ready core pods.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"; . scripts/lawapp/_gate_lib.sh

hdr "Kubernetes runtime"

# 1. Core deployments must have AVAILABLE replicas > 0
for d in "$NS_AI/lawapp-brain" "$NS_API/lawapp-backend" "$NS_AI/lawapp-rules-engine" \
         "$NS_RAG/lawapp-rag-retrieval" "$NS_RAG/lawapp-rag-ingestion"; do
  ns="${d%/*}"; name="${d#*/}"
  avail=$(KT get deploy "$name" -n "$ns" -o jsonpath='{.status.availableReplicas}' 2>/dev/null)
  if [ "${avail:-0}" -ge 1 ] 2>/dev/null; then pass "$d available=$avail"; else fail "$d available=${avail:-0}"; fi
done

# 2. No CrashLoopBackOff in any lawapp namespace
cl=$(for ns in "$NS_AI" "$NS_API" "$NS_RAG"; do KT get pods -n "$ns" --no-headers 2>/dev/null \
      | grep -c "CrashLoopBackOff"; done | paste -sd+ | bc 2>/dev/null)
if [ "${cl:-0}" = "0" ]; then pass "no CrashLoopBackOff pods"; else fail "$cl CrashLoopBackOff pod(s)"; fi

# 3. No unexpected Pending pods (exclude intentionally scaled-to-0 → no pods at all)
pend=$(for ns in "$NS_AI" "$NS_API" "$NS_RAG"; do KT get pods -n "$ns" --no-headers 2>/dev/null \
      | awk '$3=="Pending"{print}'; done | wc -l)
if [ "${pend:-0}" = "0" ]; then pass "no Pending pods"; else fail "$pend Pending pod(s)"; fi

# 4. Brain readiness endpoint must be 200 via Service path
code=$(brain_http /health)
if [ "$code" = "200" ]; then pass "brain /health = 200"; else fail "brain /health = $code"; fi

# 5. Distributed-services wiring (SA-014) must pass — service endpoints + service-to-service paths.
if [ -x scripts/lawapp/prove-microservices-wiring.sh ]; then
  if bash scripts/lawapp/prove-microservices-wiring.sh >/tmp/msw.out 2>&1; then pass "microservices wiring proof"; else fail "microservices wiring proof (see /tmp/msw.out)"; fi
else fail "scripts/lawapp/prove-microservices-wiring.sh missing"; fi

gate_result "final-kubernetes-runtime-gate"
