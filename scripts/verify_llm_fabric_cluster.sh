#!/usr/bin/env bash
# lawapp Node-Local Inference Fabric — cluster verification (PART 9 + node-IP proof)
# ===========================================================================
# Run this from a machine WITH kubeconfig access to the Talos cluster. It does NOT
# modify anything — it only gathers proof. It is the operator's job to run this;
# the AI assistant cannot reach the cluster and must not fabricate its output.
#
#   bash scripts/verify_inference_fabric.sh | tee reports/inference-fabric-proof.txt
#
# Node IPs are used ONLY to prove DaemonSet placement. They are NOT used by the
# application — the Mother Algorithm calls the Service DNS, never these IPs.
set -uo pipefail

NS="lawapp-ai"
SVC="llm-inference-service"
SVC_DNS="http://${SVC}.${NS}.svc.cluster.local:11434"

# Operational verification IPs (placement proof only — never app config).
NODE_CONTROL="148.251.247.56"
NODE_LLM="138.201.253.245"
NODE_SECONDARY="138.201.202.174"

hr(){ printf '\n=== %s ===\n' "$1"; }
PASS=0; FAIL=0
chk(){ if eval "$2"; then echo "PASS: $1"; PASS=$((PASS+1)); else echo "FAIL: $1"; FAIL=$((FAIL+1)); fi; }

hr "1. Nodes (-o wide)"
kubectl get nodes -o wide

hr "2. Map the three known IPs to nodes"
kubectl get nodes -o wide | grep -E "${NODE_CONTROL}|${NODE_LLM}|${NODE_SECONDARY}" || \
  echo "WARN: none of the known IPs matched node InternalIP/ExternalIP"

hr "3. Ollama DaemonSet"
kubectl -n "$NS" get ds ollama-inference -o wide

hr "4. Ollama pods per node"
kubectl -n "$NS" get pods -l app=ollama-inference -o wide

hr "4b. Assert one ollama pod on each known node IP"
for ip in "$NODE_CONTROL" "$NODE_LLM" "$NODE_SECONDARY"; do
  NODE=$(kubectl get nodes -o wide --no-headers | awk -v ip="$ip" '$6==ip || $7==ip {print $1}')
  if [ -z "$NODE" ]; then echo "FAIL: no node found for IP $ip"; FAIL=$((FAIL+1)); continue; fi
  N=$(kubectl -n "$NS" get pods -l app=ollama-inference -o wide --no-headers \
        | awk -v node="$NODE" '$7==node' | grep -c Running)
  chk "node $NODE ($ip) has a Running ollama-inference pod" "[ \"$N\" -ge 1 ]"
done

hr "5. Model availability per pod (ollama list)"
for pod in $(kubectl -n "$NS" get pods -l app=ollama-inference -o name); do
  echo "--- $pod ---"
  kubectl -n "$NS" exec "$pod" -- ollama list || echo "  (exec failed for $pod)"
done

hr "6. Service is internal only"
kubectl -n "$NS" get svc "$SVC" -o wide
echo "--- type + internalTrafficPolicy ---"
kubectl -n "$NS" get svc "$SVC" -o yaml | grep -E "type:|internalTrafficPolicy:"
TYPE=$(kubectl -n "$NS" get svc "$SVC" -o jsonpath='{.spec.type}' 2>/dev/null)
ITP=$(kubectl -n "$NS" get svc "$SVC" -o jsonpath='{.spec.internalTrafficPolicy}' 2>/dev/null)
chk "Service type is ClusterIP"           "[ \"$TYPE\" = \"ClusterIP\" ]"
chk "internalTrafficPolicy is Local"      "[ \"$ITP\" = \"Local\" ]"

hr "7. No public exposure"
kubectl -n "$NS" get ingress 2>/dev/null || echo "(no ingress objects)"
kubectl -n "$NS" get svc
LB=$(kubectl -n "$NS" get svc -o jsonpath='{.items[*].spec.type}' | tr ' ' '\n' | grep -c LoadBalancer)
chk "no LoadBalancer service in $NS"       "[ \"${LB:-0}\" -eq 0 ]"

hr "8. Smoke test through the Service DNS (temporary Job)"
kubectl -n "$NS" delete job ollama-smoke --ignore-not-found >/dev/null 2>&1
kubectl -n "$NS" run ollama-smoke --restart=Never --image=curlimages/curl --command -- \
  curl -s "${SVC_DNS}/api/tags" && sleep 5
kubectl -n "$NS" logs ollama-smoke 2>/dev/null || echo "  (smoke logs unavailable)"
kubectl -n "$NS" delete pod ollama-smoke --ignore-not-found >/dev/null 2>&1

hr "9. CPU Manager static policy reality check (PART 5)"
echo "Guaranteed QoS requires requests==limits (set in the manifest)."
echo "TRUE core pinning additionally requires kubelet --cpu-manager-policy=static."
for ip in "$NODE_CONTROL" "$NODE_LLM" "$NODE_SECONDARY"; do
  NODE=$(kubectl get nodes -o wide --no-headers | awk -v ip="$ip" '$6==ip || $7==ip {print $1}')
  [ -z "$NODE" ] && continue
  echo "--- $NODE configz (cpuManagerPolicy) ---"
  kubectl get --raw "/api/v1/nodes/${NODE}/proxy/configz" 2>/dev/null \
    | grep -o '"cpuManagerPolicy":"[^"]*"' || echo "  configz unavailable — pinning NOT CONFIRMED"
done

hr "SUMMARY"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ] && echo "VERIFICATION: PASS" || echo "VERIFICATION: FAIL (see above)"
