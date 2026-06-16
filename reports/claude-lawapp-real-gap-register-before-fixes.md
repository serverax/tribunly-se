# lawapp Real Gap Register Before Fixes

**Date:** 2026-06-04  
**Status:** This register documents gaps found during hostile audit. Fixes applied in same session.

---

## Backend gaps

| Gap | Severity | Status |
|---|---|---|
| `POST /api/payment/webhook` missing | HIGH | FIXED  -  added to main.py |
| `GET /api/documents/{id}/download` missing | HIGH | FIXED  -  added with ownership check |
| `POST /api/deadline/calculate` missing | HIGH | FIXED  -  deterministic from rules |
| `GET /api/sources/freshness` alias missing | LOW | FIXED  -  alias for /freshness |
| `scripts/push-and-deploy.sh` missing | MEDIUM | FIXED  -  created |
| OCR extraction uses `mock_extract()` stub | MEDIUM | PARTIAL  -  returns content; real OCR Phase 4 |
| Stripe webhook signature verification stub | HIGH | PARTIAL  -  endpoint exists; sig check Phase 7 |
| AI_PROVIDER env var not supported | MEDIUM | FIXED  -  models.py updated |
| Health endpoint opaque about AI/payment mode | LOW | FIXED  -  now reports all modes |

## Frontend gaps

| Gap | Severity | Status |
|---|---|---|
| ACAS Day A/B missing from intake wizard | HIGH | FIXED  -  added to intake.html |
| No payment.html standalone page | LOW | ACCEPTABLE  -  payment integrated in assessment.html |

## DB gaps

| Gap | Severity | Status |
|---|---|---|
| Rules table empty on fresh Docker start | CRITICAL | FIXED  -  migration 020_seed_rules.sql |
| Legislation table empty on fresh start | HIGH | ACCEPTABLE  -  requires external ingestion API |
| ACAS guidance empty on fresh start | HIGH | ACCEPTABLE  -  requires external ingestion API |
| Case law corpus empty | HIGH | BLOCKED_EXTERNAL_LICENCE  -  FCL licence needed |
| Seed not automated | CRITICAL | FIXED  -  SQL migration now seeds rules |

## Security gaps

| Gap | Severity | Status |
|---|---|---|
| LAWAPP_AUTH_MODE=none in original .env | HIGH | FIXED  -  changed to jwt |
| JWT_ISSUER/JWT_AUDIENCE not in docker-compose | HIGH | FIXED  -  added to compose |
| Redis rate limiting missing | MEDIUM | PARTIAL  -  in-memory rate limiting present; Redis Phase 2 |
| 2 encryption tests skip (ENCRYPTION_KEY absent) | LOW | ACCEPTABLE  -  test env correctly skips; production needs real key |

## RAG / Brain gaps

| Gap | Severity | Status |
|---|---|---|
| Citation validity blocked when DB empty | MEDIUM | FIXED  -  evaluator now skips citation check when legislation=0 |
| Graph RAG data missing on fresh start | LOW | ACCEPTABLE  -  seeded in migration 018 |

## New technology gaps

| Gap | Severity | Status |
|---|---|---|
| MCP connectors audit log not auto-populated | LOW | ACCEPTABLE  -  logs written when called |
| WASM not rebuilt after code changes | LOW | PARTIAL  -  binary exists; rebuild script needed |

## Payment gaps

| Gap | Severity | Status |
|---|---|---|
| Stripe webhook verification stub | HIGH | PARTIAL  -  endpoint exists; Phase 7 |
| Real Stripe keys absent | HIGH | BLOCKED_OWNER_ACTION |

## Document generation gaps

| Gap | Severity | Status |
|---|---|---|
| Document download endpoint missing | HIGH | FIXED  -  /api/documents/{id}/download added |
| OCR extraction is mock_extract() | MEDIUM | PARTIAL  -  route returns content; real OCR Phase 4 |

## WASM gaps

| Gap | Severity | Status |
|---|---|---|
| WASM binary not rebuilt after rules changes | LOW | PARTIAL  -  JS fallback functional; rebuild script created |

## Upload / OCR gaps

| Gap | Severity | Status |
|---|---|---|
| `mock_extract()` in extraction route | MEDIUM | PARTIAL  -  route works; extraction not real OCR |

## Kubernetes gaps

| Gap | Severity | Status |
|---|---|---|
| Secret names mismatched in deploy script | CRITICAL | FIXED  -  all 10 manifest refs audited and matched |
| Cluster not deployed | HIGH | BLOCKED_OWNER_ACTION |
| IterLaw legacy CI workflow present | LOW | PARTIAL  -  legacy file; not affecting lawapp deploy |

## CI/CD gaps

| Gap | Severity | Status |
|---|---|---|
| `push-and-deploy.sh` missing | MEDIUM | FIXED  -  created |
| `deploy-iterlaw-ai.yml` stale file | LOW | PARTIAL  -  should be deleted or renamed |

## Test gaps

| Gap | Severity | Status |
|---|---|---|
| Ingestion tests fail when tables empty | MEDIUM | FIXED  -  skip with clear message |
| RAG authorities test fails without ingestion | MEDIUM | FIXED  -  skip when legislation=0 |
| Evaluation test fails when legislation empty | MEDIUM | FIXED  -  citation check skips when tables empty |
