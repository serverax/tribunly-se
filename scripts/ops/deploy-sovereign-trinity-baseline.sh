#!/usr/bin/env bash
set -euo pipefail

NS_AI="lawapp-ai"
NS_RAG="lawapp-rag"
NS_API="lawapp-api"
MODEL="${MODEL:-qwen2.5:3b-instruct-q6_K}"
CPUSET="${CPUSET:-0-3}"

echo "=== 0. Pre-flight ==="
kubectl get nodes -o wide
kubectl get ns "${NS_AI}" "${NS_RAG}" "${NS_API}" >/dev/null

echo "=== 1. Create inference policy config ==="
kubectl -n "${NS_AI}" create configmap lawapp-inference-policy \
  --from-literal=OLLAMA_MODEL="${MODEL}" \
  --from-literal=CPUSET="${CPUSET}" \
  --from-literal=ROUTING_STRATEGY="deterministic_first" \
  --from-literal=LLM_LAST_RESORT_ONLY="true" \
  --from-literal=LOCAL_LLM_ONLY="true" \
  --from-literal=NO_AI_AUTHORITY="true" \
  --from-literal=REQUIRE_LOCAL_CORPUS_UUID_CITATION="true" \
  --from-literal=REQUIRE_PII_SCRUBBING="true" \
  --from-literal=REQUIRE_GRAPH_CRITIC="true" \
  --from-literal=REQUIRE_CITATION_CHECK="true" \
  --from-literal=DOMAIN_WHITELIST="legislation.gov.uk,caselaw.nationalarchives.gov.uk,www.acas.org.uk,acas.org.uk" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "=== 2. Deploy Ollama DaemonSet + Local service ==="
cat > infra/k8s/inference/ollama-inference-daemonset.yaml <<YAML
apiVersion: v1
kind: Service
metadata:
  name: ollama-inference
  namespace: ${NS_AI}
  labels:
    app.kubernetes.io/name: ollama-inference
spec:
  type: ClusterIP
  internalTrafficPolicy: Local
  selector:
    app.kubernetes.io/name: ollama-inference
  ports:
    - name: http
      port: 11434
      targetPort: 11434
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: ollama-inference
  namespace: ${NS_AI}
  labels:
    app.kubernetes.io/name: ollama-inference
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: ollama-inference
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ollama-inference
    spec:
      terminationGracePeriodSeconds: 30
      tolerations:
        - operator: Exists
      volumes:
        - name: ollama-data
          hostPath:
            path: /var/lib/lawapp/ollama
            type: DirectoryOrCreate
        - name: tools
          emptyDir: {}
      initContainers:
        - name: copy-busybox-taskset
          image: busybox:1.36
          command:
            - /bin/sh
            - -lc
            - |
              set -e
              cp /bin/busybox /tools/busybox
              chmod +x /tools/busybox
              /tools/busybox taskset --help >/dev/null
          volumeMounts:
            - name: tools
              mountPath: /tools
      containers:
        - name: ollama
          image: ollama/ollama:latest
          imagePullPolicy: IfNotPresent
          env:
            - name: OLLAMA_HOST
              value: "0.0.0.0:11434"
            - name: OLLAMA_MODELS
              value: "/root/.ollama/models"
            - name: OLLAMA_KEEP_ALIVE
              value: "24h"
            - name: OLLAMA_NUM_PARALLEL
              value: "1"
            - name: OLLAMA_MAX_LOADED_MODELS
              value: "1"
            - name: OLLAMA_MODEL
              valueFrom:
                configMapKeyRef:
                  name: lawapp-inference-policy
                  key: OLLAMA_MODEL
            - name: CPUSET
              valueFrom:
                configMapKeyRef:
                  name: lawapp-inference-policy
                  key: CPUSET
          ports:
            - name: http
              containerPort: 11434
          resources:
            requests:
              cpu: "4"
              memory: "6Gi"
            limits:
              cpu: "4"
              memory: "10Gi"
          volumeMounts:
            - name: ollama-data
              mountPath: /root/.ollama
            - name: tools
              mountPath: /tools
          command:
            - /bin/sh
            - -lc
            - |
              set -e

              echo "Starting temporary Ollama server for model preload..."
              ollama serve &
              PID="\$!"

              for i in \$(seq 1 120); do
                if ollama list >/dev/null 2>&1; then
                  break
                fi
                sleep 2
              done

              echo "Pulling model: \${OLLAMA_MODEL}"
              ollama pull "\${OLLAMA_MODEL}"

              echo "Stopping temporary server..."
              kill "\${PID}" || true
              wait "\${PID}" || true

              echo "Starting pinned Ollama server on CPU set \${CPUSET}"
              exec /tools/busybox taskset -c "\${CPUSET}" ollama serve
          readinessProbe:
            httpGet:
              path: /api/tags
              port: 11434
            initialDelaySeconds: 20
            periodSeconds: 10
            failureThreshold: 18
          livenessProbe:
            httpGet:
              path: /api/tags
              port: 11434
            initialDelaySeconds: 60
            periodSeconds: 30
            failureThreshold: 5
YAML

kubectl apply -f infra/k8s/inference/ollama-inference-daemonset.yaml
kubectl -n "${NS_AI}" rollout status ds/ollama-inference --timeout=900s

echo "=== 3. Apply restricted network policy ==="
cat > infra/k8s/inference/ollama-network-policy.yaml <<YAML
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ollama-inference-local-callers-only
  namespace: ${NS_AI}
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: ollama-inference
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ${NS_AI}
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ${NS_API}
      ports:
        - protocol: TCP
          port: 11434
YAML

kubectl apply -f infra/k8s/inference/ollama-network-policy.yaml

echo "=== 4. Patch brain/orchestrator deployments if present ==="
for DEP in lawapp-brain lawapp-orchestrator lawapp-api; do
  if kubectl -n "${NS_AI}" get deploy "${DEP}" >/dev/null 2>&1; then
    TARGET_NS="${NS_AI}"
  elif kubectl -n "${NS_API}" get deploy "${DEP}" >/dev/null 2>&1; then
    TARGET_NS="${NS_API}"
  else
    echo "Deployment ${DEP} not found, skipping patch."
    continue
  fi

  echo "Patching ${TARGET_NS}/${DEP}"
  kubectl -n "${TARGET_NS}" set env deploy/"${DEP}" \
    OLLAMA_BASE_URL="http://ollama-inference.${NS_AI}.svc.cluster.local:11434" \
    OLLAMA_MODEL="${MODEL}" \
    ROUTING_STRATEGY="deterministic_first" \
    LLM_LAST_RESORT_ONLY="true" \
    NO_AI_AUTHORITY="true" \
    REQUIRE_LOCAL_CORPUS_UUID_CITATION="true" \
    REQUIRE_PII_SCRUBBING="true" \
    REQUIRE_GRAPH_CRITIC="true" \
    REQUIRE_CITATION_CHECK="true" \
    DSPY_EVOLUTION_ENABLED="true" \
    DSPY_FAIL_CLOSED="true" \
    DOMAIN_WHITELIST="legislation.gov.uk,caselaw.nationalarchives.gov.uk,www.acas.org.uk,acas.org.uk"

  kubectl -n "${TARGET_NS}" rollout status deploy/"${DEP}" --timeout=300s || true
done

echo "=== 5. Deploy crawler policy ConfigMap ==="
kubectl -n "${NS_RAG}" create configmap lawapp-crawler-policy \
  --from-literal=DOMAIN_WHITELIST="legislation.gov.uk,caselaw.nationalarchives.gov.uk,www.acas.org.uk,acas.org.uk" \
  --from-literal=FAIL_CLOSED_ON_UNVERIFIED_SOURCE="true" \
  --from-literal=INGESTION_CRITIC_REQUIRED="true" \
  --from-literal=REJECT_IF_NO_STATUTORY_REFERENCE="true" \
  --from-literal=NO_OPEN_WEB_LEARNING="true" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "=== 6. Deploy crawler CronJob if image exists in your registry ==="
cat > infra/k8s/inference/legal-crawler-cronjob.yaml <<YAML
apiVersion: batch/v1
kind: CronJob
metadata:
  name: legal-corpus-crawler
  namespace: ${NS_RAG}
spec:
  schedule: "17 */6 * * *"
  concurrencyPolicy: Forbid
  failedJobsHistoryLimit: 3
  successfulJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 1
      template:
        metadata:
          labels:
            app.kubernetes.io/name: legal-corpus-crawler
        spec:
          restartPolicy: Never
          containers:
            - name: crawler
              image: ghcr.io/serverax/lawapp-crawler:latest
              imagePullPolicy: IfNotPresent
              envFrom:
                - configMapRef:
                    name: lawapp-crawler-policy
              env:
                - name: INGESTION_MODE
                  value: "official_sources_only"
                - name: LEGAL_CORPUS_REGISTRY_REQUIRED
                  value: "true"
                - name: INGESTION_CRITIC_REQUIRED
                  value: "true"
                - name: NO_AI_AUTHORITY
                  value: "true"
              command:
                - /bin/sh
                - -lc
                - |
                  set -e
                  echo "Crawler must enforce DOMAIN_WHITELIST and IngestionCritic in code."
                  python -m ingestion.crawler --fail-closed --official-sources-only
YAML

kubectl apply -f infra/k8s/inference/legal-crawler-cronjob.yaml || {
  echo "Crawler image or manifest failed. This is NOT a PASS. Build/push ghcr.io/serverax/lawapp-crawler:latest first."
}

echo "=== 7. Show final objects ==="
kubectl -n "${NS_AI}" get ds,po,svc,ep,endpointslice -l app.kubernetes.io/name=ollama-inference -o wide
kubectl -n "${NS_RAG}" get cm,cronjob | grep -E 'lawapp-crawler-policy|legal-corpus-crawler' || true

echo "Baseline deploy finished. Now run scripts/ops/verify-sovereign-trinity-baseline.sh"
