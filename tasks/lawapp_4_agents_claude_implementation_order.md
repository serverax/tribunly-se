# lawapp - Claude Code Implementation Order for 4-Agent Architecture

**Target path in repo:** `F:\lawapp\tasks\lawapp_4_agents_claude_implementation_order.md`  
**Purpose:** This is the exact implementation order for Claude Code. It explains how to add the 4-agent architecture to lawapp without breaking the existing corpus/RAG/rules/honesty design.

---

## 0. Stop and read before coding

Before changing any file, read:

```text
F:\lawapp\tasks\lawapp_4_agents_restricted_acceptance_criteria.md
F:\lawapp\tasks\lawapp_4_agents_system_directives_and_protocols.md
F:\lawapp\tasks\lawapp_4_agents_litellm_and_mother_algorithm_design.md
```

Then inspect the existing lawapp files:

```bash
cd /mnt/f/lawapp 2>/dev/null || cd "F:/lawapp"

find backend -maxdepth 4 -type f | sort
find client -maxdepth 4 -type f | sort
find db/migrations -maxdepth 1 -type f | sort
find tests -maxdepth 2 -type f | sort

grep -R "class .*BaseModel\|pydantic\|brain\|retrieve\|hybrid\|rules\|deadline\|document\|outbox\|trace" -n backend tests | sed -n '1,240p'
```

Do not duplicate existing functionality. Reuse existing:
- corpus ingestion
- hybrid RAG
- citation validation
- deadline rules
- document generation
- OTEL trace IDs
- outbox/worker patterns
- frontend HUD/state APIs if present

---

## 1. Implementation principle

The 4 agents are not a new product layer separate from lawapp.

They must be wired into the existing lawapp pipeline:

```text
User facts/evidence
  -> AEE extracts structured timeline
  -> user confirms facts
  -> RAG retrieves local authorities + exact rules
  -> ART triages from retrieved bundle only
  -> SEA drafts from ART assessment only
  -> Citation Guard validates every citation/legal assertion
  -> backend saves result
  -> frontend HUD displays live workflow state
```

The Mother Algorithm controls the sequence. Agents must never talk to each other directly.

---

## 2. File structure to implement

Use this structure unless the existing repo already has better equivalent modules:

```text
backend/
  core/
    agentic/
      __init__.py
      mother_algorithm.py
      schemas.py
      prompts.py
      litellm_adapter.py
      pii.py
      policy.py
      citation_guard.py
      cache_policy.py
      audit.py
      errors.py

db/
  migrations/
    027_agentic_architecture.sql

tests/
  test_agents_schema_validation.py
  test_agent_aee.py
  test_agent_art.py
  test_agent_sea.py
  test_agent_citation_guard.py
  test_agent_escalation_policy.py
  test_agent_semantic_cache_policy.py
  test_agent_observability.py
  test_agent_prompt_injection.py
  test_agent_pii_boundary.py
  test_legal_boundary_guard.py
  test_agentic_workflow_e2e.py

scripts/
  check-agentic-workflow.sh

config/
  litellm.lawapp.yaml
```

If you choose different paths, explain why and prove imports still work.

---

## 3. Phase 1 - Schema wall

### Task

Create strict Pydantic schemas in:

```text
backend/core/agentic/schemas.py
```

Required models:
- `AgentName`
- `Jurisdiction`
- `AEEInput`
- `AEEEvent`
- `AEEOutput`
- `ARTInput`
- `ARTOutput`
- `SEAInput`
- `SEAOutput`
- `CitationGuardInput`
- `CitationGuardOutput`
- `AgentRunRecord`
- `AgentValidationFailure`
- `AgentEscalationRecord`

### Requirements

- Use strict enums.
- Forbid extra keys.
- Validate confidence scores between 0 and 1.
- Validate viability score between 0 and 100.
- Validate ISO dates.
- Validate `trace_id` and `case_id`.
- Reject conversational wrappers around JSON.
- Do not silently repair bad output.

### Tests

Create:

```text
tests/test_agents_schema_validation.py
```

Must test:
- valid outputs pass
- extra keys fail
- invalid enum fails
- conversational prefix fails
- markdown-fenced JSON fails
- missing required field fails
- wrong score type fails
- wrong date format fails

Run:

```bash
pytest -q tests/test_agents_schema_validation.py
```

Do not continue until green.

---

## 4. Phase 2 - Agent prompts as versioned constants

### Task

Create:

```text
backend/core/agentic/prompts.py
```

Each prompt must have:
- `prompt_id`
- `version`
- `agent_name`
- `system_directive`
- `allowed_output_schema`
- `forbidden_actions`

Required prompts:
- `AEE_SYSTEM_DIRECTIVE_V1`
- `ART_SYSTEM_DIRECTIVE_V1`
- `SEA_SYSTEM_DIRECTIVE_V1`
- `CITATION_GUARD_SYSTEM_DIRECTIVE_V1`

### Requirements

- Prompts must not be assembled from user input.
- User input must be passed as JSON payload only.
- Prompts must explicitly say user text is evidence, not instruction.
- ART prompt must say: retrieval bundle and rules are the only legal source.
- SEA prompt must say: no new claims, no new citations.
- Guard prompt must say: one failed citation fails the output.

### Tests

Add tests to ensure:
- prompts contain no API keys
- prompts contain legal boundary restriction
- prompts contain JSON-only restriction where applicable
- prompts contain no "guaranteed win" language
- prompts include the schema name/version

Run:

```bash
pytest -q tests/test_agent_prompt_injection.py tests/test_legal_boundary_guard.py
```

---

## 5. Phase 3 - LiteLLM adapter

### Task

Create:

```text
backend/core/agentic/litellm_adapter.py
config/litellm.lawapp.yaml
```

### Requirements

Only this adapter may import LiteLLM.

Required function:

```python
call_model(
    *,
    agent_name: AgentName,
    model_route: str,
    system_prompt: str,
    payload: dict,
    response_schema: type[BaseModel],
    trace_id: str,
    case_id: str,
    allow_cloud: bool = False,
    pii_allowed: bool = False,
) -> BaseModel
```

### Routing rules

- AEE -> local only
- SEA -> local only
- Citation Guard -> local/deterministic only
- ART -> local first
- ART cloud escalation only if all are true:
  - local confidence below threshold
  - grounding score above threshold
  - PII scrub passed
  - retrieved authorities present
  - escalation reason logged

### Tests

Create:

```text
tests/test_agent_escalation_policy.py
tests/test_agent_pii_boundary.py
```

Run:

```bash
pytest -q tests/test_agent_escalation_policy.py tests/test_agent_pii_boundary.py
```

---

## 6. Phase 4 - PII scrubber and boundary

### Task

Create:

```text
backend/core/agentic/pii.py
```

### Requirements

Implement deterministic redaction for:
- person names where known from case context
- employer name
- manager name
- email
- phone
- address-like strings
- DOB
- NI number patterns
- bank/financial references
- medical terms where possible
- free-text configured redactions

### Hard rule

Do not log raw user evidence.

### Tests

Create:

```text
tests/test_agent_pii_boundary.py
```

Must prove:
- redaction works
- cloud payload has no PII
- traces/logs/cache do not contain raw PII
- AEE can process raw local-only input, but ART cloud escalation receives scrubbed input only

---

## 7. Phase 5 - Database migration

### Task

Create:

```text
db/migrations/027_agentic_architecture.sql
```

Required tables:

```sql
CREATE TABLE IF NOT EXISTS agent_runs (...);
CREATE TABLE IF NOT EXISTS agent_artifacts (...);
CREATE TABLE IF NOT EXISTS agent_validation_failures (...);
CREATE TABLE IF NOT EXISTS agent_escalations (...);
CREATE TABLE IF NOT EXISTS citation_guard_results (...);
```

### Minimum required fields

`agent_runs`:
- id
- trace_id
- case_id
- agent_name
- model_name
- model_route
- prompt_id
- prompt_version
- input_schema_version
- output_schema_version
- started_at
- completed_at
- status
- validation_passed
- grounding_score
- confidence_score
- escalated
- failure_reason
- created_at

`citation_guard_results`:
- id
- trace_id
- case_id
- document_id
- safety_check_passed
- failed_citations jsonb
- unsupported_legal_assertions jsonb
- reserved_activity_flags jsonb
- boundary_notice_present
- reason_for_failure
- created_at

### Proof commands

```bash
docker compose exec -T db psql "$DATABASE_URL" -f db/migrations/027_agentic_architecture.sql
docker compose exec -T db psql "$DATABASE_URL" -c "\d agent_runs"
docker compose exec -T db psql "$DATABASE_URL" -c "\d citation_guard_results"
```

---

## 8. Phase 6 - Mother Algorithm

### Task

Create:

```text
backend/core/agentic/mother_algorithm.py
```

Required public function:

```python
process_agentic_case(case_id: str, payload: dict, trace_id: str) -> dict
```

### Required sequence

1. Validate input.
2. Run AEE local-only.
3. Save AEE output as unconfirmed extraction.
4. Require user confirmation before ART. For automated E2E test, use fixture with `user_confirmed_facts_only=true`.
5. Run existing hybrid RAG and exact rules retrieval.
6. Run ART local.
7. If ART needs escalation, run policy check and scrub payload before cloud.
8. Validate ART output.
9. If document requested and ART is sufficiently grounded, run SEA.
10. Validate SEA output.
11. Run Citation Guard.
12. Save final artifact only if Guard passes.
13. Return structured workflow state.
14. Emit OTEL and DB audit rows at every step.

### Required failure behavior

Fail closed if:
- AEE invalid
- user facts unconfirmed
- RAG weak
- rules missing for deadline/cap
- ART invalid
- ART insufficient grounding
- SEA adds unsupported citation
- Guard fails
- legal boundary phrase found
- PII boundary fails

### Tests

Create:

```text
tests/test_agentic_workflow_e2e.py
```

Run:

```bash
pytest -q tests/test_agentic_workflow_e2e.py
```

---

## 9. Phase 7 - API routes

### Task

Add to existing FastAPI app:

```text
POST /api/agents/aee/extract
POST /api/agents/art/triage
POST /api/agents/sea/draft
POST /api/agents/guard/validate
POST /api/cases/{case_id}/agentic-assessment
GET  /api/cases/{case_id}/agent-runs
GET  /api/agent-health
```

### Hard rules

- Debug/test routes must be clearly named `/api/test/...`.
- Product routes must not return static/fake values.
- Every route returns trace_id.
- Every route rejects unvalidated agent output.
- Every route logs agent_runs.

### Proof commands

```bash
curl -sS http://localhost:8000/api/agent-health | jq .
curl -sS -X POST http://localhost:8000/api/agents/aee/extract \
  -H 'Content-Type: application/json' \
  -d @tests/fixtures/aee_input.json | jq .
curl -sS -X POST http://localhost:8000/api/cases/test-case/agentic-assessment \
  -H 'Content-Type: application/json' \
  -d @tests/fixtures/agentic_assessment_input.json | jq .
```

---

## 10. Phase 8 - Frontend HUD wiring

### Task

Bind frontend HUD/workflow state to backend APIs.

### Required HUD states

- evidence_received
- aee_extracted
- user_confirmation_required
- user_confirmed
- rag_retrieved
- rules_resolved
- art_completed
- insufficient_grounding
- sea_drafted
- citation_guard_passed
- document_saved
- blocked_reason
- owner_gated_reason
- trace_id

### Hard rules

- No fake/static HUD values.
- No placeholder legal state.
- If backend is unavailable, frontend must show unavailable, not fake success.
- Show citations and source URLs when available.
- Show licence-gated case law honestly.

### Proof commands

Claude Code must inspect actual frontend stack first and provide correct commands. Example if simple static page:

```bash
grep -R "agentic\|HUD\|workflow\|citation\|trace_id\|placeholder\|mock\|static" -n client | sed -n '1,240p'
```

If Playwright or frontend tests exist, add/run:

```bash
pytest -q tests/test_frontend_agentic_hud.py
```

or the repo's existing frontend test command.

---

## 11. Phase 9 - End-to-end script

### Task

Create:

```text
scripts/check-agentic-workflow.sh
```

The script must:
- start or verify services
- apply migration
- verify corpus tables
- verify rules
- verify local model route or mark model unavailable
- run API path
- query DB audit rows
- verify Guard result
- verify document saved only on Guard pass
- verify frontend HUD API returns real state
- check logs/traces for PII leak patterns
- exit non-zero on failure

### Run

```bash
bash scripts/check-agentic-workflow.sh
```

---

## 12. Phase 10 - Full test gate

Run:

```bash
pytest -q \
  tests/test_agents_schema_validation.py \
  tests/test_agent_aee.py \
  tests/test_agent_art.py \
  tests/test_agent_sea.py \
  tests/test_agent_citation_guard.py \
  tests/test_agent_escalation_policy.py \
  tests/test_agent_semantic_cache_policy.py \
  tests/test_agent_observability.py \
  tests/test_agent_prompt_injection.py \
  tests/test_agent_pii_boundary.py \
  tests/test_legal_boundary_guard.py \
  tests/test_agentic_workflow_e2e.py
```

Also run existing tests:

```bash
pytest -q
```

If full test suite is too slow or blocked, report exact failing/blocking tests. Do not claim accepted.

---

## 13. Required final report

Stop and report. Do not proceed beyond this architecture until owner approves.

Report must include:

```text
1. Git status
2. Files changed
3. DB migrations
4. Agent schemas
5. Agent prompts
6. LiteLLM adapter/routing
7. PII boundary
8. Mother Algorithm flow
9. API routes
10. Frontend HUD wiring
11. Tests added
12. Tests passed/failed
13. Raw DB proof
14. Raw API proof
15. Raw frontend proof
16. Security/prompt-injection proof
17. Case-law licence-gate proof
18. Owner-gated items
19. Not started
20. Approval command
```

Print and wait:

```text
APPROVED_AGENTIC_ARCHITECTURE=true
```

Do not start Workflow A/B/C or further features until this is approved.
