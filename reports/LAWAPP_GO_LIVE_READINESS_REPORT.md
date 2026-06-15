# LAWAPP GO-LIVE READINESS REPORT

Date: 2026-06-14
Root: `F:\lawapp`
Branch: `release/lawapp-clean-snapshot`
Verdict: NOT READY / NO-GO

## Executive Summary

LawApp is closer to a real controlled-beta path than at the start of QA: local Docker services are healthy, schema readiness passes, auth/payment/document workflow proof passes, and the app now fails closed for unverified employment modules and missing DB-backed legal rules.

Go-live is still blocked. The user's requirement is 24 UK employment-law modules with all UK employment law inside server databases. The DB catalogue now contains exactly 24 modules and all 24 now have verified DB rule/source coverage, but only `unfair_dismissal`, `unpaid_wages`, `wrongful_dismissal`, `redundancy`, `working_time`, `holiday_pay`, and `flexible_working` are production diagnosis scope. The remaining 17 are partial, hidden from production support, and still fail the final database gate.

## PASS Evidence

- Product handoff understood: LawApp is a UK employment-law self-help assistant, not a solicitor or legal-advice product; workflow is landing page -> assessment -> governed rules/RAG/Graph RAG -> dashboard/documents/payment/handoff.
- `docker compose ps` on 2026-06-14: backend, DB, Redis, rules, RAG, Graph RAG, redaction, audit, admin, case, notification, and outbox worker are running and healthy locally.
- `Invoke-WebRequest http://127.0.0.1:8000/health`: PASS, `db=connected`, `auth_mode=jwt`, `payment_mode=test`.
- `python -m pytest -q tests\test_case_save_readiness.py tests\security\test_auth_routes.py tests\test_payment_confirm_test_route.py tests\test_schema_readiness_proof.py tests\test_employment_module_scope.py tests\test_db_backed_legal_values.py`: 47 passed, 1 skipped.
- `python -m py_compile backend\api\main.py backend\api\payment_routes.py scripts\proof\apply_migrations.py scripts\proof\prove_schema_readiness.py`: PASS.
- `bash -n scripts/proof/prove_lawapp_full_workflows.sh && bash -n scripts/proof/prove_database_integrity.sh && bash -n db/init-migrations.sh && bash -n scripts/docker-init-db.sh`: PASS.
- `bash scripts/proof/prove_lawapp_full_workflows.sh`: PASS. Proves landing, health, governed unfair-dismissal assessment, DB-grounded wrongful-dismissal diagnosis, DB-grounded redundancy diagnosis, DB-grounded working-time diagnosis, DB-grounded holiday-pay diagnosis, DB-grounded flexible-working diagnosis, out-of-scope rejection, anonymous document block, anonymous case-creation block, registration/login, save case, dashboard reload, User B denied User A case, anonymous case read denied, unpaid document block, payment session, invalid webhook rejection, admin protection, test payment confirmation, paid particulars and schedule of loss, and legal boundary notice in downloaded documents.
- `python scripts\proof\prove_schema_readiness.py`: PASS against the local Docker DB. Required workflow tables/columns and 24 `employment_modules` rows are present.
- `python scripts\proof\apply_migrations.py`: PASS against local Docker DB and configured external DB; migrations `064_remaining_employment_module_anchors.sql`, `065_promote_redundancy_wrongful_workflows.sql`, `066_redundancy_rule_source_metadata.sql`, and `067_promote_working_time_holiday_flexible_workflows.sql` applied successfully to both.
- Local DB snapshot: 24 covered employment modules, 7 production modules, 17 non-production modules, 125 `rules` rows, and 104 `legislation` rows.

## FAIL Evidence

- `bash scripts/proof/prove_database_integrity.sh`: FAIL at the go-live employment-module gate.
- Exact DB blocker: 24-module catalogue exists, all modules require DB backing, and all 24 have verified DB rule/source coverage, but 17 modules are not production-ready. Seven are production diagnosis scope (`unfair_dismissal`, `unpaid_wages`, `wrongful_dismissal`, `redundancy`, `working_time`, `holiday_pay`, `flexible_working`); 17 are partial and remain hidden from supported production scope. Modules still not production-ready:
  `agency_workers`, `constructive_dismissal`, `discrimination`, `employment_contracts`, `equal_pay`, `fixed_term_workers`, `health_and_safety`, `maternity_rights`, `national_minimum_wage`, `parental_leave`, `part_time_workers`, `paternity_rights`, `pregnancy_maternity_discrimination`, `shared_parental_leave`, `trade_union_rights`, `tupe`, `whistleblowing`.
- `k6 run scripts\load\k6_100k_readiness.js`: FAIL. 50-VU smoke crossed thresholds: p95 `1.05s` against a `<1000ms` threshold and `http_req_failed=64.45%`. Some failures are expected negative-control 4xx responses, but the script still proves the current load gate is not green. 100k users in five minutes is not proven.
- Full pytest suite has not been proven green in this QA pass.
- Full legal accuracy across all 24 modules is not proven.
- Production secret rotation and deployment secret-store proof are not complete.
- K8s/runtime, CI, observability, backups/restore, and production CDN/pooler/headroom are not proven.

## Fixes Applied During QA

- Added server-side 24-module employment catalogue and DB migration.
- Added verified initial DB rule/source coverage for `redundancy` and `wrongful_dismissal`; both remain `partial`, not production.
- Added verified initial DB rule/source coverage for `working_time`, `holiday_pay`, `national_minimum_wage`, and `flexible_working`; all remain `partial`, not production.
- Added verified initial DB rule/source coverage for `discrimination`, `pregnancy_maternity_discrimination`, `equal_pay`, and `whistleblowing`; all remain `partial`, not production.
- Added verified initial DB rule/source coverage for `maternity_rights`, `paternity_rights`, `parental_leave`, and `shared_parental_leave`; all remain `partial`, not production.
- Added verified initial DB rule/source coverage for `constructive_dismissal`, `employment_contracts`, `fixed_term_workers`, `part_time_workers`, `agency_workers`, `health_and_safety`, `trade_union_rights`, and `tupe`; all remain `partial`, not production.
- Promoted `wrongful_dismissal` and `redundancy` to production scope with deterministic DB-backed assessments and live workflow proof. Added redundancy-specific week-pay cap, age-band multipliers, and counted-years limit as DB rules.
- Promoted `working_time`, `holiday_pay`, and `flexible_working` to production diagnosis scope with deterministic DB-backed assessments and live workflow proof.
- Added DB readiness migration `059_workflow_schema_compat.sql` and migration runner `scripts/proof/apply_migrations.py`.
- Tightened `/cases` so anonymous case creation now returns 401/403.
- Added `/api/payments/confirm-test`, guarded by auth, ownership, payment session, and `PAYMENT_MODE=test`.
- Removed broad fake module claims and production legal fallback defaults.
- Made missing DB legal rules and unsupported modules fail closed.
- Made DB bootstrap/migration scripts fail hard on migration errors.
- Added strict workflow, schema, DB, payment, module-scope, and legal-rule proof tests/scripts.

## Final Status

NOT READY - LAWAPP HARD BLOCKERS REMAIN.

Primary blocker: complete and prove all 24 UK employment-law modules with DB-backed rules, cited legal corpus, workflows, RAG/Graph RAG coverage, legal-accuracy tests, and document/payment/security proof where applicable.
