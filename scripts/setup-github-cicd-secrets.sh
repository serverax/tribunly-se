#!/usr/bin/env bash
set -euo pipefail

cd /mnt/f/lawapp

echo "This script sets GitHub Actions secrets for lawapp."
echo "It does not write secrets into the repo."

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is missing. Install GitHub CLI first."
  exit 1
fi

gh auth status

export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config-hetzner}"

if [ ! -f "$KUBECONFIG" ]; then
  echo "Kubeconfig not found at: $KUBECONFIG"
  echo "Set it first:"
  echo "export KUBECONFIG=\$HOME/.kube/config-hetzner"
  exit 1
fi

echo "=== Testing Talos cluster access ==="
kubectl get nodes
kubectl get ns | grep lawapp || true

echo "=== Setting KUBE_CONFIG_B64 ==="
base64 -w 0 "$KUBECONFIG" | gh secret set KUBE_CONFIG_B64

echo "=== Set POSTGRES_PASSWORD ==="
read -s -p "POSTGRES_PASSWORD: " POSTGRES_PASSWORD
echo
printf "%s" "$POSTGRES_PASSWORD" | gh secret set POSTGRES_PASSWORD

echo "=== Generate/set JWT_SECRET ==="
openssl rand -base64 32 | gh secret set JWT_SECRET

echo "=== Generate/set ENCRYPTION_KEY ==="
python3 - <<'PY' | gh secret set ENCRYPTION_KEY
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY

echo "=== Set ANTHROPIC_API_KEY ==="
read -s -p "ANTHROPIC_API_KEY: " ANTHROPIC_API_KEY
echo
printf "%s" "$ANTHROPIC_API_KEY" | gh secret set ANTHROPIC_API_KEY

echo "=== Secrets configured ==="
gh secret list
