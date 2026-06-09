# LAWAPP Tier 1 Services - Quick Start Guide

## Three Zero-Dependency Services

These services have no dependencies on other microservices. They only depend on PostgreSQL and Redis.

---

## Service 1: lawapp-rules-service (port 8016)

### Purpose
Query deterministic legal facts (deadlines, caps, thresholds, qualifying periods, remedies).

### Key Endpoints

```bash
# Health check
curl http://localhost:8016/health
# {"status": "ok", "timestamp": "..."}

# Readiness check (503 if DB/Redis down)
curl http://localhost:8016/ready
# {"status": "ready", "database_connected": true, "redis_connected": true}

# Get a specific rule
curl http://localhost:8016/api/rules/uk_employment/unfair_dismissal/unfair_dismissal.time_limit_months
# {"rule_key": "...", "value_numeric": 3, "unit": "months", "authority_ref": "ERA 1996 s.111(2)", ...}

# List all rules for a domain
curl http://localhost:8016/api/rules/list?domain=uk_employment
# {"domain": "uk_employment", "rules": [...], "total_count": 42}

# Validate rules are loaded for a domain
curl http://localhost:8016/api/rules/validate/uk_employment
# {"domain": "uk_employment", "modules": {"unfair_dismissal": 12, ...}, "total_rules": 42}
```

### Features
- **Caching:** Redis with 1-hour TTL
- **No LLM:** Pure database lookup
- **Trace Propagation:** X-Trace-ID header support
- **As-of-date Queries:** Get rules effective on specific dates

### Database
Table: `rules`
```
domain, claim_type, rule_key, value_numeric, value_text, unit,
authority_type, authority_ref, authority_url,
effective_from, effective_to, is_prospective, last_verified_at
```

---

## Service 2: lawapp-audit-service (port 8020)

### Purpose
Immutable audit logging for compliance, debugging, and governance.

### Key Endpoints

```bash
# Health check
curl http://localhost:8020/health
# {"status": "ok", "timestamp": "..."}

# Readiness check (503 if DB down)
curl http://localhost:8020/ready
# {"status": "ready", "database_connected": true}

# Create audit log entry
curl -X POST http://localhost:8020/api/audit/log \
  -H "Content-Type: application/json" \
  -d '{
    "trace_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "user-123",
    "tenant_id": "tenant-456",
    "action": "case_created",
    "resource_type": "case",
    "resource_id": "case-789",
    "result": "success"
  }'
# {"id": "...", "trace_id": "...", "created_at": "..."}

# Retrieve full trace
curl http://localhost:8020/api/audit/trace/550e8400-e29b-41d4-a716-446655440000
# {"trace_id": "...", "steps": [...], "total_steps": 5}

# Retrieve user's recent actions (user isolation)
curl http://localhost:8020/api/audit/user/user-123?limit=100
# {"user_id": "user-123", "recent_actions": [...], "total_count": 42}
```

### Features
- **Write-Only:** No delete endpoints (immutable)
- **User Isolation:** Each user sees only their actions
- **Trace Correlation:** All steps for a trace_id linked together
- **Pagination:** limit parameter (1-1000)

### Database
Table: `audit_logs`
```
id, trace_id, user_id, tenant_id, action, resource_type, resource_id,
old_value, new_value, result, error_message, created_at
```

### Critical Security Note
User A **cannot** read User B's audit logs. This is enforced via WHERE user_id = %s in the database query.

---

## Service 3: lawapp-redaction-service (port 8019)

### Purpose
Redact PII (personally identifiable information) before sending text to third-party LLMs.

### Key Endpoints

```bash
# Health check
curl http://localhost:8019/health
# {"status": "ok", "timestamp": "..."}

# Readiness check (503 if DB down)
curl http://localhost:8019/ready
# {"status": "ready", "database_connected": true}

# Redact PII from text
curl -X POST http://localhost:8019/api/redact \
  -H "Content-Type: application/json" \
  -d '{"text": "John Smith (john@example.com, 020 7946 0958) was paid £40,000"}'
# {
#   "redacted_text": "[NAME] ([EMAIL], [PHONE]) was paid [SALARY]",
#   "entities_found": 4,
#   "entities": [...],
#   "redaction_rule_hash": "..."
# }

# Validate a redaction is correct
curl -X POST http://localhost:8019/api/validate_redaction \
  -H "Content-Type: application/json" \
  -d '{
    "original": "Contact john@example.com",
    "redacted": "Contact [EMAIL]"
  }'
# {"valid": true, "reason": "All 1 PII entities properly redacted"}
```

### PII Entity Types Detected
- `EMAIL`: john.smith@example.com
- `PHONE`: 020 7946 0958, +44 20 7946 0958
- `SALARY`: £40,000, £123,456.78
- `NAME`: John Smith, Jane Doe (CamelCase pairs)
- `COMPANY`: Acme Ltd, Google Inc, Meta LLC
- `POSTCODE`: SW1A 1AA (UK format)
- `DATE`: 01/01/2025, 31-12-2024

### Features
- **No Plaintext Logging:** SHA256 hashes only in audit trail
- **No External ML:** Purely regex-based pattern matching
- **Validation Endpoint:** Confirms PII was properly redacted
- **Audit Trail:** Records what was redacted (rules + hashes, not values)

### Database
Table: `redaction_audit`
```
trace_id, original_hash, redacted_hash, redaction_rules_applied, created_at
```

**Important:** Original text is NEVER stored. Only hashes are kept for audit.

---

## Docker Compose Usage

Start all three services:
```bash
docker compose up -d lawapp-rules-service lawapp-audit-service lawapp-redaction-service
```

Check service health:
```bash
docker compose ps
curl http://localhost:8016/health
curl http://localhost:8020/health
curl http://localhost:8019/health
```

Stop services:
```bash
docker compose down
```

---

## Kubernetes Deployment

### Create Namespaces
```bash
kubectl create namespace lawapp-ai
kubectl create namespace lawapp-monitoring
kubectl create namespace lawapp-security
```

### Deploy Services
```bash
# Rules Service
kubectl apply -f infra/k8s/lawapp-rules-service-deployment.yaml
kubectl apply -f infra/k8s/lawapp-rules-service-service.yaml

# Audit Service
kubectl apply -f infra/k8s/lawapp-audit-service-deployment.yaml
kubectl apply -f infra/k8s/lawapp-audit-service-service.yaml

# Redaction Service
kubectl apply -f infra/k8s/lawapp-redaction-service-deployment.yaml
kubectl apply -f infra/k8s/lawapp-redaction-service-service.yaml
```

### Check Deployment Status
```bash
kubectl get pods -n lawapp-ai
kubectl get pods -n lawapp-monitoring
kubectl get pods -n lawapp-security

kubectl get svc -n lawapp-ai
kubectl get svc -n lawapp-monitoring
kubectl get svc -n lawapp-security

# Check logs
kubectl logs -n lawapp-ai deployment/lawapp-rules-service
```

---

## Testing

Run integration tests:
```bash
pytest backend/tests/test_tier1_services_integration.py -v
```

Test categories:
- Health/readiness checks
- Endpoint contract compliance
- Database connectivity
- User isolation verification
- PII redaction accuracy
- Caching functionality
- Error handling
- Security boundaries

---

## Environment Variables

### Rules Service
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `PORT`: Service port (default 8016)
- `LOG_LEVEL`: Logging level (default INFO)
- `CACHE_TTL_SECONDS`: Cache expiry in seconds (default 3600)

### Audit Service
- `DATABASE_URL`: PostgreSQL connection string
- `PORT`: Service port (default 8020)
- `LOG_LEVEL`: Logging level (default INFO)

### Redaction Service
- `DATABASE_URL`: PostgreSQL connection string
- `PORT`: Service port (default 8019)
- `LOG_LEVEL`: Logging level (default INFO)

---

## Trace ID Propagation

All services support trace ID propagation via the `X-Trace-ID` header.

Example:
```bash
curl http://localhost:8016/api/rules/... \
  -H "X-Trace-ID: my-request-550e8400-e29b-41d4-a716-446655440000"
```

The trace ID is:
1. Extracted from the request header
2. Logged on all operations
3. Included in database writes (for full audit trail)
4. Available in response metadata

---

## Key Design Principles

✓ **No LLM:** Rules service is pure database lookup
✓ **Real DB Calls:** All services use PostgreSQL (not mocks)
✓ **User Isolation:** Audit service enforces WHERE user_id filters
✓ **PII Protection:** Redaction service never logs plaintext
✓ **Fail Closed:** Services return 503 if dependencies unavailable
✓ **Parameterized Queries:** All use %s placeholders (no SQL injection)
✓ **Trace Correlation:** Every action traceable end-to-end
✓ **Production Ready:** Logging, health checks, resource limits

---

## Next Steps

1. **Start the services** via Docker Compose or Kubernetes
2. **Run the tests** to verify functionality
3. **Call the endpoints** from your application (gateway-api will route requests)
4. **Monitor health** via /health and /ready endpoints
5. **Review logs** for trace IDs and errors

---

## Support

For detailed architecture and implementation, see:
- `infra/contracts/service_contracts.yaml` - Service definitions
- `infra/contracts/api_contracts.json` - Endpoint specifications
- `reports/backend-services-tier1-proof.md` - Complete proof document

For code documentation, see:
- Service docstrings in each main.py file
- Inline comments for complex logic
- Pydantic schemas for request/response validation

---

**Last Updated:** 2026-06-08
**Status:** Production Ready
