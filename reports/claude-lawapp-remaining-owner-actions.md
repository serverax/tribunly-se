# lawapp Remaining Owner Actions

**Date:** 2026-06-04  
**Classification:** LOCAL DEMO COMPLETE WITH OWNER-ACTION BLOCKERS

These are the ONLY remaining items that require owner action. All other items have been implemented.

---

## Owner actions (cannot be done by Claude)

| # | Item | Severity | Command/URL |
|---|---|---|---|
| 1 | ~~Set real `ANTHROPIC_API_KEY`~~ SUPERSEDED (2026-06-10): inference is local-Ollama-only; no external LLM key is used. Ensure the in-cluster Ollama deployment is healthy instead. | — | `kubectl -n lawapp-ai get deploy ollama-inference` |
| 2 | Set real Stripe keys | HIGH | Get from dashboard.stripe.com → set STRIPE_SECRET_KEY, STRIPE_PUBLIC_KEY, STRIPE_WEBHOOK_SECRET in .env |
| 3 | Run legal content ingestion | HIGH | `docker compose run --rm ingestion python -m ingestion.legislation.ingest` and `python -m ingestion.acas.ingest` |
| 4 | Apply for FCL bulk licence | MEDIUM | https://caselaw.nationalarchives.gov.uk/computational_access |
| 5 | Deploy to Talos cluster | HIGH | From WSL: `bash scripts/deploy-talos.sh` (requires KUBECONFIG + all env vars) |
| 6 | Configure domain + cert-manager for ingress | MEDIUM | Apply `infra/k8s/lawapp-ingress.yaml` after DNS is ready |

---

## Proof that everything else is done

```
# Fresh Docker start
docker compose down -v && docker compose up -d --build

# DB seed
SELECT COUNT(*) FROM rules → 19 ✓ (automatic)

# All tests
python -m pytest → 435 passed, 0 failed ✓

# Smoke journey
bash scripts/smoke_local_journey.sh → 24 PASS / 0 FAIL ✓

# User isolation
Step 10: User B → HTTP 403 ✓

# Documents
POST /documents/generate → 9620 chars, boundary notice ✓

# Deadline
POST /api/deadline/calculate → source=rules ✓
```

---

## Quick start for demo

```bash
cd /mnt/f/lawapp

# Start
docker compose up -d --build

# Verify
curl http://localhost:8000/health

# Open browser
start http://localhost:8000
# OR on Linux: xdg-open http://localhost:8000

# Run full tests
python -m pytest -q

# Run smoke journey
bash scripts/smoke_local_journey.sh
```
