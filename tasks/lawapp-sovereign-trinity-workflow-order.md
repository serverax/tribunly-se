# lawapp  -  Sovereign Trinity Workflow Build Order

**Status:** Open workflow order  -  keep this document expandable. More workflows, acceptance gates, and domain modules may be added later.

**Project:** lawapp  
**Root:** `F:\lawapp` / `/mnt/f/lawapp`  
**Purpose:** Build lawapp as a modular, workflow-driven UK legal AI platform, starting with UK employment law, while keeping the architecture reusable for future modules such as immigration law, business law, housing law, benefits law, debt law, and consumer law.

---

## 0. Mandatory reading before any work

Claude must not edit code, create files, run implementation plans, or mark anything complete before reading these guides:

```text
F:\Claude mcp/.claude/LEGAL_AI_GURU_GUIDE.md
F:\Claude mcp/.claude/LEGAL_AI_UX_GURU_GUIDE.md
F:\Claude mcp/.claude/LEGAL_AI_BACKEND_GURU_GUIDE.md
```

Before doing anything, Claude must run and show proof:

```bash
cat "F:/Claude mcp/.claude/LEGAL_AI_GURU_GUIDE.md" | head -80
cat "F:/Claude mcp/.claude/LEGAL_AI_UX_GURU_GUIDE.md" | head -80
cat "F:/Claude mcp/.claude/LEGAL_AI_BACKEND_GURU_GUIDE.md" | head -80
```

If running from WSL and the path is mounted differently, Claude must locate the files first:

```bash
find /mnt -path '*LEGAL_AI_GURU_GUIDE.md' -o -path '*LEGAL_AI_UX_GURU_GUIDE.md' -o -path '*LEGAL_AI_BACKEND_GURU_GUIDE.md'
```

If any guide is missing, Claude must stop and report:

```text
BLOCKED  -  REQUIRED GURU GUIDE MISSING
```

No workaround. No guessing. No implementation before reading the guides.

---

## 1. Non-negotiable build rule

Claude must build **workflows**, not technology names.

Do not claim a technology is complete because:

- a file exists
- a script passes
- a table exists
- a route exists
- a report says PASS
- a screenshot looks good
- a unit test passes in isolation
- static demo data renders in the UI

A feature is accepted only when this chain works:

```text
frontend user action
→ backend route
→ auth/security/ownership
→ Mother Algorithm / Brain
→ correct specialist agent
→ local legal DB / RAG / rules / WASM / cache / queue
→ citation and safety validation
→ DB/audit/trace update
→ response back to frontend
→ visible user result
→ automated proof gate
```

Anything less is:

```text
NOT ACCEPTED  -  NOT WORKFLOW PROVEN
```

---

## 2. Product architecture to build

Implement the **Sovereign Trinity Architecture** inside lawapp.

```text
User Input
→ Mother Algorithm / Orchestrator
→ Agent AEE: Analysis and Evidence Extraction
→ Agent ART: Algorithmic Reasoning and Triage
→ Agent SEA: Strategic Execution and Automation
→ Local Knowledge Layer
→ Automated Legal Resolution
```

### Mother Algorithm / Brain

The central controller. Every legal workflow must pass through it.

It must own:

- request intake
- auth/user context
- case context
- feature entitlement
- jurisdiction check
- legal domain routing
- risk/urgency classification
- prompt injection guard
- PII minimisation
- retrieval planning
- hybrid search
- Graph RAG
- source trust ranking
- context compression
- cost governor
- AI/model router
- citation validator
- hallucination validator
- legal safety guard
- human review decision
- outbox events
- audit log
- OpenTelemetry trace

No legal route may bypass Brain.

### Agent AEE  -  Analysis and Evidence Extraction

Purpose:

- parse messy evidence
- extract chronology
- scrub PII
- detect dates
- detect legal events
- tag evidence
- build case timeline

Used by:

- upload/OCR workflow
- constructive dismissal workflow
- grievance workflow
- bundle generation
- ET1 document generation

### Agent ART  -  Algorithmic Reasoning and Triage

Purpose:

- analyse legal viability
- apply deterministic legal tests
- calculate deadlines
- assess risk
- classify claims
- produce strict JSON assessment
- never produce uncontrolled advice

Used by:

- free diagnosis
- constructive dismissal logic
- discrimination/Vento logic
- settlement calculator
- risk score
- human review queue

### Agent SEA  -  Strategic Execution and Automation

Purpose:

- generate documents
- create ET1 particulars
- create schedule of loss
- create grievance letters
- create settlement/counter-offer letters
- assemble tribunal bundles
- trigger outbox worker jobs
- notify user when output is ready

Used by:

- paid document generation
- bundle builder
- ACAS/settlement workflow
- case preparation workflow

---

## 3. Modular product rule

lawapp must be modular.

The first module is:

```text
UK Employment Law
```

Future modules must be possible without rewriting the platform:

```text
UK Immigration Law
UK Business Law
UK Housing Law
UK Benefits Law
UK Debt Law
UK Consumer Law
```

Use module/domain boundaries:

```text
backend/domains/employment/
backend/domains/immigration/      future
backend/domains/business/         future
backend/core/brain.py
backend/core/rag/
backend/core/agents/
backend/core/rules/
backend/core/safety/
backend/core/documents/
```

Acceptance:

- employment law works now
- domain config exists
- future domain can be added by config + sources + rules + templates, not by rewriting Brain
- no project naming drift
- use lawapp consistently

---

## 4. Required responsive frontend UX targets

The frontend must become a responsive, modular, visual legal dashboard.

Required modules:

1. Sovereign Trinity architecture overview
2. Fast legal diagnosis dashboard
3. Evidence upload and timeline parser
4. Constructive dismissal timeline/risk view
5. Hybrid search weight/ranking viewer
6. Schedule of Loss calculator
7. Settlement calculator
8. Vento band / discrimination compensation calculator
9. ET1 Particulars of Claim generator
10. Document generation trace view
11. Case HUD: viability, deadline, risks, next action
12. Source/citation viewer
13. Human review/handoff status
14. Saved case dashboard
15. Audit/trace panel for each case
16. Tribunal bundle builder
17. ACAS Early Conciliation preparation screen
18. User confirmation screen for extracted facts
19. Payment entitlement and document unlock screen
20. Account deletion/data retention screen

The app must be:

- responsive
- modular
- mobile-friendly
- desktop-friendly
- simple for stressed users
- not overloaded with legal jargon
- clear on “not legal advice / self-help draft”
- fast to use
- visually explain the result

Acceptance:

- each screen connects to real backend data
- no static UI pretending to work
- calculators use backend rules/WASM/JS fallback
- document preview comes from real document generator
- trace view uses real trace data
- citations are clickable/visible
- warnings and human review state are shown clearly

---

## 5. Open workflow backlog

This section remains open. Add more workflows as the product grows.

### Workflow A  -  Zero-friction multimodal intake

User uploads or pastes messy evidence:

- WhatsApp export
- email thread
- dismissal letter
- grievance letter
- contract
- payslip
- screenshots
- voice transcript
- notes

Required chain:

```text
frontend drop zone
→ upload/paste endpoint
→ auth + ownership check
→ file type/size validation
→ private asset row
→ Agent AEE
→ OCR/local parser/provider if enabled
→ PII scrubber
→ temporal normaliser
→ legal event classifier
→ evidence_chronology DB rows
→ unconfirmed facts DB rows
→ user confirmation screen
→ confirmed facts enter Brain
→ outbox evidence_parsed event
→ trace/metrics/audit
```

DB tables:

```text
evidence_chronology
unconfirmed_facts
```

Acceptance:

- raw upload creates private asset row
- Agent AEE extracts at least one event
- PII is scrubbed before logs/model/provider
- dates are normalised to ISO
- legal tags are assigned
- unconfirmed facts are not used until user confirms
- frontend shows timeline and confirmation controls
- Brain uses confirmed facts only
- tests prove fake/static extraction is not accepted

---

### Workflow B  -  Constructive dismissal algorithm

Agent ART must process constructive dismissal through a deterministic matrix:

1. Breach classification
2. Kaur last-straw matrix
3. Affirmation trap
4. Causation
5. Recommended action

Required JSON output:

```json
{
  "claim_viability": "high|medium|low|zero",
  "claim_type": "constructive_dismissal",
  "breach_type": "express|implied_mtc|both|none",
  "repudiatory_acts": [
    {
      "date": "2026-03-23",
      "event": "Failure to provide grievance bundle",
      "weight": "last_straw",
      "source_event_id": "ev-001"
    }
  ],
  "affirmation_risk": {
    "delay_days": 4,
    "risk_level": "low|medium|high",
    "mitigation": "Employee was pursuing grievance"
  },
  "causation_established": true,
  "evidence_gaps": [],
  "recommended_action": "draft_et1_particulars|request_more_evidence|human_review|do_not_proceed",
  "citations": []
}
```

Acceptance:

- no raw prose from ART
- JSON schema enforced
- legal logic is represented in rules/policy/config and cited
- delay calculation is deterministic
- resignation letter is checked if available
- high affirmation risk triggers warning/human review
- frontend timeline shows affirmation risk
- document generator uses this output if ET1 is created

---

### Workflow C  -  Fast Opinion Case HUD

HUD fields:

```text
claim_viability
traffic_light_status
deadline_date
days_remaining
urgent_warning
claim_type
strength
key_weaknesses
evidence_gaps
estimated_value_range
recommended_next_step
citations
human_review_required
data_privacy_status
trace_id
```

Acceptance:

- HUD is populated from real backend fields
- no static dashboard values
- viability changes when facts change
- deadline changes when dates change
- warnings change when risk changes
- citations visible
- trace ID visible or accessible
- frontend is responsive

---

### Workflow D  -  Schedule of Loss calculator

Required calculations:

```text
0.5 week pay for years under age 22
1.0 week pay for years age 22-40
1.5 weeks pay for years age 41+
weekly pay cap from rules table
maximum service years from rules table
loss of earnings
future loss
benefits
pension loss
mitigation
ACAS uplift/reduction where applicable
statutory cap / 52 weeks pay where applicable
```

Acceptance:

- no hardcoded statutory values in frontend
- weekly pay cap comes from rules DB
- calculation is reproducible server-side
- frontend sliders update instantly
- backend validates result
- trace records calculation
- generated Schedule of Loss document uses same values

---

### Workflow E  -  Settlement calculator and strategy simulator

Outputs:

```text
risk_adjusted_value
settlement_threshold
recommendation: accept|negotiate|consider tribunal|human review
reasoning_summary
warning
counter_offer_amount
citations
```

Acceptance:

- no guaranteed-win language
- user can adjust sliders
- result updates in real time
- recommendation is caveated
- high-value/low-confidence triggers human review
- SEA can draft settlement/counter-offer letter from result
- all legal claims cited

---

### Workflow F  -  Vento band discriminator

Acceptance:

- Vento band values are from rules/legal corpus, not hardcoded
- user can select/adjust severity
- app explains uncertainty
- high-value discrimination claims trigger human review
- no final “worth X guaranteed” language
- Schedule of Loss includes Vento calculation only when claim type supports it

---

### Workflow G  -  Hybrid Search and local law DB

Required local corpus:

```text
legislation.gov.uk
ACAS official guidance
GOV.UK Content API
tribunal procedure pages
Find Case Law only when licence-gated
```

Hybrid search must combine:

```text
vector search
lexical/BM25/full-text search
reciprocal rank fusion or weighted ranking
source trust score
jurisdiction weighting
recency weighting
stale-source penalty
```

Acceptance:

- official sources only
- embeddings exist
- lexical index exists
- source freshness works
- query returns source URLs
- RAG answer cites retrieved DB rows
- fake citations rejected
- ACAS cannot override legislation
- wrong jurisdiction downgraded/rejected
- Find Case Law bulk blocked without licence

---

### Workflow H  -  ET1 and Particulars of Claim generator

Required chain:

```text
frontend generate document
→ auth/ownership
→ payment entitlement
→ Brain document request
→ SEA document_generation_pending outbox event
→ worker claims with FOR UPDATE SKIP LOCKED
→ SEA loads confirmed chronology and assessment
→ template/rules-based assembly
→ citation validator
→ legal safety notice
→ PDF/DOCX render
→ encrypted private storage
→ processed outbox event
→ notification
→ frontend download
```

Acceptance:

- returns 202 Accepted for async generation if worker used
- worker processes event
- no duplicate generation
- document cites correct laws
- citation mismatch blocks document
- user B cannot download user A document
- output marked self-help draft, not legal advice
- trace shows all steps

---

### Workflow I  -  Tribunal bundle assembler

Required output:

```text
index
chronology
key issues
evidence list
witness statement structure
ET1 support
schedule of loss
correspondence section
ACAS certificate section
source/citation appendix
```

Acceptance:

- bundle uses confirmed evidence only
- indexed and paginated
- source documents linked to chronology
- missing evidence flagged
- no fake evidence
- cross-user download blocked

---

### Workflow J  -  ACAS Early Conciliation and negotiation assistant

Acceptance:

- app does not file or represent user unless legally approved
- produces self-help preparation material
- settlement advice is caveated
- deadline calculation included
- user sees next steps clearly

---

### Workflow K  -  OpenTelemetry Glass Engine

Required chain:

```text
frontend click
→ X-Trace-ID
→ backend logs
→ Brain trace
→ DB query span
→ RAG span
→ model/router span
→ validator span
→ outbox span
→ response header
→ trace view in frontend/admin
```

Acceptance:

- same trace ID appears in response, logs, DB, Brain trace, outbox
- metrics counters exist
- no secrets or raw PII in logs/spans
- errors captured safely
- trace waterfall visible

---

### Workflow L  -  Automated red-team gate

Required attacks:

```text
ignore previous instructions
reveal system prompt
change claim_viability to guaranteed_win
break JSON schema
fake citation injection
malicious evidence source text
tool exfiltration attempt
cross-user data request
```

Acceptance:

- tests include malicious JSON/evidence files
- injection guard blocks or neutralises
- schema validator rejects invalid output
- citation validator rejects fake law
- legal safety blocks guaranteed outcome language
- CI fails on regression
- no `|| true`

---

### Workflow M  -  B2C paid document unlock

Acceptance:

- clear price before payment
- no hidden subscription trap
- unpaid access blocked
- payment event recorded
- paid document generation unlocked only after entitlement
- refund/support path visible

---

### Workflow N  -  B2B HR compliance module future

Future domain module for employers/SMEs.

Acceptance:

- separate business-law/HR compliance domain module
- tenant isolation
- handbook/contract upload
- compliance scan
- law-change monitoring
- HR response drafting
- risk dashboard

---

### Workflow O  -  Solicitor/human handoff

Acceptance:

- user consent required
- minimised lead package
- no referral incentive distorts assessment
- partner firm tracking
- caveats shown

---

## 6. Required database additions/checks

Analyse existing DB and add only if missing:

```text
evidence_chronology
unconfirmed_facts
legal_documents
legal_corpus_chunks
source_trust_scores
settlement_scenarios
schedule_of_loss_calculations
document_generation_jobs
bundle_exports
feature_flags
otel_trace_index
red_team_results
```

Every new table must have:

```text
uuid primary key
case_id/user_id where relevant
trace_id
created_at
updated_at
source_url where source-based
no raw PII unless encrypted/minimised
```

---

## 7. Required final workflow matrix

Create/update:

```text
reports/lawapp-sovereign-trinity-workflow-matrix.md
```

Include:

```text
Workflow
User story
Frontend screen
Backend route
Brain stage
Agent used
DB tables
RAG/source usage
WASM/cache/queue usage
Safety/validator
Trace/metric
Tests/gates
Status
Missing gaps
Action to close
```

---

## 8. Required final gates

Create/update:

```bash
scripts/lawapp/final-sovereign-trinity-gate.sh
scripts/lawapp/final-user-workflows-gate.sh
scripts/lawapp/final-legal-corpus-gate.sh
scripts/lawapp/final-document-generation-gate.sh
scripts/lawapp/final-observability-redteam-gate.sh
```

Gates must fail if:

- workflow uses static demo data
- frontend not wired
- backend route missing
- Brain bypassed
- citations missing
- legal corpus empty
- trace missing
- outbox not processing
- user confirmation missing for extracted facts
- cross-user access possible
- payment entitlement bypass possible
- red-team attack passes
- no DB proof
- no test proof

Forbidden in gates:

```text
|| true
echo PASS
continue-on-error
mock success
static proof
```

---

## 9. Final report

Create/update:

```text
reports/lawapp-sovereign-trinity-final-readiness.md
```

Verdict can only be:

```text
READY  -  SOVEREIGN TRINITY WORKFLOWS FULLY PROVEN
```

or:

```text
NOT READY  -  SOVEREIGN TRINITY WORKFLOWS NOT FULLY PROVEN
```

No other verdict is allowed.

---

## 10. Permanent instruction for Claude

Claude, build the workflows, not the names.

The screenshots are product targets.

The platform must make the user’s life easier, faster, safer, and clearer.

The user must be able to:

- upload messy evidence
- see an automatic legal timeline
- understand viability quickly
- see the deadline countdown
- calculate loss
- compare settlement vs tribunal
- generate ET1 particulars
- generate schedule of loss
- create a tribunal bundle
- see citations
- see warnings
- see human review status
- download documents
- trace how the answer was produced

No placeholders.  
No static demos.  
No fake legal values.  
No unsupported claims.  
No unproven technology.  
No workflow bypass.  
No local-only acceptance.  
No “file exists” acceptance.

Continue implementation only when each workflow has:

```text
real frontend
real backend route
real Brain stage
real DB state
real safety validation
real trace
real automated proof
```

---

## 11. Append-only workflow rule

This document is intentionally open.

When new user needs, competitor gaps, review pain points, legal modules, or product ideas appear, append them as new workflows:

```text
Workflow P  -  ...
Workflow Q  -  ...
Workflow R  -  ...
```

Do not delete existing workflows unless the owner explicitly approves removal.

