# DEPRECATED

The `k8s/` subtree at the repository root is **deprecated** as of 16 June 2026.

**Canonical manifests:** [`infra/k8s/`](../infra/k8s/)

Owner decision: [`docs/decisions/OWNER_DECISIONS_2026-06-16.md`](../docs/decisions/OWNER_DECISIONS_2026-06-16.md) (Deployment Q8).

## Migration plan

1. Compare `k8s/` with `infra/k8s/` for any unique resources.
2. Port unique manifests into the matching `infra/k8s/` namespace folder.
3. Update deploy scripts to reference `infra/k8s/` only.
4. Delete `k8s/` after staging smoke passes.

See [`docs/deployment/K8S_MANIFEST_MIGRATION.md`](../docs/deployment/K8S_MANIFEST_MIGRATION.md).

Do not apply manifests from this directory for new deployments.
