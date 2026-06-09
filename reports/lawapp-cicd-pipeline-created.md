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
