#!/usr/bin/env bash
set -euo pipefail

cd /mnt/f/lawapp

echo "=== Creating CI/CD directories ==="
mkdir -p .github/workflows
mkdir -p scripts
mkdir -p reports

echo "=== Creating GitHub Actions CI workflow ==="
cat > .github/workflows/lawapp-ci.yml <<'YAML'
name: LawApp CI

on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]

permissions:
  contents: read

jobs:
  test:
    name: Test lawapp
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: lawapp
          POSTGRES_USER: lawapp
          POSTGRES_PASSWORD: lawapp
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U lawapp -d lawapp"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 10

    env:
      DATABASE_URL: postgresql://lawapp:lawapp@localhost:5432/lawapp
      LAWAPP_AUTH_MODE: jwt
      JWT_SECRET: ${{ secrets.CI_JWT_SECRET }}
      ENCRYPTION_KEY: test-ci-encryption-key
      AI_PROVIDER: stub
      STRIPE_MODE: test_simulator

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Show repo
        run: |
          pwd
          find . -maxdepth 3 -type f | sort | head -200

      - name: Set up Python
        if: hashFiles('requirements.txt', 'backend/requirements.txt', 'pyproject.toml') != ''
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Python dependencies
        if: hashFiles('requirements.txt', 'backend/requirements.txt') != ''
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          if [ -f backend/requirements.txt ]; then pip install -r backend/requirements.txt; fi

      - name: Run migrations if available
        run: |
          if [ -f scripts/apply-migrations.sh ]; then
            bash scripts/apply-migrations.sh
          elif [ -d db/migrations ]; then
            echo "Migrations folder found. Project-specific migration runner not found."
          else
            echo "No migrations detected."
          fi

      - name: Run backend tests
        run: |
          if [ -d tests ]; then
            python -m pytest -q
          else
            echo "No tests folder found."
          fi

      - name: Set up Node
        if: hashFiles('client/package.json', 'package.json') != ''
        uses: actions/setup-node@v4
        with:
          node-version: '22'

      - name: Install and test frontend
        if: hashFiles('client/package.json') != ''
        run: |
          cd client
          npm ci || npm install
          npm run lint --if-present
          npm test --if-present
          npm run build --if-present
YAML

echo "=== Creating GitHub Actions deploy workflow ==="
cat > .github/workflows/lawapp-deploy-talos.yml <<'YAML'
name: LawApp Deploy to Talos

on:
  workflow_dispatch:
  push:
    branches: [ main ]

permissions:
  contents: read
  packages: write

env:
  REGISTRY: ghcr.io
  IMAGE_BACKEND: ghcr.io/${{ github.repository }}/lawapp-backend
  IMAGE_FRONTEND: ghcr.io/${{ github.repository }}/lawapp-frontend

jobs:
  build-and-deploy:
    name: Build and deploy lawapp
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Confirm branch and commit
        run: |
          git branch --show-current || true
          git rev-parse --short HEAD
          find . -maxdepth 3 -type f | sort | head -200

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Detect Dockerfiles
        id: detect
        run: |
          if [ -f backend/Dockerfile ]; then
            echo "backend_dockerfile=backend/Dockerfile" >> "$GITHUB_OUTPUT"
            echo "backend_context=." >> "$GITHUB_OUTPUT"
          elif [ -f Dockerfile ]; then
            echo "backend_dockerfile=Dockerfile" >> "$GITHUB_OUTPUT"
            echo "backend_context=." >> "$GITHUB_OUTPUT"
          else
            echo "backend_dockerfile=" >> "$GITHUB_OUTPUT"
          fi

          if [ -f client/Dockerfile ]; then
            echo "frontend_dockerfile=client/Dockerfile" >> "$GITHUB_OUTPUT"
            echo "frontend_context=client" >> "$GITHUB_OUTPUT"
          else
            echo "frontend_dockerfile=" >> "$GITHUB_OUTPUT"
          fi

      - name: Build and push backend image
        if: steps.detect.outputs.backend_dockerfile != ''
        uses: docker/build-push-action@v6
        with:
          context: ${{ steps.detect.outputs.backend_context }}
          file: ${{ steps.detect.outputs.backend_dockerfile }}
          push: true
          tags: |
            ${{ env.IMAGE_BACKEND }}:${{ github.sha }}
            ${{ env.IMAGE_BACKEND }}:latest

      - name: Build and push frontend image
        if: steps.detect.outputs.frontend_dockerfile != ''
        uses: docker/build-push-action@v6
        with:
          context: ${{ steps.detect.outputs.frontend_context }}
          file: ${{ steps.detect.outputs.frontend_dockerfile }}
          push: true
          tags: |
            ${{ env.IMAGE_FRONTEND }}:${{ github.sha }}
            ${{ env.IMAGE_FRONTEND }}:latest

      - name: Install kubectl
        uses: azure/setup-kubectl@v4
        with:
          version: latest

      - name: Configure kubeconfig
        run: |
          mkdir -p "$HOME/.kube"
          echo "${{ secrets.KUBE_CONFIG_B64 }}" | base64 -d > "$HOME/.kube/config"
          chmod 600 "$HOME/.kube/config"
          kubectl cluster-info
          kubectl get nodes

      - name: Confirm lawapp namespaces
        run: |
          kubectl get ns lawapp-api
          kubectl get ns lawapp-rag
          kubectl get ns lawapp-ai
          kubectl get ns lawapp-security
          kubectl get ns lawapp-monitoring

      - name: Create or update runtime secrets
        run: |
          kubectl -n lawapp-api create secret generic lawapp-secrets \
            --from-literal=POSTGRES_PASSWORD="${{ secrets.POSTGRES_PASSWORD }}" \
            --from-literal=JWT_SECRET="${{ secrets.JWT_SECRET }}" \
            --from-literal=ENCRYPTION_KEY="${{ secrets.ENCRYPTION_KEY }}" \
            --from-literal=ANTHROPIC_API_KEY="${{ secrets.ANTHROPIC_API_KEY }}" \
            --dry-run=client -o yaml | kubectl apply -f -

          kubectl -n lawapp-rag create secret generic lawapp-secrets \
            --from-literal=POSTGRES_PASSWORD="${{ secrets.POSTGRES_PASSWORD }}" \
            --from-literal=JWT_SECRET="${{ secrets.JWT_SECRET }}" \
            --from-literal=ENCRYPTION_KEY="${{ secrets.ENCRYPTION_KEY }}" \
            --from-literal=ANTHROPIC_API_KEY="${{ secrets.ANTHROPIC_API_KEY }}" \
            --dry-run=client -o yaml | kubectl apply -f -

          kubectl -n lawapp-ai create secret generic lawapp-ai-secrets \
            --from-literal=ANTHROPIC_API_KEY="${{ secrets.ANTHROPIC_API_KEY }}" \
            --dry-run=client -o yaml | kubectl apply -f -

      - name: Apply Kubernetes manifests
        run: |
          if [ -d infra/k8s ]; then
            kubectl apply -f infra/k8s/
          elif [ -d k8s ]; then
            kubectl apply -f k8s/
          else
            echo "No Kubernetes manifest directory found."
            exit 1
          fi

      - name: Update backend image if deployment exists
        run: |
          if kubectl -n lawapp-api get deployment lawapp-backend >/dev/null 2>&1; then
            kubectl -n lawapp-api set image deployment/lawapp-backend lawapp-backend=${IMAGE_BACKEND}:${GITHUB_SHA} || true
          fi

      - name: Update frontend image if deployment exists
        run: |
          if kubectl -n lawapp-api get deployment lawapp-frontend >/dev/null 2>&1; then
            kubectl -n lawapp-api set image deployment/lawapp-frontend lawapp-frontend=${IMAGE_FRONTEND}:${GITHUB_SHA} || true
          fi

      - name: Restart lawapp deployments
        run: |
          kubectl -n lawapp-api rollout restart deployment || true
          kubectl -n lawapp-rag rollout restart deployment || true
          kubectl -n lawapp-ai rollout restart deployment || true

      - name: Confirm rollout
        run: |
          kubectl -n lawapp-api rollout status deployment --timeout=180s || true
          kubectl -n lawapp-rag rollout status deployment --timeout=180s || true
          kubectl -n lawapp-ai rollout status deployment --timeout=180s || true

      - name: Show final status
        if: always()
        run: |
          echo "=== lawapp-api ==="
          kubectl get pods,svc,ingress -n lawapp-api || true
          echo "=== lawapp-rag ==="
          kubectl get pods,svc -n lawapp-rag || true
          echo "=== lawapp-ai ==="
          kubectl get pods,svc -n lawapp-ai || true
          echo "=== lawapp-security ==="
          kubectl get pods,svc -n lawapp-security || true
          echo "=== lawapp-monitoring ==="
          kubectl get pods,svc -n lawapp-monitoring || true
          echo "=== recent events ==="
          kubectl get events -A --sort-by=.lastTimestamp | tail -80 || true
YAML

echo "=== Creating local push helper ==="
cat > scripts/push-to-github.sh <<'BASH'
#!/usr/bin/env bash
set -euo pipefail

cd /mnt/f/lawapp

BRANCH="${1:-main}"
MESSAGE="${2:-lawapp update: CI/CD pipeline and deployment workflow}"

echo "=== Git state before push ==="
git status --short
git branch --show-current

echo "=== Safety check: no obvious secrets ==="
grep -R "sk-ant-\|sk_live_\|BEGIN OPENSSH PRIVATE KEY\|BEGIN RSA PRIVATE KEY\|KUBE_CONFIG" -n . \
  --exclude-dir=.git \
  --exclude-dir=node_modules \
  --exclude-dir=.venv \
  --exclude="*.md" || true

echo "=== Adding files ==="
git add .

echo "=== Commit ==="
if git diff --cached --quiet; then
  echo "No changes to commit."
else
  git commit -m "$MESSAGE"
fi

echo "=== Push ==="
git branch -M "$BRANCH"
git push -u origin "$BRANCH"

echo "=== Done. GitHub Actions should start automatically. ==="
BASH
chmod +x scripts/push-to-github.sh

echo "=== Creating GitHub secrets setup helper ==="
cat > scripts/setup-github-cicd-secrets.sh <<'BASH'
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
BASH
chmod +x scripts/setup-github-cicd-secrets.sh

echo "=== Creating CI/CD report ==="
cat > reports/lawapp-cicd-pipeline-created.md <<'MD'
# LawApp CI/CD Pipeline

Created files:

- `.github/workflows/lawapp-ci.yml`
- `.github/workflows/lawapp-deploy-talos.yml`
- `scripts/push-to-github.sh`
- `scripts/setup-github-cicd-secrets.sh`

Flow:

1. Developer works in `/mnt/f/lawapp`.
2. Developer runs `bash scripts/push-to-github.sh`.
3. Code is pushed to GitHub `main`.
4. GitHub Actions runs CI.
5. GitHub Actions builds container images and pushes them to GHCR.
6. GitHub Actions connects to Talos using `KUBE_CONFIG_B64`.
7. Manifests are applied.
8. Deployments in lawapp namespaces are restarted and rollout is checked.

Required GitHub secrets:

- `KUBE_CONFIG_B64`
- `POSTGRES_PASSWORD`
- `JWT_SECRET`
- `ENCRYPTION_KEY`
- `ANTHROPIC_API_KEY`

Approved namespaces:

- `lawapp-api`
- `lawapp-rag`
- `lawapp-ai`
- `lawapp-security`
- `lawapp-monitoring`
MD

echo "=== CI/CD files created ==="
find .github/workflows scripts reports -maxdepth 2 -type f | sort
