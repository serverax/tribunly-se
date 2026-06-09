#!/usr/bin/env bash
set -euo pipefail

echo "=================================================="
echo "LAWAPP CI/CD CONFIRMATION + AUTO REPAIR SCRIPT"
echo "Local project -> GitHub -> GitHub Actions -> K8s"
echo "=================================================="

PROJECT_DIR="/mnt/f/lawapp"
REPO="serverax/lawapp"
WORKFLOW=".github/workflows/lawapp-ci-cd.yml"
BRANCH="$(git branch --show-current 2>/dev/null || true)"

fail() {
  echo ""
  echo "❌ FAILED: $1"
  exit 1
}

ok() {
  echo "✅ $1"
}

warn() {
  echo "⚠️  $1"
}

cd "$PROJECT_DIR" || fail "Cannot enter $PROJECT_DIR"

echo ""
echo "1) Checking required tools..."
command -v git >/dev/null || fail "git is missing"
command -v gh >/dev/null || fail "GitHub CLI gh is missing"
command -v kubectl >/dev/null || fail "kubectl is missing"
ok "git, gh, kubectl found"

echo ""
echo "2) Checking git repo..."
git rev-parse --is-inside-work-tree >/dev/null || fail "Not inside a git repo"
BRANCH="$(git branch --show-current)"
[ -n "$BRANCH" ] || fail "Cannot detect current git branch"
ok "Current branch: $BRANCH"

echo ""
echo "3) Checking GitHub remote..."
REMOTE="$(git remote get-url origin 2>/dev/null || true)"
if [ -z "$REMOTE" ]; then
  warn "No origin remote found. Setting origin to git@github.com:$REPO.git"
  git remote add origin "git@github.com:$REPO.git"
else
  echo "Origin remote: $REMOTE"
fi

if ! git remote get-url origin | grep -Eq "github.com[:/]serverax/lawapp(.git)?$"; then
  warn "Origin remote is not serverax/lawapp. Repairing..."
  git remote set-url origin "git@github.com:$REPO.git"
fi
ok "Origin remote points to $REPO"

echo ""
echo "4) Checking GitHub authentication..."
gh auth status >/dev/null || fail "gh is not authenticated. Run: gh auth login"
ok "GitHub CLI authenticated"

echo ""
echo "5) Checking GitHub repo access..."
gh repo view "$REPO" >/dev/null || fail "Cannot access GitHub repo $REPO"
ok "GitHub repo accessible"

echo ""
echo "6) Checking Kubernetes access..."
kubectl cluster-info >/dev/null || fail "kubectl cannot reach cluster"
ok "kubectl can reach cluster"

echo ""
echo "7) Checking lawapp namespaces..."
for ns in lawapp-api lawapp-ai lawapp-rag lawapp-monitoring lawapp-security; do
  if kubectl get ns "$ns" >/dev/null 2>&1; then
    ok "Namespace exists: $ns"
  else
    warn "Namespace missing: $ns - creating it"
    kubectl create ns "$ns"
  fi
done

echo ""
echo "8) Checking GitHub KUBECONFIG_B64 secret..."
if gh secret list --repo "$REPO" | grep -q '^KUBECONFIG_B64'; then
  ok "GitHub secret KUBECONFIG_B64 exists"
else
  warn "KUBECONFIG_B64 missing. Creating from ~/.kube/config"
  [ -f "$HOME/.kube/config" ] || fail "~/.kube/config not found"
  base64 -w0 "$HOME/.kube/config" | gh secret set KUBECONFIG_B64 --repo "$REPO"
  ok "KUBECONFIG_B64 created"
fi

echo ""
echo "9) Detecting Kubernetes manifest path..."
MANIFEST_PATH=""
if [ -d "infra/k8s" ]; then
  MANIFEST_PATH="infra/k8s"
elif [ -d "k8s" ]; then
  MANIFEST_PATH="k8s"
elif [ -d "deploy/k8s" ]; then
  MANIFEST_PATH="deploy/k8s"
else
  fail "No Kubernetes manifest directory found. Expected infra/k8s, k8s, or deploy/k8s"
fi
ok "Using manifest path: $MANIFEST_PATH"

echo ""
echo "10) Creating/repairing GitHub Actions workflow..."
mkdir -p .github/workflows

cat > "$WORKFLOW" <<YAML
name: lawapp-ci-cd

on:
  push:
    branches:
      - main
      - master
      - "$BRANCH"
  workflow_dispatch:

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Show repo state
        run: |
          pwd
          ls -la
          git rev-parse --short HEAD

      - name: Detect project structure
        run: |
          echo "Checking lawapp structure"
          find . -maxdepth 3 -type f | sed 's#^\./##' | sort | head -200

      - name: Basic static checks
        run: |
          set -e
          test -d "$MANIFEST_PATH"
          echo "Manifest path exists: $MANIFEST_PATH"

  deploy:
    needs: ci
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Install kubectl
        uses: azure/setup-kubectl@v4

      - name: Configure kubeconfig
        run: |
          mkdir -p ~/.kube
          echo "\${{ secrets.KUBECONFIG_B64 }}" | base64 -d > ~/.kube/config
          chmod 600 ~/.kube/config

      - name: Confirm cluster access
        run: |
          kubectl cluster-info
          kubectl get nodes -o wide

      - name: Ensure namespaces exist
        run: |
          for ns in lawapp-api lawapp-ai lawapp-rag lawapp-monitoring lawapp-security; do
            kubectl get ns "\$ns" >/dev/null 2>&1 || kubectl create ns "\$ns"
          done
          kubectl get ns | grep lawapp

      - name: Apply Kubernetes manifests
        run: |
          kubectl apply -f "$MANIFEST_PATH" --recursive

      - name: Restart lawapp deployments if present
        run: |
          for ns in lawapp-api lawapp-ai lawapp-rag lawapp-monitoring lawapp-security; do
            echo "Namespace: \$ns"
            kubectl -n "\$ns" get deploy || true
            for d in \$(kubectl -n "\$ns" get deploy -o name 2>/dev/null || true); do
              kubectl -n "\$ns" rollout restart "\$d"
            done
          done

      - name: Confirm rollout
        run: |
          set +e
          for ns in lawapp-api lawapp-ai lawapp-rag lawapp-monitoring lawapp-security; do
            echo "==== \$ns ===="
            kubectl -n "\$ns" get pods,svc,deploy -o wide || true
            for d in \$(kubectl -n "\$ns" get deploy -o name 2>/dev/null || true); do
              kubectl -n "\$ns" rollout status "\$d" --timeout=180s
            done
          done

      - name: Show events if anything failed
        if: always()
        run: |
          for ns in lawapp-api lawapp-ai lawapp-rag lawapp-monitoring lawapp-security; do
            echo "==== EVENTS \$ns ===="
            kubectl -n "\$ns" get events --sort-by=.lastTimestamp | tail -50 || true
          done
YAML

ok "Workflow created/repaired: $WORKFLOW"

echo ""
echo "11) Creating local push helper..."
mkdir -p scripts

cat > scripts/push-and-deploy.sh <<'PUSH'
#!/usr/bin/env bash
set -euo pipefail

MSG="${1:-lawapp ci cd update}"
REPO="serverax/lawapp"
BRANCH="$(git branch --show-current)"

echo "Current branch: $BRANCH"

git status --short

git add .
git commit -m "$MSG" || echo "No changes to commit"

git push -u origin "$BRANCH"

echo ""
echo "Triggering GitHub Actions workflow..."
gh workflow run lawapp-ci-cd.yml --repo "$REPO" --ref "$BRANCH"

echo ""
echo "Latest runs:"
gh run list --repo "$REPO" --workflow lawapp-ci-cd.yml --limit 5

echo ""
echo "To watch:"
echo "gh run watch --repo $REPO --workflow lawapp-ci-cd.yml"
PUSH

chmod +x scripts/push-and-deploy.sh
ok "Created scripts/push-and-deploy.sh"

echo ""
echo "12) Local Kubernetes visibility check..."
for ns in lawapp-api lawapp-ai lawapp-rag lawapp-monitoring lawapp-security; do
  echo ""
  echo "==== $ns ===="
  kubectl -n "$ns" get pods,svc,deploy 2>/dev/null || true
done

echo ""
echo "=================================================="
echo "✅ CI/CD confirmation script finished."
echo ""
echo "NEXT COMMAND:"
echo "bash scripts/push-and-deploy.sh \"confirm lawapp cicd automation\""
echo ""
echo "THEN WATCH:"
echo "gh run watch --repo $REPO --workflow lawapp-ci-cd.yml"
echo "=================================================="
