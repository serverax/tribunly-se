# RAG / Algorithm QA

Date: 2026-06-14
Status: FAIL / PARTIAL

## Required Pipeline

Product handoff requires classification -> rules lookup -> RAG -> Graph RAG -> reasoning -> scoring -> governance -> assessment, with no solicitor/legal-advice posture and no unsupported legal claims.

## PASS Evidence

- Full workflow proof returns a governed unfair-dismissal assessment with a deadline field, citations, and Graph RAG context.
- Out-of-scope query is rejected in live workflow proof.
- `tests/test_employment_module_scope.py`: verifies 24 required employment modules are declared server-side, only production modules are exposed, and unverified modules fail closed.
- `tests/test_db_backed_legal_values.py`: verifies missing legal rule values fail closed.
- Database proof confirms DB rules exist for current production modules: `unfair_dismissal` and `unpaid_wages`.
- Migration `060_redundancy_wrongful_dismissal_rules.sql` adds verified statutory anchors for `redundancy` and `wrongful_dismissal`, bringing those modules to partial DB coverage without exposing them as supported production modules.
- Migration `061_working_time_holiday_nmw_flexible_rules.sql` adds verified statutory anchors for `working_time`, `holiday_pay`, `national_minimum_wage`, and `flexible_working`, also partial only.
- Migration `062_equality_whistleblowing_rules.sql` adds verified statutory anchors for `discrimination`, `pregnancy_maternity_discrimination`, `equal_pay`, and `whistleblowing`, also partial only.
- Migration `063_family_leave_rules.sql` adds verified statutory anchors for `maternity_rights`, `paternity_rights`, `parental_leave`, and `shared_parental_leave`, also partial only.
- Migration `064_remaining_employment_module_anchors.sql` adds verified statutory anchors for `constructive_dismissal`, `employment_contracts`, `fixed_term_workers`, `part_time_workers`, `agency_workers`, `health_and_safety`, `trade_union_rights`, and `tupe`, also partial only.
- Migrations `065_promote_redundancy_wrongful_workflows.sql` and `066_redundancy_rule_source_metadata.sql` promote `wrongful_dismissal` and `redundancy` with DB-backed deterministic workflow proof. Redundancy calculation values now include DB rules for the week-pay cap, counted-years limit, and age-band multipliers.
- Migration `067_promote_working_time_holiday_flexible_workflows.sql` promotes `working_time`, `holiday_pay`, and `flexible_working` to deterministic DB-backed diagnosis scope with live workflow proof.
- Database proof confirms all 24 employment modules now have at least one verified DB rule/source anchor.
- RAG/Graph RAG compose services are healthy locally.

## FAIL / UNPROVEN Evidence

- `bash scripts/proof/prove_database_integrity.sh`: FAIL because 17 of 24 employment modules are not production-ready. DB coverage now exists for all 24 modules, but only 7 are production diagnosis scope.
- Full RAG/Graph RAG evidence across every UK employment-law module is not present.
- Legal accuracy matrix cannot mark all scenarios PASS.
- Full provenance chain from legal source -> chunk/node/edge -> retrieval -> citation guard -> final answer is not proven for all modules.
- Full pytest and CI are not proven green.

## Verdict

PARTIAL only. Current production path is suitable for further controlled proof on `unfair_dismissal`, `unpaid_wages`, `wrongful_dismissal`, `redundancy`, `working_time`, `holiday_pay`, and `flexible_working`, but not go-live for the promised 24-module UK employment-law product.
