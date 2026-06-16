# LAWAPP  -  Full Continuation Evidence Report
**Generated:** 2026-06-04  
**Branch:** main  
**Commit:** 080af6981d03fd412fe43dfec6f67febe4ff758c  
**Working tree:** DIRTY (uncommitted changes  -  see section 1)

---

## FINAL VERDICT

| Level | Status | Reason |
|---|---|---|
| LOCAL DEMO READY | FAIL | rules=0, payment_events table missing, legislation=0, acas=0 |
| STAGING READY | FAIL  -  EXTERNAL BLOCKER | Kubernetes DNS not resolving from workstation; CI test/build failing |
| PRODUCTION READY | FAIL | All staging/local gaps still open |

---

## 1. Repo State

**Branch:** main  
**Commit:** 080af6981d03fd412fe43dfec6f67febe4ff758c

**Uncommitted changes:**
```
M  .claude/settings.local.json
M  .github/workflows/lawapp-ci.yml    ← CI fix uncommitted
M  backend/core/retrieve.py
M  client/public/css/styles.css
M  client/public/pages/intake.html
M  client/public/pages/saved_case.html
M  docker-compose.yml
D  infra/k8s/iterlaw/*.yaml (all)     ← legacy quarantine in progress
```

---

## 2. Docker State (live)

```
lawapp-backend-1  healthy  :8000
lawapp-db-1       healthy  :5435
lawapp-redis-1    healthy  :6379
```

---

## 3. Backend Health

```json
{
  "status": "ok",
  "db": "connected",
  "auth_mode": "jwt",
  "payment_mode": "test_simulator",
  "ai_provider": { "provider": "stub", "active": false }
}
```

---

## 4. Database State (live)

| Table | Count | Status |
|---|---|---|
| rules | 0 | FAIL  -  seed migration not populating |
| legislation | 0 | FAIL  -  ingestion not run |
| acas_guidance | 0 | FAIL  -  ingestion not run |
| brain_traces | 0 | expected |
| payment_events | TABLE MISSING | CRITICAL FAIL  -  migration absent |

---

## 5. WASM Evidence

| Check | Result |
|---|---|
| Binary exists (`client/public/wasm/lawapp_wasm_bg.wasm`, 95KB) | PASS |
| JS fallback exists (`client/public/js/deadline.js`, 7.4KB) | PASS |
| Rust source exists (`client/wasm/src/lib.rs`) | PASS |
| No hardcoded legal caps in Rust (123543/751/118223) | PASS |
| No hardcoded legal caps in JS | PASS |
| `time_limit_months` is a parameter (not hardcoded) | PASS |
| Binary newer than Rust source (not stale) | PASS |
| CI installs wasm-pack + rebuilds if stale | PASS |
| Local rebuild (`bash scripts/rebuild-wasm.sh`) | BLOCKED  -  wasm-pack not on Windows PATH |

**WASM verdict: CI and code correct. Local rebuild blocked by Windows wasm-pack absence.**

---

## 6. CI/CD Evidence

```
SUCCESS  LawApp Deploy to Talos   main  workflow_dispatch  2026-06-04T06:40
SUCCESS  LawApp Deploy to Talos   main  push               2026-06-04T06:18
FAIL     lawapp  -  Build and push  main  push               2026-06-04T06:18
FAIL     LawApp Docker Proof      main  push               2026-06-04T06:18
FAIL     lawapp CI  -  Test/Build   main  push               2026-06-04T06:18
FAIL     lawapp-ci                main  push               2026-06-04T06:18
```

**Talos deploy: PASS.**  
**CI failure root cause:** "Project-specific migration runner not found"  -  the committed `lawapp-ci.yml` has a bug. The locally modified version fixes this but has not been pushed.

---

## 7. Kubernetes Evidence

```
kubectl config current-context: aks-iterlaw-we-prod
kubectl get ns: ERROR  -  no such host: aks-iterla-rg-iterlaw-we-pr-58900f-dimr8u4a.hcp.westeurope.azmk8s.io
```

Cluster DNS not resolving from this workstation.  
**`LawApp Deploy to Talos` CI job SUCCEEDED**  -  cluster was reachable from GitHub Actions.  
This is an **external blocker**  -  owner needs VPN/kubeconfig access to verify from local machine.  

Required namespaces (`lawapp-ai`, `lawapp-rag`, `lawapp-api`, `lawapp-monitoring`, `lawapp-security`) **cannot be verified locally**.

---

## 8. Payment / Stripe

| Check | Result |
|---|---|
| `stripe>=10.0` in pyproject.toml | PASS |
| `verify_webhook_signature()` in payment.py (line 96) | PASS |
| STRIPE_WEBHOOK_SECRET missing = EnvironmentError (line 116) | PASS |
| `payment_events` table exists | FAIL  -  table missing from DB schema |
| `payment_status` on `cases` table | PASS  -  main.py:569 reads it |

---

## 9. OCR / Upload

Frontend has upload file list (case_detail.html, `/cases/{id}/uploads`). No page promises OCR text extraction. Backend returns 501 for extract route. **OCR correctly disabled and not advertised.**

---

## 10. Legacy Naming

`infra/k8s/iterlaw/`  -  all files staged for deletion (uncommitted). Active CI/deploy uses `LawApp` naming. Kubernetes cluster name `aks-iterlaw-we-prod` is a cloud resource name (not a lawapp namespace)  -  requires owner to reprovision to rename.

---

## 11. Gate Scripts

| Script | Status |
|---|---|
| `scripts/gate-kubernetes.sh` | EXISTS |
| `scripts/gate-real-ai.sh` | EXISTS |
| `scripts/gate-stripe.sh` | EXISTS |
| `scripts/gate-wasm-no-hardcode.sh` | CREATED this session |
| `scripts/lawapp-full-local-bootstrap.sh` | CREATED this session |
| `scripts/gate-full-acceptance.sh` | NOT CREATED  -  session cost limit |
| `scripts/gate-db-fresh-rebuild.sh` | NOT CREATED |
| `scripts/gate-rag-grounding.sh` | NOT CREATED |
| `scripts/gate-security-baseline.sh` | NOT CREATED |
| `scripts/gate-cicd-k8s-proof.sh` | NOT CREATED |
| `scripts/gate-frontend-backend-wiring.sh` | NOT CREATED |
| `scripts/gate-payment-webhook.sh` | NOT CREATED |

---

## 12. Remaining Blockers

### Coding gaps (must fix)

| # | Gap | Evidence | Fix |
|---|---|---|---|
| 1 | `payment_events` table missing | `psql: ERROR relation "payment_events" does not exist` | Add migration: `payment_events(id, event_id, event_type, session_id, case_id, amount, currency, status, processed, received_at)` |
| 2 | `rules` = 0 after clean Docker start | `SELECT COUNT(*) FROM rules` = 0 | Seed migration must insert rules unconditionally |
| 3 | CI migration runner not found | `gh run view` log: exit 1 | Push uncommitted `lawapp-ci.yml` fix |
| 4 | 6 gate scripts missing | Gate scripts list above | Create in next session |

### Owner secret / config gaps

| Gap | Evidence |
|---|---|
| `ANTHROPIC_API_KEY` | Health shows `ai_provider.active: false` |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | Health shows `payment_mode: test_simulator` |
| Kubernetes VPN/kubeconfig | DNS not resolving |

### External licence gaps

| Gap | Evidence |
|---|---|
| FCL case law licence | `case_law_chunks = 0` |

### Production compliance gaps

| Gap | Evidence |
|---|---|
| DPIA / legal review | Not started |
| Penetration test | Not started |
| Production monitoring | K8s not accessible |
