#!/usr/bin/env bash
set -euo pipefail

export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config-hetzner}"

kubectl get nodes -o wide
kubectl get pods -n lawapp-api || true
kubectl get svc -n lawapp-api || true
kubectl get ingress -n lawapp-api || true
kubectl get pods -n lawapp-rag || true
kubectl get pods -n lawapp-ai || true
kubectl get pods -n lawapp-security || true
kubectl get pods -n lawapp-monitoring || true
kubectl get events -A --sort-by=.lastTimestamp | tail -80 || true
