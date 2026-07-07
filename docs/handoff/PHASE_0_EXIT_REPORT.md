# Phase 0 Exit Report

Generated: 2026-07-07

## Task 0 Evidence

Branch and HEAD:

```text
git branch --show-current
codex/phase-0

git log --oneline -3
8432368 fix(beta): package domains in backend image
3511b67 fix: repair beta diagnosis and JWT readiness gates
97aeae4 docs: verify LawApp technologies and workflows
```

Handoff summaries:

- `docs/handoff/HANDOFF.md`: Snapshot recorded a near-beta release line with RAG/ingestion verification complete, Docker health evidence, and beta promotion pending owner decision.
- `docs/handoff/RELEASE_STATE.md`: Historical release context recorded RAG 1024 repair and required verification re-run before beta promotion.
- `docs/handoff/KNOWN_ISSUES.md`: Open issues were AKS DNS/remote visibility, stale handover docs, untracked workspace noise, and unknown full test state pending verification.
- `docs/handoff/NEXT_TASKS.md`: Immediate priority was RAG 1024 verification, ADR-000 checks, forbidden path checks, and ingestion/RAG metrics.
- `docs/handoff/PROOF_INDEX.md`: Indexed beta gate proof, Docker domain packaging, targeted pytest, RAG 1024 proof, and historical path checks.

Survival table:

| Check | Evidence | Result |
| --- | --- | --- |
| PII/model boundary on RAG/embed path | `backend/services/lawapp-rag-service/ollama_embed.py:24`, `backend/services/lawapp-rag-service/main.py:261`, `backend/core/deidentify.py:67`, `backend/core/agentic/litellm_adapter.py:57` | Present in code; runtime proof deferred to Phase 2 |
| Stripe webhook proof path | `backend/api/payment_routes.py:419`, `scripts/proof/prove_lawapp_full_workflows.sh:384`, `tests/security/test_payment_access.py:72` | Present |
| 13-module scope-cut fencing | `client/public/js/beta-scope.js:21`, `tests/test_ui_beta_scope.py:13`, `reports/track_b_scope_cut_response.json:1`, `reports/ui_scope_enforcement_cursor.txt:8` | Present at tip |
| 1024-dim embedding config | `backend/services/lawapp-rag-service/ollama_embed.py:13`, `scripts/reembed_corpus_1024.py:27`, `backend/core/retrieve.py:291`, `tests/test_rag_1024_retrieval_repair.py:14` | Present at tip |

Price evidence:

- `backend/api/payment_routes.py:85`: `"full_documents": 2999,  # £29.99`
- Owner reconfirmation remains pending because the reset plan records a discrepancy with a prior £99 owner decision. No price change was made.

New floor baseline:

- Commit: `8432368`
- Command: `docker compose -f docker-compose.yml run --rm -T -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=lawapp ingestion sh -c "cd /app && python -m pytest tests/ -q -p no:cacheprovider --ignore=tests/integration/test_semantic_retrieval.py"`
- Summary: `ERROR tests/test_knowledge_proposals.py`; `Interrupted: 1 error during collection`; `2 warnings, 1 error in 83.08s`
- Aggregate: `0 passed / 0 failed / 0 skipped / 1 collection error`

## Task 1

- Commit: `e25e0dc` (`docs: add phase reset plan`)
- Diff stat:

```text
7 files changed, 394 insertions(+)
```

## Task 2

- Authoritative state doc: `docs/handoff/LAWAPP_CURRENT_STATE.md`
- Commit: `7db5925` (`docs: record recovered tree current state`)

## Task 3

SUPERSEDED files bannered:

- `tasks/lawapphandsoff.md`
- `docs/07_PROJECT_HANDOVER.md`
- `docs/08_UNFAIR_DISMISSAL_SEED_SPEC.md`

Files searched but not bannered because they are authoritative sweep instructions, not stale instructions:

- `docs/handoff/phases/LAWAPP_RESET_AND_EXECUTION_PLAN.md`
- `docs/handoff/phases/PHASE_0_SCOPE_FREEZE.md`

## Task 4

Client/public grep evidence: the 13 partial modules appear only in `client/public/js/beta-scope.js` as `PARTIAL_HIDDEN`; no public HTML/page/fetch target exposes them.

| Module | Client/public reachability | Route/fence evidence |
| --- | --- | --- |
| `constructive_dismissal` | Not reachable from public beta surface | Hidden in `beta-scope.js`; `tests/test_ui_beta_scope.py` asserts it is absent from HTML |
| `discrimination` | Not reachable from public beta surface | Hidden in `beta-scope.js`; `reports/track_b_scope_cut_response.json` returns `not_covered` |
| `pregnancy_maternity_discrimination` | Not reachable from public beta surface | Hidden in `beta-scope.js`; no other `client/public` hits |
| `equal_pay` | Not reachable from public beta surface | Hidden in `beta-scope.js`; no other `client/public` hits |
| `whistleblowing` | Not reachable from public beta surface | Hidden in `beta-scope.js`; no other `client/public` hits |
| `health_and_safety` | Not reachable from public beta surface | Hidden in `beta-scope.js`; no other `client/public` hits |
| `trade_union_rights` | Not reachable from public beta surface | Hidden in `beta-scope.js`; no other `client/public` hits |
| `maternity_rights` | Not reachable from public beta surface | Hidden in `beta-scope.js`; no other `client/public` hits |
| `paternity_rights` | Not reachable from public beta surface | Hidden in `beta-scope.js`; no other `client/public` hits |
| `parental_leave` | Not reachable from public beta surface | Hidden in `beta-scope.js`; no other `client/public` hits |
| `shared_parental_leave` | Not reachable from public beta surface | Hidden in `beta-scope.js`; no other `client/public` hits |
| `national_minimum_wage` | Not reachable from public beta surface | Hidden in `beta-scope.js`; no other `client/public` hits |
| `tupe` | Not reachable from public beta surface | Hidden in `beta-scope.js`; no other `client/public` hits |

No reachable module was found on the `client/public/` beta surface.

## Task 5

Whole-branch diff stat against `main-restored` after Phase 0 changes:

```text
docs/07_PROJECT_HANDOVER.md                       |  2 +
docs/08_UNFAIR_DISMISSAL_SEED_SPEC.md             |  2 +
docs/handoff/LAWAPP_CURRENT_STATE.md              | 58 ++++++++++++++++
docs/handoff/PHASE_0_EXIT_REPORT.md               | 120 +++++++++++++++++++++
docs/handoff/phases/LAWAPP_RESET_AND_EXECUTION_PLAN.md | 79 ++++++++++++++++++++++
docs/handoff/phases/PHASE_0_SCOPE_FREEZE.md       | 47 +++++++++++++
docs/handoff/phases/PHASE_1_FLOOR_TRIAGE.md       | 54 +++++++++++++++
docs/handoff/phases/PHASE_2_OWNER_SECURITY_GATES.md | 53 +++++++++++++++
docs/handoff/phases/PHASE_3_PAID_MOMENT_PROOF.md  | 57 ++++++++++++++++
docs/handoff/phases/PHASE_4_SURFACE_PROOF.md      | 55 +++++++++++++++
docs/handoff/phases/PHASE_5_BETA_SHIP.md          | 49 ++++++++++++++
tasks/lawapphandsoff.md                           |  2 +
12 files changed, 579 insertions(+)
```

Only documentation, handoff, and verification-report artifacts were touched.

## Hard Stop

Phase 0 stops here. PHASE_1 was not opened by Codex during Phase 0 execution.
