# Security QA Report

Date: 2026-06-14
Status: FAIL / NO-GO

## PASS Evidence

- `bash scripts/proof/prove_lawapp_full_workflows.sh`: PASS.
- Proved anonymous document generation blocked.
- Proved anonymous case creation blocked after patching `/cases`.
- Proved User B cannot access User A's saved case.
- Proved anonymous case read returns 401.
- Proved unpaid user cannot generate full documents.
- Proved invalid/unsigned payment webhook does not unlock documents.
- Proved admin/reporting page is protected without admin key.
- Proved test payment confirmation only works through authenticated test-mode payment session.
- `python -m pytest -q tests\test_case_save_readiness.py tests\security\test_auth_routes.py tests\test_payment_confirm_test_route.py tests\test_schema_readiness_proof.py tests\test_employment_module_scope.py tests\test_db_backed_legal_values.py`: 47 passed, 1 skipped.

## Fixed Findings

Severity: CRITICAL
Path: `backend/api/main.py`
Issue: `POST /cases` allowed anonymous case creation and stored an orphaned case.
Fix: `/cases` now requires authenticated user identity before opening DB work.
Proof: Live workflow script now logs `PASS: anonymous case creation blocked`; targeted auth tests pass.
Status: fixed.

Severity: HIGH
Path: `backend/api/payment_routes.py`
Issue: Go-live proof needed a safe way to prove paid-document flow without using fake production payment bypass.
Fix: Added authenticated `/api/payments/confirm-test`, restricted to `PAYMENT_MODE=test` and existing owned sessions.
Proof: Full workflow proof marks case paid via test confirmation, then generates paid documents.
Status: fixed for local test mode.

Severity: HIGH
Path: `backend/api/main.py`, `backend/core/*`
Issue: Broad unverified module claims and hardcoded legal fallback values could create unsafe legal outputs.
Fix: Registry-backed production scope, DB-backed legal values, and fail-closed missing-rule behavior.
Proof: Employment module and DB-backed legal value tests pass.
Status: fixed for current production scope.

## Remaining Security Blockers

- Production secrets remain in local/development compose-style config and must be rotated/moved into deployment secret storage before public launch.
- Full SQL injection, XSS, upload malware, brute-force/rate-limit, logging/PII leakage, and third-party LLM payload audits are not fully proven.
- Full CI/K8s production auth and network-policy evidence is missing.
- 17 of 24 employment modules are not production-ready; legal-security posture cannot pass for unsupported modules. All 17 non-production modules now have partial verified DB coverage but remain blocked from production exposure: `agency_workers`, `constructive_dismissal`, `discrimination`, `employment_contracts`, `equal_pay`, `fixed_term_workers`, `health_and_safety`, `maternity_rights`, `national_minimum_wage`, `parental_leave`, `part_time_workers`, `paternity_rights`, `pregnancy_maternity_discrimination`, `shared_parental_leave`, `trade_union_rights`, `tupe`, and `whistleblowing`.

## Verdict

REJECT for go-live. Core workflow gates are now much stronger, but production security is not fully proven.
