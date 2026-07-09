# Owner Runbook — lawapp Controlled Beta

Version: WO009 Ship Package
Date: 2026-07-09
Branch: `cc/convergence` from `main-restored@526cbcc`

---

## 1. Start the Stack

```bash
cd F:\lawapp-restore
docker compose up -d
```

Wait for all 15 services to reach healthy:

```bash
docker compose ps
```

Expected: backend, control-plane, db, frontend, ollama, redis, outbox-worker, and 8 lawapp-* services all "Up (healthy)".

First-run only — pull inference model:

```bash
docker compose exec ollama ollama pull qwen2.5:3b-instruct-q6_K
```

Embedding model (`bge-large-en-v1.5`) is already imported from prior ingestion runs.

## 2. Access the App

| Surface | URL |
|---------|-----|
| Landing page | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Health check | http://localhost:8000/health |
| Control plane | http://localhost:3001 |

## 3. Verify Health

```bash
curl http://localhost:8000/health
```

Expect: `ai_provider.active: true`, all service checks green.

## 4. Run Tests

```bash
docker compose exec backend python -m pytest tests/ -q --tb=line
```

WO009 floor: see `reports/SHIP_READINESS.md` for current numbers. Expected: 1925+ passed, 0 failed, ~52 skipped.

## 5. Key User Journeys

### 5a. Assessment (free tier)

1. Go to http://localhost:3000
2. Click "Check Your Rights"
3. Fill intake form: claim type "Unfair Dismissal", dismissal date, employment start, weekly pay
4. Submit — assessment runs through the brain pipeline (~25s)
5. Result shows: strength indicator, citations with legislation URLs, deadline with authority reference
6. Deadline widget shows days remaining with urgency colour

### 5b. Deadline Calculator

1. From assessment result, click deadline link or go to Deadline Tracker
2. Enter dismissal date — live preview computes from server rules
3. ACAS early conciliation dates extend the deadline via stop-clock

### 5c. Document Generation (paid tier)

1. Complete an assessment
2. Click "Get Your Documents" — payment wall (Stripe test mode)
3. After payment: Particulars of Claim and Schedule of Loss available for download
4. Documents cite the same legislation as the assessment

## 6. Data Census

| Category | Count |
|----------|-------|
| Distinct acts | 27 |
| Legislation rows | 3066+ |
| Corpus chunks | 6038+ |
| Rules | ~128 |
| Case law | 0 (licence-gated, D4) |

Ingestion may still be running in background. Check:

```bash
docker compose exec db psql -U lawapp -d lawapp -c "SELECT count(*) FROM legislation; SELECT count(*) FROM corpus_chunks;"
```

## 7. Freshness Monitoring

Start the monitoring profile:

```bash
docker compose --profile monitoring up -d freshness-monitor
```

Runs weekly. Check last report:

```bash
docker compose logs freshness-monitor --tail 50
```

Monitors for stale sources (>30 days) and ERA 2025 commencement SI publication.

## 8. Security Controls

| Control | Status |
|---------|--------|
| pip-audit | Clean (0 vulnerabilities) |
| Secret scan | Clean (no real secrets in repo) |
| Security headers | CSP, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy, Permissions-Policy |
| Rate limiting | slowapi: 30/min on /assess, 10/min on /auth/register |
| XSS | 0 innerHTML assignments in client templates |
| CitationGuard | Active — no answer cites a source that doesn't exist |

## 9. ERA 2025 Provisional Rules

Two ERA 2025 rules (6-month qualifying period, 6-month time limit) are seeded with `is_prospective = true` and will NOT appear in assessments until a commencement SI is enacted.

When the commencement SI is published:
1. Freshness monitor will detect it (checks legislation.gov.uk)
2. Owner sets `is_prospective = false` and updates `effective_from` to the commencement date
3. Verify with: `docker compose exec backend python -m pytest tests/integration/test_retrieve_rules.py -v`

## 10. Deployment Notes

- Backend Python code is BAKED into the Docker image. To deploy code changes:
  1. Edit files on host
  2. `docker compose cp backend/api/main.py backend:/app/backend/api/main.py`
  3. `docker compose exec backend kill -HUP 1` (reloads uvicorn without container restart)
  4. Do NOT use `docker compose restart` — it wipes cp'd files

- Client HTML files ARE bind-mounted (`./client/public:/app/client/public:ro`) — edits take effect on browser refresh.

- For permanent changes: rebuild the image with `docker compose build backend`.

## 11. Owner-Gated Decisions

| Decision | Status | Reference |
|----------|--------|-----------|
| Price (£29.99 vs £99) | PENDING | `docs/handoff/LAWAPP_CURRENT_STATE.md` |
| Find Case Law licence (D4) | PENDING | Expected ~13 July 2026 |
| ERA 2025 commencement | MONITORING | Freshness job active |
| Production deployment | OWNER ONLY | No CI/CD push without owner |
| Stripe live keys | OWNER ONLY | Test mode only in beta |

## 12. Reports Index

| Report | Path |
|--------|------|
| Ship readiness | `reports/SHIP_READINESS.md` |
| Progress board | `reports/PROGRESS_BOARD.md` |
| Rules verification | `reports/RULES_VERIFICATION_SHEET.md` |
| Security sweep | `reports/security_sweep.md` |
| k6 latency | `reports/k6_smoke_latency_report.md` |
| Accessibility log | `reports/frontend_accessibility_log.md` |
| Freshness proof | `reports/freshness_proof.md` |
| Manifest reconciliation | `reports/a7_manifest_reconciliation.md` |

## 13. Support

- All legal answers are grounded in ingested legislation — never generated from training data
- CitationGuard verifies every citation before display
- Local Ollama inference only — no external LLM calls
- Brain trace ID appears in every response for audit
