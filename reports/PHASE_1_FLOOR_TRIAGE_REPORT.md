# Phase 1 Floor Triage Report

Generated: 2026-07-07

## Scope

Branch: `codex/phase-1`

Base carried from Phase 0: `ae2b595` (`docs: sign phase 0 hard exit`)

Work order: unlock collection, establish the real floor, classify failures, and stop. No push, merge, deploy, secrets work, scope additions, or non-collection fixes were performed.

## Step 1 - Collection Error

Command:

```text
docker compose -f docker-compose.yml run --rm -T -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=lawapp ingestion sh -c "cd /app && python -m pytest tests/test_knowledge_proposals.py --collect-only -q"
```

Original traceback:

```text
ImportError while importing test module '/app/tests/test_knowledge_proposals.py'
tests/test_knowledge_proposals.py:12:
from backend.core.knowledge_proposer import propose_knowledge_gap, approve_proposal
E   ImportError: cannot import name 'propose_knowledge_gap' from 'backend.core.knowledge_proposer'
```

Diagnosis: missing export/function. `backend/core/brain.py` also imports `propose_knowledge_gap`, so this was not only a stale test import.

Minimal fix: added `propose_knowledge_gap()` to `backend/core/knowledge_proposer.py`. It only queues a row in `knowledge.ingestion_proposals`; it does not write rules, legislation, corpus rows, or legal output.

Verification after fix:

```text
tests/test_knowledge_proposals.py::TestIngestionWriteGuard::test_brain_path_does_not_import_ingestion_writes
tests/test_knowledge_proposals.py::TestIngestionWriteGuard::test_brain_module_has_no_direct_rules_insert
tests/test_knowledge_proposals.py::TestIngestionWriteGuard::test_pipeline_module_has_no_direct_rules_insert
tests/test_knowledge_proposals.py::TestIngestionWriteGuard::test_ingestion_write_functions_documented
tests/test_knowledge_proposals.py::TestKnowledgeProposals::test_propose_creates_row_only
tests/test_knowledge_proposals.py::TestKnowledgeProposals::test_approve_does_not_insert_rules
tests/test_knowledge_proposals.py::TestKnowledgeProposals::test_propose_invalid_proposer_raises

7 tests collected in 7.27s
```

Fix diff stat:

```text
backend/core/knowledge_proposer.py | 73 ++++++++++++++++++++++++++++++++++++++
1 file changed, 73 insertions(+)
```

## Step 2 - Real Floor

Command:

```text
docker compose -f docker-compose.yml run --rm -T -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=lawapp ingestion sh -c "cd /app && python -m pytest tests/ -q --tb=short -p no:cacheprovider --ignore=tests/integration/test_semantic_retrieval.py"
```

Baseline line:

```text
512 failed, 998 passed, 62 skipped, 7 warnings, 313 errors in 458.44s (0:07:38)
```

Combined baseline: `998 passed / 512 failed / 62 skipped / 313 errors`.

Full per-test failure/error lines: `reports/phase1_test_result_lines.txt`

Per-test classification table: `reports/phase1_triage_table.csv`

Counts:

| Classification | Count | Meaning |
| --- | ---: | --- |
| ENVIRONMENT | 720 | Dominant DB/bootstrap cascade. Fresh compose DB was reachable but schema/data bootstrap was absent or incomplete; signatures include missing `users`, `cases`, `rules`, `documents`, and `outbox_events`. |
| KNOWN-BENIGN | 3 | Legacy embedding/source-table expectations. Accepted-risk evidence: `reports/rag_1024_retrieval_repair.txt:111`, `reports/prod_embed_hardening_cursor.txt:45`, `docs/handoff/RELEASE_STATE.md:42`. |
| REAL DEFECT | 102 | Non-environment assertion/exception failures requiring owner assignment. Dominant signature is `NameError: name 'logger' is not defined` in `backend/core/brain.py`; another explicit defect is `approve_proposal` not publishing the expected outbox event. |

Lane counts:

| Lane | Count |
| --- | ---: |
| db/compose/test-env | 634 |
| backend/tests | 61 |
| payment | 59 |
| intake/diagnosis | 57 |
| security | 11 |
| retrieval/embedding | 3 |

## Step 3 - Priority Triage

Security/XSS/injection:

- `tests/test_xss_protection.py` did not fail in the full floor.
- Targeted proof: `python -m pytest tests/test_xss_protection.py -q` -> `2 passed in 8.70s`.
- The test checks `client/public/pages/assessment.html`, `client/public/pages/intake.html`, and `client/public/pages/saved_case.html` for `.innerHTML =` and `textContent` usage.
- Remaining security failures in the floor are DB/environment or schema readiness failures, not XSS hits.

Payment lane:

- Payment-related entries are mostly ENVIRONMENT because the compose DB lacks payment/case schema (`cases`, `payment_events`, or related tables).
- Examples: `tests/payment/test_payment.py::TestStripeWebhookVerification::test_payment_events_table_exists`, `tests/security/test_payment_access.py::TestCreateSessionEndpointSecurity::test_payment_status_endpoint_exists`, `tests/integration/test_phase4b_bundle.py::*`.
- Owning lane: payment plus db/compose bootstrap.

Intake/diagnosis lane:

- Real defect cluster: `backend/core/brain.py` references `logger` but the module defines no logger object. This causes repeated `NameError: name 'logger' is not defined`.
- Affected examples: `tests/brain/test_brain.py::*`, `tests/integration/test_brain_gatekeeper.py::*`, `tests/test_claim_checker.py::*`, `tests/test_mother_controller.py::*`.
- Owning lane: intake/diagnosis backend.

Retrieval/embedding lane:

- Three embedding failures are classified KNOWN-BENIGN legacy-dimension/source-table expectations.
- Current accepted risk: source tables remain `vector(384)`/legacy while `corpus_chunks` 1024 is authoritative for retrieval.

Collection-fix follow-on:

- `tests/test_knowledge_proposals.py::TestKnowledgeProposals::test_approve_does_not_insert_rules` now runs and fails because `approve_proposal()` does not call `backend.core.outbox.publish()` as expected.
- Classification: REAL DEFECT.
- Owning lane: backend/tests.

## Step 4 - 13-Module Fence Completion

`client/public/` grep found the 13 partial modules only in `client/public/js/beta-scope.js` under `PARTIAL_HIDDEN`. No public HTML/page/fetch route exposes them.

| Module | Client/public status |
| --- | --- |
| `constructive_dismissal` | Hidden only; not publicly reachable |
| `discrimination` | Hidden only; not publicly reachable |
| `pregnancy_maternity_discrimination` | Hidden only; not publicly reachable |
| `equal_pay` | Hidden only; not publicly reachable |
| `whistleblowing` | Hidden only; not publicly reachable |
| `health_and_safety` | Hidden only; not publicly reachable |
| `trade_union_rights` | Hidden only; not publicly reachable |
| `maternity_rights` | Hidden only; not publicly reachable |
| `paternity_rights` | Hidden only; not publicly reachable |
| `parental_leave` | Hidden only; not publicly reachable |
| `shared_parental_leave` | Hidden only; not publicly reachable |
| `national_minimum_wage` | Hidden only; not publicly reachable |
| `tupe` | Hidden only; not publicly reachable |

## Recommendation

NO-GO on real defects only.

Reason: XSS is not present in the new floor, but the real-defect set is non-zero. The first owner assignments should be:

1. Intake/diagnosis backend: define or wire `logger` in `backend/core/brain.py`, then rerun the affected brain/diagnosis tests.
2. Backend proposal/outbox lane: decide whether `approve_proposal()` must publish `ingestion_proposal_approved`, then fix or update the test contract.
3. DB/compose lane: run or repair schema/bootstrap before treating the 720 ENVIRONMENT entries as product defects.

No fixes beyond the collection unlock were applied.
