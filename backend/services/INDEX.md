# LAWAPP Tier 1 Services - Complete Index

## Overview

This directory contains **3 zero-dependency microservices** that form the foundational layer of LAWAPP.

- **lawapp-rules-service** (port 8016): Deterministic legal rules lookup
- **lawapp-audit-service** (port 8020): Immutable audit logging
- **lawapp-redaction-service** (port 8019): PII detection and redaction

All three services:
- Connect to PostgreSQL database
- Have no dependencies on other microservices
- Include health/readiness probes
- Enforce user isolation and security
- Propagate trace IDs for observability
- Are production-ready with error handling

---

## File Structure

```
backend/services/
├── INDEX.md                                          (this file)
├── TIER1_QUICKSTART.md                              (usage guide)
├── __init__.py                                       (package marker)
│
├── lawapp-rules-service/
│   ├── main.py                                      (440 lines, FastAPI app)
│   ├── requirements.txt                             (dependencies)
│   ├── Dockerfile                                   (python:3.12-slim)
│   └── __init__.py
│
├── lawapp-audit-service/
│   ├── main.py                                      (400 lines, FastAPI app)
│   ├── requirements.txt                             (dependencies)
│   ├── Dockerfile                                   (python:3.12-slim)
│   └── __init__.py
│
└── lawapp-redaction-service/
    ├── main.py                                      (430 lines, FastAPI app)
    ├── requirements.txt                             (dependencies)
    ├── Dockerfile                                   (python:3.12-slim)
    └── __init__.py
```

---

## Quick Start

### 1. Start Services with Docker Compose

```bash
cd /sessions/ecstatic-charming-dirac/mnt/lawapp

# Start all dependencies + tier 1 services
docker compose up -d db redis
docker compose up -d lawapp-rules-service lawapp-audit-service lawapp-redaction-service

# Check they're running
docker compose ps

# Test health endpoints
curl http://localhost:8016/health
curl http://localhost:8020/health
curl http://localhost:8019/health
```

### 2. Run Integration Tests

```bash
# Run all tier 1 tests
pytest backend/tests/test_tier1_services_integration.py -v

# Run specific service tests
pytest backend/tests/test_tier1_services_integration.py::TestRulesService -v
pytest backend/tests/test_tier1_services_integration.py::TestAuditService -v
pytest backend/tests/test_tier1_services_integration.py::TestRedactionService -v
```

### 3. Kubernetes Deployment

```bash
# Create namespaces
kubectl create namespace lawapp-ai
kubectl create namespace lawapp-monitoring
kubectl create namespace lawapp-security

# Deploy services
kubectl apply -f infra/k8s/lawapp-rules-service-deployment.yaml
kubectl apply -f infra/k8s/lawapp-rules-service-service.yaml
kubectl apply -f infra/k8s/lawapp-audit-service-deployment.yaml
kubectl apply -f infra/k8s/lawapp-audit-service-service.yaml
kubectl apply -f infra/k8s/lawapp-redaction-service-deployment.yaml
kubectl apply -f infra/k8s/lawapp-redaction-service-service.yaml

# Check status
kubectl get pods -n lawapp-ai
kubectl get pods -n lawapp-monitoring
kubectl get pods -n lawapp-security
```

---

## Service Details

### lawapp-rules-service

**Purpose:** Query deterministic legal facts without LLM

**File:** `lawapp-rules-service/main.py` (440 lines)

**Endpoints:**
- `GET /health` → Health check
- `GET /ready` → Readiness probe (503 if DB/Redis down)
- `GET /api/rules/{domain}/{module}/{rule_key}` → Fetch rule by key
- `GET /api/rules/list?domain=...&module=...` → List all rules
- `GET /api/rules/validate/{domain}` → Coverage report

**Database:** PostgreSQL `rules` table
```sql
domain, claim_type, rule_key, value_numeric, value_text, unit,
authority_type, authority_ref, authority_url,
effective_from, effective_to, is_prospective, last_verified_at
```

**Cache:** Redis with 1-hour TTL
- Key format: `rule:{domain}:{module}:{rule_key}`
- Includes as_of_date for historical queries

**Environment:**
```
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
PORT=8016
LOG_LEVEL=INFO
CACHE_TTL_SECONDS=3600
```

**Tests:** 9 integration tests
- Health check ✓
- Readiness check ✓
- Rule lookup (existing, not found) ✓
- List rules ✓
- Validate rules ✓
- Cache functionality ✓

---

### lawapp-audit-service

**Purpose:** Immutable audit logging for compliance

**File:** `lawapp-audit-service/main.py` (400 lines)

**Endpoints:**
- `GET /health` → Health check
- `GET /ready` → Readiness probe (503 if DB down)
- `POST /api/audit/log` → Create audit entry (201)
- `GET /api/audit/trace/{trace_id}` → Retrieve full trace
- `GET /api/audit/user/{user_id}?limit=N` → Retrieve user's actions

**Database:** PostgreSQL `audit_logs` table
```sql
id, trace_id, user_id, tenant_id, action, resource_type, resource_id,
old_value, new_value, result, error_message, created_at
```

**Key Features:**
- Write-only (no deletes, immutable)
- User isolation: WHERE user_id = %s enforced in database
- Trace correlation: all steps for a trace_id linked
- Pagination: limit parameter (1-1000)

**Environment:**
```
DATABASE_URL=postgresql://...
PORT=8020
LOG_LEVEL=INFO
```

**Tests:** 10 integration tests
- Health check ✓
- Readiness check ✓
- Create audit entry ✓
- Retrieve trace ✓
- Retrieve user audit ✓
- User isolation (CRITICAL) ✓
- Pagination ✓

---

### lawapp-redaction-service

**Purpose:** Redact PII before external LLM calls

**File:** `lawapp-redaction-service/main.py` (430 lines)

**Endpoints:**
- `GET /health` → Health check
- `GET /ready` → Readiness probe (503 if DB down)
- `POST /api/redact` → Redact PII from text
- `POST /api/validate_redaction` → Verify redaction

**PII Entity Types:**
- EMAIL: `john@example.com`
- PHONE: `020 7946 0958`, `+44 20 7946 0958`
- SALARY: `£40,000`, `£123,456.78`
- NAME: `John Smith`, `Jane Doe` (CamelCase pairs)
- COMPANY: `Acme Ltd`, `Google Inc`, `Meta LLC`
- POSTCODE: `SW1A 1AA` (UK format)
- DATE: `01/01/2025`, `31-12-2024`

**Database:** PostgreSQL `redaction_audit` table
```sql
trace_id, original_hash, redacted_hash, redaction_rules_applied, created_at
```

**Key Features:**
- No external ML models (regex-based)
- Original text NEVER stored (only SHA256 hashes)
- Safe entity responses (return `[REDACTED]`)
- Validation endpoint confirms proper redaction

**Environment:**
```
DATABASE_URL=postgresql://...
PORT=8019
LOG_LEVEL=INFO
```

**Tests:** 11 integration tests
- Health check ✓
- Readiness check ✓
- Redact email ✓
- Redact phone ✓
- Redact salary ✓
- Redact multiple entities ✓
- No PII text unchanged ✓
- Validate correct redaction ✓
- Validate failed redaction ✓

---

## Docker Compose Integration

Services added to `docker-compose.yml`:

```yaml
lawapp-rules-service:
  build: ./backend/services/lawapp-rules-service
  ports: ["8016:8016"]
  depends_on: [db, redis]
  healthcheck: curl -f http://localhost:8016/health

lawapp-audit-service:
  build: ./backend/services/lawapp-audit-service
  ports: ["8020:8020"]
  depends_on: [db]
  healthcheck: curl -f http://localhost:8020/health

lawapp-redaction-service:
  build: ./backend/services/lawapp-redaction-service
  ports: ["8019:8019"]
  depends_on: [db]
  healthcheck: curl -f http://localhost:8019/health
```

All services:
- Use environment variables from `.env`
- Connect to `db` service (postgres)
- Connect to `redis` service (where applicable)
- Have healthchecks
- Restart unless stopped

---

## Kubernetes Manifests

### Rules Service
- **Deployment:** `infra/k8s/lawapp-rules-service-deployment.yaml`
  - Namespace: `lawapp-ai`
  - Replicas: 1
  - Resources: requests(100m/256Mi) limits(500m/512Mi)
  - Probes: liveness(10s) readiness(5s)

- **Service:** `infra/k8s/lawapp-rules-service-service.yaml`
  - Type: ClusterIP
  - Port: 8016

### Audit Service
- **Deployment:** `infra/k8s/lawapp-audit-service-deployment.yaml`
  - Namespace: `lawapp-monitoring`
  - Replicas: 1
  - Resources: requests(100m/256Mi) limits(500m/512Mi)
  - Probes: liveness(10s) readiness(5s)

- **Service:** `infra/k8s/lawapp-audit-service-service.yaml`
  - Type: ClusterIP
  - Port: 8020

### Redaction Service
- **Deployment:** `infra/k8s/lawapp-redaction-service-deployment.yaml`
  - Namespace: `lawapp-security`
  - Replicas: 1
  - Resources: requests(100m/256Mi) limits(500m/512Mi)
  - Probes: liveness(10s) readiness(5s)

- **Service:** `infra/k8s/lawapp-redaction-service-service.yaml`
  - Type: ClusterIP
  - Port: 8019

All manifests:
- Use canonical namespaces per service_contracts.yaml
- Define resource requests and limits
- Configure health/readiness probes
- Inject DATABASE_URL via secretKeyRef (no hardcoded secrets)
- Use imagePullPolicy: IfNotPresent

---

## Testing

**Integration Tests:** `backend/tests/test_tier1_services_integration.py` (500 lines)

**Test Categories:**

1. **Rules Service Tests (9)**
   - Health/readiness checks
   - Rule lookup (existing, not found)
   - List rules
   - Validate rules
   - Cache functionality

2. **Audit Service Tests (10)**
   - Health/readiness checks
   - Create audit log entry
   - Retrieve trace
   - Retrieve user audit
   - **User isolation verification (CRITICAL)**
   - Pagination

3. **Redaction Service Tests (11)**
   - Health/readiness checks
   - PII detection (email, phone, salary)
   - Multiple entity redaction
   - No PII text unchanged
   - Validation (pass/fail)

**Run Tests:**
```bash
# All tests
pytest backend/tests/test_tier1_services_integration.py -v

# Specific test class
pytest backend/tests/test_tier1_services_integration.py::TestRulesService -v

# Specific test
pytest backend/tests/test_tier1_services_integration.py::TestAuditService::test_user_isolation -v
```

---

## Documentation

- **TIER1_QUICKSTART.md** - Quick reference guide with examples
- **INDEX.md** - This file, complete service overview
- **reports/backend-services-tier1-proof.md** - Full acceptance proof (1000+ lines)

---

## Key Design Principles

✓ **No LLM:** Rules service is pure database lookup
✓ **Real DB Calls:** All services use PostgreSQL, not mocks
✓ **User Isolation:** Audit service enforces per-user access
✓ **PII Protection:** Redaction service never logs plaintext
✓ **Fail Closed:** Services return 503 if dependencies unavailable
✓ **Parameterized Queries:** All use %s placeholders (no SQL injection)
✓ **Trace Correlation:** Every action traceable end-to-end
✓ **Production Ready:** Logging, health checks, resource limits

---

## Status

- **Build Date:** 2026-06-08
- **Status:** Production Ready
- **All Tests:** Passing
- **Docker:** Ready to build and run
- **Kubernetes:** Manifests ready to deploy
- **Next Phase:** Tier 2 business services

---

## Contact & Support

For detailed implementation questions, see:
- Service docstrings in each main.py
- Inline comments for complex logic
- Pydantic schemas for request/response validation
- Test file for usage examples

For architecture questions, see:
- `infra/contracts/service_contracts.yaml`
- `infra/contracts/api_contracts.json`
- `docs/MASTER_LEGAL_BRAIN_ALGORITHM.md`

---

**Last Updated:** 2026-06-08
**Maintained By:** Principal Architect
**Status:** ✓ Production Ready
