# User Stories & Acceptance Criteria

**Pairs with:** `01_BUILD_PLAN.md` (maps stories to phases), `02_HLD_ARCHITECTURE.md`.
**Form:** "As a [person], I want [need], so that [outcome]." Each story lists acceptance criteria (AC). Stories are grouped by the phase that delivers them.

---

## Phase 3  -  MVP core stories (must be genuinely excellent before anything else)

### US-1 Diagnosis
*As someone who's just been dismissed, I want to find out whether what happened was unlawful, so that I know if I have a case worth pursuing.*
- AC1: User completes a guided, plain-English intake without legal jargon.
- AC2: System returns a structured assessment: viability, rough value range, deadline, weaknesses.
- AC3: For an out-of-scope matter, system says "not supported", does not guess.
- AC4: Every legal point in the result traces to a citation (grounding).

### US-2 Honest truth (the differentiator)
*As a worried person, I want to be told plainly if my case is weak, so that I don't chase something hopeless or get false hope.*
- AC1: Weak/no-claim outcomes are stated plainly, not softened into false encouragement.
- AC2: `key_weaknesses` are shown for any non-trivial case.
- AC3: When confidence/grounding is insufficient, the system says so and routes to human help rather than fabricating.
- AC4: No "win your case"/guarantee language anywhere.

### US-3 Deadline awareness
*As someone who doesn't know the rules, I want to be warned clearly about my time limit, so that I don't lose my right to claim.*
- AC1: Limitation date computed from the `rules` table values (deterministic), shown prominently.
- AC2: ACAS Early Conciliation window reflected.
- AC3: Deadline recalculates live as the user edits dates (WASM).
- AC4: Reminders/alerts as the date approaches.

### US-4 Affordable documents (paid value)
*As someone who can't afford a solicitor, I want proper tribunal documents prepared with my real facts, so that I can pursue my claim without paying thousands.*
- AC1: After payment, user can download a correct, well-structured Particulars of Claim and Schedule of Loss for unfair dismissal.
- AC2: Documents are populated with the user's actual facts.
- AC3: Documents marked as user-owned self-help drafts, not legal advice.
- AC4: Pricing anchored against solicitor cost, shown clearly before payment.

### US-5 Honest handoff (safety net)
*As someone whose case is serious/complex, I want to be told when I need a real solicitor and connected to one, so that I don't damage my own case.*
- AC1: "Beyond self-help" cases trigger the handoff path.
- AC2: Handoff is free to the user.
- AC3: (Phase 6) lead packaged and routed to a partner firm with tracking.

### US-6 Plain understanding
*As a non-lawyer, I want everything in plain English, so that I understand my situation and feel in control.*
- AC1: No unexplained legal jargon in any user-facing text.
- AC2: Explanations can draw on Explanatory Notes where helpful.

### US-7 Trust
*As someone burned by overpromising apps before, I want to trust this tool is honest, so that I'll rely on it for something important.*
- AC1: "Not a law firm / not legal advice" notice on every relevant surface.
- AC2: The honesty behaviours (US-2) are visibly consistent.
- AC3: Sources/citations are visible so the user can verify.

---

## Phase 4  -  Depth stories

### US-8 Upload instead of retype
*As a stressed user, I want to photograph/upload my dismissal letter and contract, so that I don't have to retype everything.*
- AC1: User uploads PDF/image; OCR + extraction pulls key facts.
- AC2: Extracted facts shown for user confirmation before use (never silently trusted).
- AC3: Uploads encrypted; never sent raw to third-party models.

### US-9 Full bundle
*As someone going to a hearing, I want the complete tribunal-ready document set, so that I'm properly prepared.*
- AC1: Premium tier generates witness-statement structure, chronology, evidence checklist, ET1 support.
- AC2: Output coherent and correctly structured for unfair dismissal.

### US-10 Track my dispute
*As someone in an ongoing dispute, I want the timeline and next steps tracked, so that I don't miss a step.*
- AC1: System holds the dispute sequence and surfaces next actions/dates.
- AC2: Notifications advance correctly through the timeline.

---

## Phase 5  -  Validation & second claim type

### US-11 (internal) Prove willingness to pay
*As the business, I want to know if free-diagnosis users convert to paid prep, so that I know the model works.*
- AC1: Funnel instrumented (diagnosis-start → complete → pay); conversion figure available.

### US-12 (internal) Accuracy I can trust
*As the business, I want a regression suite of known-correct fact patterns, so that changes can't silently degrade legal accuracy.*
- AC1: Test set with expected outcomes; accuracy measured; CI gate on regressions.

### US-13 Second claim type
*As a user with a discrimination/unpaid-wages issue, I want the same quality of help, so that the tool covers more of my problem.*
- AC1: New claim type added via rulebook + templates + test set, reusing the engine.
- AC2: New type passes the same accuracy bar before launch.

---

## Phase 6  -  Revenue & scale

### US-14 Solicitor partner receives leads
*As a partner firm, I want qualified, pre-prepared leads, so that I gain clients efficiently.*
- AC1: Handoff packages the assessment + documents as a lead.
- AC2: Referral status + fee tracked; arrangement structured within referral rules.
- AC3: Referral incentives never distort the honest assessment (hard rule).

### US-15 Union/employer white-label
*As a union/employer, I want a branded member tool, so that I add value and reduce escalations.*
- AC1: Brandable instance deployable with admin + reporting.

---

## Story → Phase → Architecture mapping (sanity check)
| Story | Phase | Architecture it exercises |
|---|---|---|
| US-1 Diagnosis | 3 | Retrieval + Reasoning + Governance |
| US-2 Honesty | 3 | Governance gate + scoring |
| US-3 Deadline | 3 | `rules` table + WASM |
| US-4 Documents | 3 | Generation + payment |
| US-5 Handoff | 3/6 | Governance route + referrals |
| US-8 Upload | 4 | OCR/extraction + encryption |
| US-13 2nd type | 5 | Engine reuse + new rulebook |
| US-14 Referral | 6 | Referrals + lead packaging |

If any architecture component maps to no story, question it. If any story maps to no component, there's a gap.
