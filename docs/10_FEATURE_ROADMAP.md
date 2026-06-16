# 10 - Lawapp Feature Roadmap (additive to 01_BUILD_PLAN.md)

**Type:** Phased feature specification  -  adds to and extends the original six-phase plan.
**Project root:** `F:\lawapp`
**Positioning:** AI-first UK employment claim co-pilot. Instant cited diagnosis, rules-backed
engine, deadline protection, evidence intelligence, document readiness, audit trail, optional
human coaching, optional solicitor review. Transparent one-off pricing with optional subscription.

**Not:** an AI lawyer, robot lawyer, Valla clone, template site, or general legal chatbot.
**Never:** conducts litigation, files claims, represents users, or guarantees outcomes.

---

## General guardrails (apply to every phase)

1. Never call lawapp an "AI lawyer" or imply it replaces a solicitor.
2. Never conduct litigation, file claims, or represent users.
3. Never guarantee outcomes. Honesty is the product.
4. AI and coaching are self-help support only.
5. Solicitor advice is only from authorised solicitors or regulated firms.
6. External LLM calls require de-identification (UK GDPR Art.9).
7. Legal facts come from rules/retrieval, not model memory.
8. Governance gate is mandatory on every assessment output.
9. FCL bulk ingestion blocked until licence grant.
10. OpenAI quota blocks embeddings only  -  structured engine work continues.

---

## PHASE 2C  -  Structured assessment and audit foundation

### Task list

| # | Task | Status |
|---|---|---|
| 2C-1 | Canonical structured assessment object with all fields | DONE |
| 2C-2 | `employer_arguments` field added to schema + assess_logic | **IN PROGRESS** |
| 2C-3 | Case weakness engine: key_weaknesses + employer may argue | **IN PROGRESS** |
| 2C-4 | Citation transparency: every assertion maps to a source | DONE (BM25) |
| 2C-5 | Assessment audit log schema (`assessment_audit_logs`) | **IN PROGRESS** |
| 2C-6 | `/assess` response includes `governance_result` + `boundary_log` | DONE |
| 2C-7 | Tests: weaknesses, employer_arguments, audit, OOS, no-PII | PARTIAL |

### 2C-2/2C-3 Assessment schema additions

The canonical structured assessment object gains `employer_arguments`:

```
claim_type, jurisdiction, in_scope,
has_viable_claim: yes/no/uncertain,
strength: low/medium/high/uncertain,
reasoning_summary,
value_range,
key_weaknesses,           ← always populated for non-trivial cases
employer_arguments,       ← NEW: what the employer may argue
deadline,
recommended_next_step,
citations,                ← every assertion maps to a cited source
grounding_score,
confidence_score,
insufficient_grounding,
boundary_log,
governance_result
```

Employer argument examples (generated deterministically from facts):
- "Employer may argue the reason was potentially fair (conduct/capability/redundancy)"
- "Employer may argue the procedure was reasonable given the circumstances"
- "Employer may argue the claimant failed to mitigate loss"
- "Employer may argue service is below the qualifying period"
- "Employer may argue the deadline has expired and the claim is out of time"

### 2C-5 Assessment audit log schema

See `db/migrations/003_phase2c_audit.sql`.

### 2C test requirements

- Weak case (QP fail) shows `key_weaknesses` and `employer_arguments`
- Employer arguments populated where conduct/redundancy reason given
- Unsupported legal assertion blocked by governance (no citation → insufficient_grounding)
- Audit payload created on every governed assessment
- Out-of-scope returns `not_supported` with no assessment fields
- No raw PII in model payload (boundary_log proves it)

---

## PHASE 3  -  MVP dashboard, retention, pricing, coaching

### Task list

| # | Task | Phase | Status |
|---|---|---|---|
| 3-1 | User case dashboard (deadline, strength, weaknesses, next action) | 3 | Planned |
| 3-2 | Deadline protection loop (deterministic, no LLM) | 3 | Planned |
| 3-3 | Next action checklist (case-specific, computed from missing facts) | 3 | Planned |
| 3-4 | Document readiness engine + `document_readiness` table | 3 | Planned |
| 3-5 | Paid document flow (show readiness before payment) | 3 | Planned |
| 3-6 | Human coaching flow + `support_sessions` table | 3 | Planned |
| 3-7 | Solicitor review flow + `solicitor_reviews` table | 3 | Planned |
| 3-8 | Pricing model (free diagnosis, one-off docs, coaching, review) | 3 | Planned |
| 3-9 | Reminder events + `reminder_events` table | 3 | Planned |
| 3-10 | Tests for all Phase 3 flows | 3 | Planned |

### 3-1 Dashboard cards (always visible)

Every saved case dashboard shows:
- Deadline countdown: date, days remaining, ACAS status, urgency tier
- Case strength: current has_viable_claim + strength from latest assessment
- Key weaknesses (from governed assessment)
- Employer may argue (from governed assessment)
- Next action: top item from checklist
- Missing evidence: computed from case facts
- Document readiness: completion % per document type
- Human coaching CTA: appears when grounding_score < 0.4 or user confused
- Solicitor review CTA: appears on trigger conditions (see 3-7)

No dashboard text is generated outside the governed pipeline + assessment schema.

### 3-2 Deadline protection

Deterministic only  -  no LLM:
- Tribunal deadline from `rules` table + deadline engine
- ACAS EC status: not_started | in_progress | certificate_received
- Urgency tier: >90 days = normal; 30–90 = elevated; <30 = critical; 0 = missed
- Missed-deadline triage: surface s.111(2)(b) "not reasonably practicable"  -  route to solicitor; never compute

### 3-3 Next action checklist

Computed from what facts are missing. Not static. Examples:

| Condition | Checklist item |
|---|---|
| EDT not confirmed | Confirm dismissal/termination date |
| service_start_date missing | Confirm employment start date |
| reason missing | State reason given for dismissal |
| weekly_pay missing | Add weekly gross pay |
| ec_status = not_started | Start ACAS Early Conciliation |
| ec_day_b missing | Upload EC certificate |
| dismissal letter not uploaded | Upload dismissal letter |
| appeal outcome missing | Add appeal outcome |
| Documents < 50% | Begin Particulars of Claim |
| grounding_score < 0.3 | Book human coaching |
| solicitor_review triggered | Book solicitor review |

### 3-4 Document readiness engine

`document_readiness` table: see `db/migrations/004_phase3_tables.sql`.

Document types:
- `particulars_of_claim`: EDT, service length, reason, procedure, weekly pay, EC certificate, appeal
- `schedule_of_loss`: weekly pay, notice period, benefits, future loss estimate, mitigation

Readiness = % of required fields present and confirmed. `can_generate = true` only when all required fields are present.

### 3-5 Paid document flow

- Show readiness percentage before unlocking payment
- Warn/block if required facts missing
- All generated documents marked: "Self-help draft  -  not legal advice  -  prepared by the user using lawapp"
- Never imply solicitor-authored

### 3-6 Human coaching flow

Label: **"Human case-support coaching"** (not "legal advice").

Allowed:
- Help user understand the assessment output
- Organise facts and evidence
- Understand process steps (ACAS, ET1)
- Identify missing information
- Prepare questions for ACAS or a solicitor
- Help complete self-help document drafts

Not allowed:
- Solicitor advice or regulated legal advice
- Representation at any proceedings
- Filing claims on user's behalf
- Outcome guarantees

Provider type: `paralegal_coach`. Must never be labelled "solicitor" unless SRA-authorised.

### 3-7 Solicitor review flow

Trigger on:
- Urgent deadline (< 14 days)
- Missed deadline (s.111(2)(b)  -  discretionary)
- Confidence < 0.3 after full assessment
- Insufficient grounding after evidence added
- Discrimination/whistleblowing/health-safety facts (auto-unfair)
- Complex or high-value case (compensatory > 3× weekly pay estimate)
- Conflicting evidence that changes strength
- User explicitly asks for legal advice, filing, or representation

Handoff pack includes: assessment, deadline, evidence list, document drafts, key weaknesses, audit log summary, user consent.

Referral incentives must never alter the assessment. Free tier's honesty is a hard rule.

### 3-8 Pricing

MVP pricing (in order, no forced subscription):
1. Free diagnosis  -  always free
2. One-off document pack  -  Particulars of Claim + Schedule of Loss
3. One-off human coaching  -  fixed session fee
4. One-off solicitor review  -  fixed review fee (or referral fee model Phase 6)

Optional subscription (Phase 6, not MVP):
- £9/month: case tracker + reminders
- £19/month: case tracker + monthly reassessment + storage

No hidden auto-renewal. Show "pay once" options clearly.

### 3-9 Reminder events

Reminder types: deadline_approaching, acas_not_started, acas_certificate_missing, evidence_missing, document_incomplete, paid_document_ready, solicitor_review_recommended.

Message templates are static strings with placeholders  -  never generatively produced.

### 3-10 Phase 3 tests

- Dashboard returns all required cards
- Deadline warning appears when < 30 days
- Next action checklist computed from missing facts
- Document readiness updates when facts added
- Coaching CTA for incomplete/low-grounding cases
- Solicitor CTA for high-risk triggers
- Coaching flow cannot claim legal advice
- Solicitor review requires `provider_type=solicitor`
- Handoff requires `referral_consent=true`
- Pricing shows no forced subscription

---

## PHASE 4  -  Evidence intelligence and upload

### Task list

| # | Task | Status |
|---|---|---|
| 4-1 | Evidence upload + OCR/extraction pipeline | Planned |
| 4-2 | `evidence_items` table | Planned (migration placeholder) |
| 4-3 | Evidence intelligence: confirms/contradicts/supports/weakens | Planned |
| 4-4 | Contradiction checker | Planned |
| 4-5 | Dynamic case strength update on evidence add | Planned |
| 4-6 | Security: encrypt uploads, confirm before use, no raw to LLM | Planned |
| 4-7 | Phase 4 tests | Planned |

### 4-2 evidence_items schema

See `db/migrations/005_phase4_evidence.sql`.

### 4-3 Evidence intelligence outputs

For each uploaded item, surface:
- What it confirms (facts it supports)
- What it contradicts (contradictions with stated facts)
- What it supports in the assessment
- What it weakens
- Which document sections it affects
- Whether the assessment strength changed

### 4-4 Contradiction checker

Example: "You said dismissal date was 10 May. The letter says 12 May. Please confirm."

User must confirm extracted facts before they enter the assessment. Never silently trust OCR extraction.

### 4-6 Security

- Uploaded documents encrypted at rest (AES)
- Extracted facts require user confirmation step
- No raw document content sent to any external LLM
- De-identification required before any external model sees extracted facts

### 4-7 Phase 4 tests

- Upload creates evidence_item row
- Extracted facts require confirmation before use
- Contradiction detected between upload and stated facts
- Evidence changes document_readiness
- Raw upload not sent externally (boundary_log proves it)

---

## PHASE 5  -  Validation, safety, accuracy, market trust

### Task list

| # | Task | Status |
|---|---|---|
| 5-1 | Accuracy regression suite (legal correctness) | Planned |
| 5-2 | AI quality dashboard (governance metrics) | Planned |
| 5-3 | Bias and fairness review | Planned |
| 5-4 | DPIA and UK GDPR review | Planned |
| 5-5 | User feedback loop + `user_feedback` table | Planned |
| 5-6 | Phase 5 tests | Planned |

### 5-1 Accuracy regression suite

- No legal output without citations (all legal claims cited)
- Wrong/unsupported legal assertion blocked (governance)
- Deadline edge cases (month-end, EC floor, no EC)
- Weak/no-claim outcomes stated plainly
- Uncertain outcomes correctly flagged
- Document quality tests

### 5-2 AI quality dashboard

Track per time period:
- Grounding failures (insufficient_grounding count)
- Confidence failures (low_confidence count)
- Governance blocks (boundary_violation, honesty_violation counts)
- Model unavailable events (MODEL_UNAVAILABLE count)
- User corrections (assessment changes triggered by new facts)
- Human handoffs (coaching bookings)
- Solicitor review triggers

### 5-5 user_feedback schema

See `db/migrations/006_phase5_feedback.sql`.

### 5-6 Phase 5 tests

- Feedback captured with correct case_id
- Governance metrics recorded to AI quality dashboard
- User deletion removes case data (CASCADE)
- Audit log retention behaves as documented

---

## PHASE 6  -  Revenue, B2B, solicitor network

### Task list

| # | Task | Status |
|---|---|---|
| 6-1 | Live solicitor partner integration | Planned |
| 6-2 | Handoff pack (assessment + deadline + evidence + docs + consent) | Planned |
| 6-3 | Referral-fee tracking (never alters assessment) | Planned |
| 6-4 | B2B/union dashboard (member cases, deadline risk, analytics) | Planned |
| 6-5 | Optional subscription pricing (case tracker, reassessment) | Planned |

### 6-1 Handoff pack

Contents:
- Structured assessment (governed output)
- Limitation deadline with source
- Evidence list (user-confirmed items)
- Document drafts (if generated)
- Key weaknesses and employer arguments
- Audit log summary (not raw)
- User referral consent (mandatory)

Referral incentives must never alter the governed assessment. Free diagnosis tier's honesty is a hard architectural rule, not a policy preference.

### 6-4 B2B/union dashboard

Member case views: deadline risk, document readiness, handoff queue, anonymised case analytics (no personal data visible without consent). B2B admin cannot override assessment or governance gate.

---

## DB migration index

| Migration | Phase | Tables created |
|---|---|---|
| `001_initial.sql` | 1 | legislation, case_law_documents, case_law_chunks, acas_guidance, rules, users, cases, documents, referrals |
| `002_case_law_split.sql` | 1 | case_law_documents + case_law_chunks split |
| `003_phase2c_audit.sql` | 2C | assessment_audit_logs |
| `004_phase3_tables.sql` | 3 | document_readiness, support_sessions, solicitor_reviews, reminder_events |
| `005_phase4_evidence.sql` | 4 | evidence_items |
| `006_phase5_feedback.sql` | 5 | user_feedback |

---

## Key design decisions (recorded)

1. **Subscription is optional.** One-off pricing at MVP. No forced subscription.
2. **Coaching is not legal advice.** Label is "human case-support coaching." Provider type = paralegal_coach.
3. **Solicitor referral never alters assessment.** Hard architectural rule.
4. **Retention is built on legal urgency**, not generic engagement. Every retention touchpoint comes from the governed assessment.
5. **Pricing is transparent.** "Pay once" prominently; no hidden auto-renewal.
6. **Lawapp is not an AI lawyer.** Never use that phrase anywhere in the product.
7. **Deterministic deadline only.** No LLM computes or recalls a deadline or cap.
8. **Evidence requires user confirmation.** Never silently trust OCR extraction.
