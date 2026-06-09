# LawApp Full CI/CD Setup

Flow:

/mnt/f/lawapp
-> GitHub serverax/lawapp
-> GitHub Actions CI
-> GHCR image build
-> Talos deploy
-> lawapp namespaces

Required GitHub Secrets:

- KUBE_CONFIG_B64
- POSTGRES_PASSWORD
- JWT_SECRET
- ENCRYPTION_KEY
- ANTHROPIC_API_KEY
