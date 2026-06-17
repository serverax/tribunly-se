
# Deployment state (snapshot)

## Namespaces (fixed list)

- lawapp-api, lawapp-rag, lawapp-ai, lawapp-security, lawapp-monitoring: status UNKNOWN - requires verification (no live cluster access).

## Services running

- Local Docker Compose: verified healthy for core LawApp services (see HANDOFF.md).

## Secrets configured

- Not inspected; names only policy applies. Status UNKNOWN - requires verification.

## Ingress

- UNKNOWN - requires verification (cluster unreachable).

## Pods status

- UNKNOWN - requires verification (cluster unreachable).

## Health checks

- Local Docker health: passing for listed LawApp containers.
- Remote API/DB/RAG/worker: UNKNOWN - requires verification.

## Failing deployments

- None observed locally.
- Remote CrashLoopBackOff: UNKNOWN - requires verification.
