#!/usr/bin/env bash
set -euo pipefail

cd /mnt/f/lawapp

REPO="serverax/lawapp"
KUBECONFIG_PATH="${KUBECONFIG:-$HOME/.kube/config-hetzner}"

gh auth status

if [ ! -f "$KUBECONFIG_PATH" ]; then
  echo "Kubeconfig not found: $KUBECONFIG_PATH"
  exit 1
fi

export KUBECONFIG="$KUBECONFIG_PATH"
kubectl get nodes

base64 -w 0 "$KUBECONFIG_PATH" | gh secret set KUBE_CONFIG_B64 --repo "$REPO"

read -s -p "POSTGRES_PASSWORD: " POSTGRES_PASSWORD
echo
printf "%s" "$POSTGRES_PASSWORD" | gh secret set POSTGRES_PASSWORD --repo "$REPO"

openssl rand -base64 32 | gh secret set JWT_SECRET --repo "$REPO"

python3 - <<'PY2' | gh secret set ENCRYPTION_KEY --repo "$REPO"
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY2

read -s -p "ANTHROPIC_API_KEY: " ANTHROPIC_API_KEY
echo
printf "%s" "$ANTHROPIC_API_KEY" | gh secret set ANTHROPIC_API_KEY --repo "$REPO"

gh secret list --repo "$REPO"
