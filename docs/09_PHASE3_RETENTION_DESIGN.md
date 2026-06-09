# 09 - Phase 3: User Retention Loop Design

**Type:** Planning document. Not Phase 2C scope.
**Status:** Design only — no code. Phase 2C continues unblocked.
**Pairs with:** `01_BUILD_PLAN.md` Phase 3, `04_RAG_REASONING_SPEC.md`, `06_USER_STORIES.md` US-3/US-4/US-5.

---

## Retention philosophy

Retention must be built around **legal urgency**, not generic engagement.
The hook is the deadline and the gap between what the user has and what a
tribunal needs. Every retention touchpoint must be grounded in the user's
actual case facts and the governed assessment — never generic legal tips or chat.

---

## Core retention loop

```
Free diagnosis
  → deadline countdown + ACAS status
  → next-action checklist (case-specific)
  → evidence upload prompts (missing facts)
  → case strength update on each evidence add
  → document completion progress
  → reminders (deadline, ACAS, missing evidence)
  → paid document generation unlock
  → solicitor handoff if risk/complexity increases
```

---

## 1. Deadline countdown

Every saved case must surface:
- Limitation date (from `rules` table via deadline engine — deterministic)
- Days remaining
- ACAS Early Conciliation status (started/certificate received/not started)
- Risk level (urgency tier: >90 days = normal; 30-90 days = elevated; <30 days = critical)

Example display:
> "Your tribunal deadline is 30 June 2026. You have 29 days. Start ACAS Early Conciliation immediately."

Implementation:
- `cases.key_dates` JSONB field already carries `limitation_date`
- Deadline engine is already in `backend/engine/deadline.py`
- Urgency tier computed from `(limitation_date - today).days`
- ACAS status stored as a case field: `ec_status`: not_started | in_progress | certificate_received

---

## 2. Next-action checklist

Every case has a dynamic checklist derived from what facts are missing or what steps are incomplete:

| Condition | Action item |
|---|---|
| EDT not confirmed | Confirm dismissal/termination date |
| service_start_date missing | Confirm employment start date |
| reason_for_dismissal missing | State the reason given for dismissal |
| weekly_pay missing | Add weekly/monthly gross pay |
| ec_status = not_started | Start ACAS Early Conciliation |
| ec_status = in_progress | Upload EC certificate when received |
| appeal_outcome missing | Add outcome of any internal appeal |
| dismissal_letter missing | Upload dismissal letter |
| Documents not started | Begin Particulars of Claim |

Checklist is stored as `cases.key_dates` and `cases.facts_encrypted`.
Checklist items are computed from missing fields, not from a static list.

---

## 3. Evidence completion loop

Show what evidence is missing and how it affects assessment quality:

> "Your case assessment is incomplete (grounding_score: 0.3).
> Upload your dismissal letter and appeal outcome to improve assessment accuracy."

- `grounding_score` from the assessment object drives the incompleteness indicator
- Missing evidence reduces grounding_score and confidence_score
- Adding evidence triggers a re-assessment and shows the delta

Implementation: re-run `pipeline.assess()` on evidence add; compare new vs prior assessment.

---

## 4. Case strength update

When user adds facts or evidence:
1. Re-run `pipeline.assess()` (BM25 retrieval + deterministic + model)
2. Compare `strength` and `has_viable_claim` vs prior run
3. Show: previous strength → updated strength, key changes, new weaknesses, updated next step

Example:
> "Case strength updated: Uncertain → Medium. Your dismissal letter shows no warning was given, supporting the procedural unfairness argument."

Store each assessment run in a `case_assessments` history table (see schema note below).

---

## 5. Document completion score

For paid document tiers:

| Document | Required fields |
|---|---|
| Particulars of Claim | EDT, service length, reason, procedure, weekly pay, EC certificate |
| Schedule of Loss | Weekly pay, notice period, benefits, future loss estimate |

Show completion %:
> "Particulars of Claim: 62% complete. Missing: ACAS certificate number, weekly pay, appeal outcome."

Completion is computed from which fields are present in `cases.facts_encrypted`.

---

## 6. Reminder triggers

| Trigger | Condition | Message |
|---|---|---|
| Deadline urgent | < 30 days | "You have X days. File your ET1 or start EC immediately." |
| EC not started | ec_status = not_started AND < 60 days | "Start ACAS Early Conciliation now to protect your deadline." |
| EC in progress | ec_status = in_progress | "Upload your EC certificate when received." |
| Evidence missing | grounding_score < 0.4 | "Add evidence to improve your assessment accuracy." |
| Document incomplete | completion < 80% | "Your Particulars of Claim is X% complete." |
| Handoff recommended | has_viable_claim uncertain AND complexity high | "Your case may benefit from a solicitor. See options." |

Reminders are stored as `reminder_events` (linked to `cases.id`), scheduled by the case dates.

---

## 7. Dashboard design

Every user dashboard always shows:

```
┌─────────────────────────────────────────────────────────┐
│ DEADLINE: 30 June 2026 — 29 days remaining ⚠ CRITICAL   │
├─────────────────────────────────────────────────────────┤
│ CASE STRENGTH: Medium   VIABLE: Uncertain               │
│ ACAS: Not started — start immediately                   │
├─────────────────────────────────────────────────────────┤
│ NEXT STEPS (3 outstanding)                              │
│ ☐ Upload dismissal letter                              │
│ ☐ Add weekly pay                                       │
│ ☐ Start ACAS Early Conciliation                        │
├─────────────────────────────────────────────────────────┤
│ DOCUMENT PROGRESS: 0%                                   │
│ Particulars of Claim — not started                      │
├─────────────────────────────────────────────────────────┤
│ KEY WEAKNESSES                                          │
│ • Employer did not follow ACAS Code                    │
│ • Reason: conduct (potentially fair)                   │
│ • No evidence of internal appeal submitted             │
└─────────────────────────────────────────────────────────┘
```

All outputs come from the governed structured assessment — no text is generated
outside the pipeline + governance gate.

---

## 8. What retention must NOT do

- No generic daily legal tips
- No random AI chat outside a specific case context
- No news updates or case law alerts without direct user relevance
- No gamification
- No outcome guarantees in any reminder or dashboard message
- No reminder text that constitutes legal advice (all text must come from governed assessment)

---

## Schema additions needed for Phase 3

**`cases` table additions:**
- `ec_status`: not_started | in_progress | certificate_received
- `ec_day_a`, `ec_day_b`: dates (already in key_dates JSONB — promote to columns)
- `assessment_history`: JSONB array of prior assessments (or separate table)
- `document_completion_pct`: JSONB `{particulars: 0.62, schedule: 0.0}`

**New table `reminder_events`:**
```sql
CREATE TABLE reminder_events (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         uuid REFERENCES cases(id) ON DELETE CASCADE,
    trigger_type    text NOT NULL,   -- deadline_urgent | ec_not_started | evidence_missing | etc.
    trigger_date    date,            -- when to fire
    fired_at        timestamptz,
    message_key     text NOT NULL,   -- key into message templates (not free text)
    created_at      timestamptz NOT NULL DEFAULT now()
);
```

Message templates are static strings with placeholders — never generatively produced.

---

*Planning document. No code built here. Phase 2C continues. Build Phase 3 dashboard after Phase 2 is fully closed.*
