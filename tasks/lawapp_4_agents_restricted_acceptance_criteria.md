# lawapp - 4-Agent Restricted Acceptance Criteria

**Target path in repo:** `F:\lawapp\tasks\lawapp_4_agents_restricted_acceptance_criteria.md`  
**Status:** HARD GATE. Claude Code must not implement the 4-agent system unless every acceptance criterion below is treated as mandatory.

---

## 0. Purpose

This file defines the restricted acceptance criteria for the LawApp 4-agent architecture:

1. **AEE - Analysis & Evidence Extraction**
2. **ART - Algorithmic Reasoning & Triage**
3. **SEA - Strategic Execution & Automation**
4. **Citation & Safety Guard**

The agents must be controlled by the **Mother Algorithm**. Agents are not independent workers. They are stateless, called only by backend orchestration code, and their outputs must pass strict schema validation before they can affect the database, UI, documents, or user response.

---

## 1. Non-negotiable architecture rules

### AC-001 - Mother Algorithm is the only controller

**Requirement:**  
Agents must not call each other directly. Every agent call must go through the Mother Algorithm / orchestrator.

**PASS proof required:**
- Show the orchestrator file path.
- Show all agent invocation functions.
- Show no direct import/call chain from AEE → ART, ART → SEA, SEA → Guard, or Guard → any other agent.
- Show grep proof:

```bash
grep -R "call_.*agent\|invoke_.*agent\|litellm.completion\|completion(" -n backend | sed -n '1,200p'
```

**FAIL if:**
- Any agent can trigger another agent directly.
- Any agent runs as a background loop.
- Any agent has autonomous browsing, shell execution, file-system access, or DB write access.

---

### AC-002 - Agents must be stateless functions

**Requirement:**  
Each agent receives a JSON payload and returns a JSON payload or a controlled document payload. No persistent internal memory.

**PASS proof required:**
- Show no agent-specific memory table except audit/trace logs.
- Show every agent call includes `trace_id`, `case_id`, `agent_name`, `input_schema_version`, and `output_schema_version`.
- Show no long-running loop or recursive retry inside an agent.

**FAIL if:**
- Agent state is stored outside `agent_runs`, `brain_traces`, audit logs, or normal case records.
- Agent output is accepted without schema validation.

---

### AC-003 - Strict Pydantic validation is mandatory

**Requirement:**  
Every agent output must be validated using Pydantic before use.

**PASS proof required:**
- Show Pydantic models for:
  - `AEEInput`
  - `AEEOutput`
  - `ARTInput`
  - `ARTOutput`
  - `SEAInput`
  - `SEAOutput`
  - `CitationGuardInput`
  - `CitationGuardOutput`
  - `AgentRunRecord`
- Show validation failure test for each agent.

**Required command:**

```bash
pytest -q tests/test_agents_schema_validation.py
```

**PASS condition:**  
All tests pass.

**FAIL if:**
- `json.loads()` output is used without Pydantic validation.
- Extra keys are allowed unless explicitly justified.
- Conversational text before/after JSON is accepted.

---

### AC-004 - JSON-only contract for AEE, ART and Citation Guard

**Requirement:**  
AEE, ART and Citation Guard must return strict JSON only.

**PASS proof required:**
- Test that output like `Here is the JSON: {...}` is rejected.
- Test that markdown fenced JSON is rejected.
- Test that invalid enum values are rejected.
- Test that missing required fields are rejected.

**FAIL if:**
- Markdown or free text is silently stripped and accepted.
- The system “repairs” invalid legal output without logging a failure.

---

### AC-005 - SEA must be document-only but metadata must be JSON-validated

**Requirement:**  
SEA may return Markdown document text, but it must be wrapped in a strict object.

**Required output shape:**

```json
{
  "document_type": "particulars_of_claim|schedule_of_loss|grievance_letter|chronology|evidence_checklist",
  "markdown": "string",
  "citations_used": ["string"],
  "boundary_notice_present": true,
  "generated_from_assessment_id": "uuid",
  "requires_guard_review": true
}
```

**PASS proof required:**
- Test that SEA document output cannot bypass Citation Guard.
- Test that SEA output without boundary notice fails.
- Test that SEA output with citations not in retrieved bundle fails Guard.

---

## 2. Agent-specific acceptance criteria

---

## 2.1 Agent AEE - Analysis & Evidence Extraction

### Role

AEE reads user text/documents and extracts a chronological evidence timeline. It does not give legal advice.

### Required input

```json
{
  "case_id": "uuid",
  "trace_id": "uuid",
  "current_date": "YYYY-MM-DD",
  "raw_text": "string",
  "source_type": "manual_text|email|whatsapp|pdf_ocr|document_upload",
  "jurisdiction": "EW|S|NI|UNKNOWN"
}
```

### Required output

```json
{
  "timeline": [
    {
      "date": "YYYY-MM-DD|null",
      "date_status": "exact|ambiguous|missing|relative_requires_confirmation",
      "event_summary": "string",
      "evidence_type": "dismissal|grievance|disciplinary|contract|pay|sickness|discrimination|acas|other",
      "source_quote": "string",
      "pii_scrubbed": true,
      "confidence": 0.0
    }
  ],
  "missing_critical_dates": true,
  "pii_redactions": [
    {
      "type": "person|employer|phone|email|address|financial|medical|other",
      "replacement": "[EMPLOYER_NAME]"
    }
  ],
  "requires_user_confirmation": true
}
```

### Hard restrictions

AEE must not:
- provide legal advice
- assess claim viability
- cite statutes
- decide deadlines
- create documents
- send raw PII to third-party/cloud models
- write final facts into assessment without user confirmation

### PASS proof required

```bash
pytest -q tests/test_agent_aee.py
```

Must prove:
- PII is scrubbed.
- Dates are ISO-8601 or flagged.
- Ambiguous dates are not guessed silently.
- Output cannot include legal advice.
- Extracted facts require user confirmation before ART receives them.
- Raw user text is not logged.

---

## 2.2 Agent ART - Algorithmic Reasoning & Triage

### Role

ART applies retrieved law to confirmed facts. It is the legal triage agent, but it must reason only from retrieved local DB/corpus sources and deterministic `rules`.

### Required input

```json
{
  "case_id": "uuid",
  "trace_id": "uuid",
  "jurisdiction": "EW|S|NI|UNKNOWN",
  "confirmed_timeline": [],
  "retrieved_authorities": [],
  "exact_rules": [],
  "claim_scope": "unfair_dismissal|constructive_dismissal|discrimination|unknown",
  "user_confirmed_facts_only": true
}
```

### Required output

```json
{
  "claim_type": ["unfair_dismissal", "constructive_dismissal", "discrimination", "none"],
  "viability_score_percentage": 0,
  "strength": "low|medium|high|uncertain",
  "statutory_citations_used": ["string"],
  "case_law_citations_used": ["string"],
  "acas_citations_used": ["string"],
  "key_weaknesses": ["string"],
  "affirmation_risk_detected": false,
  "repudiatory_breach_detected": false,
  "causation_assessed": false,
  "limitation_status": "in_time|near_deadline|out_of_time|unknown",
  "recommended_next_step": "free_diagnosis_only|prepare_documents|seek_solicitor|not_supported|need_more_facts",
  "grounding_score": 0.0,
  "confidence_score": 0.0,
  "insufficient_grounding": true
}
```

### Hard restrictions

ART must not:
- invent legal rules
- use model memory for deadlines/caps/thresholds
- use unconfirmed extracted facts
- cite a law not present in the retrieved bundle
- claim case-law coverage if FCL/case_law tables are empty or licence-gated
- recommend filing, representation, or reserved legal activities
- output a user-facing document

### PASS proof required

```bash
pytest -q tests/test_agent_art.py
```

Must prove:
- No retrieved authorities means `insufficient_grounding=true`.
- No exact rules means no deadline/cap result is generated.
- Empty case_law tables are labelled unavailable/licence-gated.
- Weak cases include `key_weaknesses`.
- Constructive dismissal requires breach, resignation timing, causation and affirmation-risk fields.
- ART output fails validation if it contains unsupported citation strings.

---

## 2.3 Agent SEA - Strategic Execution & Automation

### Role

SEA drafts documents from validated ART output and user-confirmed facts. It must not decide the legal strategy independently.

### Required input

```json
{
  "case_id": "uuid",
  "trace_id": "uuid",
  "document_type": "particulars_of_claim|schedule_of_loss|grievance_letter|chronology|evidence_checklist",
  "validated_assessment": {},
  "confirmed_facts": {},
  "approved_citations": [],
  "template_id": "string",
  "boundary_notice_required": true
}
```

### Required output

```json
{
  "document_type": "particulars_of_claim|schedule_of_loss|grievance_letter|chronology|evidence_checklist",
  "markdown": "string",
  "citations_used": ["string"],
  "boundary_notice_present": true,
  "generated_from_assessment_id": "uuid",
  "requires_guard_review": true
}
```

### Hard restrictions

SEA must not:
- create legal strategy not present in ART output
- add new citations
- add new claims
- imply solicitor status
- include “guaranteed win”, “we will file”, “we represent you”, or similar language
- produce final downloadable document before Citation Guard passes
- produce document from unconfirmed facts

### PASS proof required

```bash
pytest -q tests/test_agent_sea.py
```

Must prove:
- Document includes self-help / not legal advice notice.
- Document cites only approved citations.
- Document is blocked if ART assessment is `insufficient_grounding=true`.
- Document is blocked if Citation Guard not run.
- SEA cannot create a new claim type not present in ART output.

---

## 2.4 Citation & Safety Guard

### Role

The Guard audits every legal assertion and citation before output reaches the user.

### Required input

```json
{
  "case_id": "uuid",
  "trace_id": "uuid",
  "draft_document": "string",
  "assessment": {},
  "verified_citations": [],
  "legal_boundary_rules": []
}
```

### Required output

```json
{
  "safety_check_passed": false,
  "failed_citations": ["string"],
  "unsupported_legal_assertions": ["string"],
  "reserved_activity_flags": ["string"],
  "boundary_notice_present": false,
  "reason_for_failure": "string"
}
```

### Hard restrictions

The Guard must not:
- rewrite the document
- add citations
- approve unknown citations
- approve documents without boundary notice
- approve documents containing reserved-activity wording
- approve documents where case law is cited but case_law source is unavailable/licence-gated

### PASS proof required

```bash
pytest -q tests/test_agent_citation_guard.py
```

Must prove:
- One hallucinated citation fails the whole output.
- One reserved-activity phrase fails the whole output.
- Missing boundary notice fails the output.
- Citation context mismatch fails the output.
- Known citations from retrieved DB pass.

---

## 3. LiteLLM and routing acceptance criteria

### AC-006 - LiteLLM must be a router/governor, not an uncontrolled gateway

**Requirement:**  
LiteLLM must be called only through a central adapter, not scattered across the codebase.

**PASS proof required:**

```bash
grep -R "litellm.completion\|from litellm\|import litellm" -n backend
```

Expected:
- Only one central adapter/module uses LiteLLM directly.

**FAIL if:**
- Multiple backend modules call LiteLLM directly.
- Agents bypass the Mother Algorithm.

---

### AC-007 - Air-gapped/local-first rule

**Requirement:**  
AEE, SEA and Citation Guard default to local/internal model endpoints only.

**PASS proof required:**
- Show LiteLLM config.
- Show model route mapping:
  - AEE → local `lawapp-edge-slm`
  - SEA → local `lawapp-edge-slm`
  - Citation Guard → deterministic/local `lawapp-edge-slm` or non-LLM validator
  - ART → local first, cloud only on strict escalation rule
- Show no raw PII goes to cloud.

**FAIL if:**
- AEE raw text can go to cloud.
- SEA receives raw unredacted evidence unnecessarily.
- Cloud fallback happens silently without audit log.

---

### AC-008 - Cloud escalation is explicit, audited, and de-identified

**Requirement:**  
ART may use heavy/cloud model only if:
- grounding is solid
- local confidence is below threshold
- payload is de-identified
- escalation is logged

**PASS proof required:**
- Test that cloud escalation cannot occur with raw PII.
- Test that cloud escalation cannot occur with weak retrieval.
- Test that escalation creates audit row with reason and trace_id.

**Required command:**

```bash
pytest -q tests/test_agent_escalation_policy.py
```

---

### AC-009 - Semantic cache must never cache raw PII or final legal answers without safety metadata

**Requirement:**  
If Redis semantic cache is implemented, cache keys/values must be de-identified and tagged with:
- jurisdiction
- claim_type
- source corpus version/hash
- rule version/effective date
- grounding score
- guard pass status
- schema version

**PASS proof required:**
- Test cache does not store raw name, email, phone, address, employer name, medical details.
- Test cache miss occurs when corpus version changes.
- Test cache miss occurs when rules version changes.
- Test cached answer cannot bypass Citation Guard.

**Required command:**

```bash
pytest -q tests/test_agent_semantic_cache_policy.py
```

**FAIL if:**
- Cached legal answer is served without rechecking source/rule version and safety status.
- Cached answer includes raw PII.

---

### AC-010 - Observability required for every agent run

**Requirement:**  
Every agent run must produce traceable evidence.

Required fields:
- `trace_id`
- `case_id`
- `agent_name`
- `model_name`
- `input_schema_version`
- `output_schema_version`
- `started_at`
- `completed_at`
- `status`
- `validation_passed`
- `grounding_score`
- `confidence_score`
- `escalated`
- `failure_reason`

**PASS proof required:**
- DB row in `agent_runs` or equivalent.
- OTEL trace links request → orchestrator → agent → validation → guard.
- Metrics counters per agent and failure type.

**Required command:**

```bash
pytest -q tests/test_agent_observability.py
```

---

## 4. Security acceptance criteria

### AC-011 - Prompt injection resistance

**Requirement:**  
User input must be treated as data only. User text must never override system directives.

**PASS proof required:**
- Test user input containing:
  - “ignore previous instructions”
  - “guaranteed win”
  - fake JSON directives
  - fake citation list
  - request to bypass guard
- Expected: rejected, ignored as instruction, or treated as evidence text.

**Required command:**

```bash
pytest -q tests/test_agent_prompt_injection.py
```

---

### AC-012 - No reserved legal activity

**Requirement:**  
System must block:
- “we will file”
- “we represent you”
- “we will act for you”
- “we guarantee”
- “court-ready final advice”
- any implication that LawApp is a solicitor/law firm

**PASS proof required:**

```bash
pytest -q tests/test_legal_boundary_guard.py
```

---

### AC-013 - No raw PII in logs, traces, cache or cloud payloads

**Requirement:**  
PII/special-category data must be redacted before logs/traces/cache/cloud.

**PASS proof required:**

```bash
pytest -q tests/test_agent_pii_boundary.py
```

Must include:
- names
- phone numbers
- emails
- addresses
- employer names
- medical terms
- financial amounts
- DOB
- national insurance number patterns

---

## 5. Database acceptance criteria

### Required tables or equivalent

- `agent_runs`
- `agent_artifacts`
- `agent_validation_failures`
- `agent_escalations`
- `citation_guard_results`

### PASS proof required

```bash
docker compose exec -T db psql "$DATABASE_URL" -c "\dt"
docker compose exec -T db psql "$DATABASE_URL" -c "\d agent_runs"
docker compose exec -T db psql "$DATABASE_URL" -c "\d citation_guard_results"
```

**FAIL if:**
- Agent outputs are not auditable.
- Guard failures are not persisted.
- Escalations are not persisted.

---

## 6. API acceptance criteria

### Required endpoints or equivalent

- `POST /api/agents/aee/extract`
- `POST /api/agents/art/triage`
- `POST /api/agents/sea/draft`
- `POST /api/agents/guard/validate`
- `POST /api/cases/{case_id}/agentic-assessment`
- `GET /api/cases/{case_id}/agent-runs`
- `GET /api/agent-health`

### PASS proof required

```bash
curl -sS http://localhost:8000/api/agent-health | jq .
curl -sS -X POST http://localhost:8000/api/agents/aee/extract -H 'Content-Type: application/json' -d @tests/fixtures/aee_input.json | jq .
curl -sS -X POST http://localhost:8000/api/cases/test-case/agentic-assessment -H 'Content-Type: application/json' -d @tests/fixtures/agentic_assessment_input.json | jq .
```

**FAIL if:**
- API returns fake static values.
- API returns raw model text.
- API returns unvalidated agent JSON.

---

## 7. End-to-end acceptance criteria

### Required E2E path

Manual evidence → AEE extraction → user confirmation → corpus/RAG retrieve → ART triage → SEA draft → Citation Guard → saved document → frontend HUD update.

### PASS proof command

Create and pass:

```bash
bash scripts/check-agentic-workflow.sh
```

This script must prove:
- DB is up
- local model endpoint health checked or stub explicitly marked unavailable
- AEE returns valid JSON
- user-confirmed facts are saved
- RAG returns authorities
- ART output validates
- SEA output validates
- Guard passes or fails correctly
- final document saved only if Guard passes
- frontend HUD API shows real state
- no raw PII in logs/traces/cache/cloud payload

**FAIL if:**
- Any step is skipped.
- Any output is simulated without being labelled test-only.
- Frontend state is static/fake.
- Guard can be bypassed.

---

## 8. Final approval gate

Claude Code must stop and report before asking to continue.

Required report sections:
1. Files changed
2. DB migrations added
3. Pydantic schemas added
4. LiteLLM adapter added
5. Agent prompts added
6. Tests added
7. Raw pytest output
8. Raw API output
9. Raw DB output
10. Frontend HUD proof
11. Known limitations
12. Owner-gated items
13. Exact approval command

Claude Code must print and wait for:

```text
APPROVED_AGENTIC_ARCHITECTURE=true
```

Do not continue after this gate without that exact approval.
