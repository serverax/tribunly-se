# UK Employment Claim Co-Pilot — Phased Build Plan

**Audience:** a coding agent (Claude Code, or similar) executing phase by phase, plus the human owner reviewing between phases.
**Format note for the agent:** Each phase is self-contained. Do not start a phase until the previous phase's Acceptance Criteria pass. At the end of each phase, stop and report status against the criteria before proceeding. Treat every "GUARDRAIL" line as a hard constraint, not a suggestion.

---

## 0. Read This First — Project Constraints (apply to every phase)

These are non-negotiable and bound everything the agent builds.

- **Domain scope:** UK employment law only (England & Wales primary; flag Scotland differences, do not silently assume them). One claim type first: **unfair dismissal**. Do not build other claim types until Phase 5.
- **Legal boundary (GUARDRAIL):** The system provides *information, assessment, and document drafting* only — all unreserved activities. It must NEVER conduct litigation, file on a user's behalf, claim rights of audience, or state or imply it is a solicitor or law firm. Every user-facing surface carries a clear "not a law firm / not legal advice" notice.
- **Honesty principle (GUARDRAIL):** The product's value is honest assessment. The system must surface case *weaknesses*, express uncertainty plainly, and route to a human/solicitor when grounding is insufficient. It must never fabricate authority or overstate the strength or value of a claim.
- **Grounding principle (GUARDRAIL):** Legal answers come from retrieved, cited, current sources — never from a model's unaided memory. Exact values (deadlines, caps, thresholds) come from deterministic data/logic, never from a generative model.
- **Data principle (GUARDRAIL):** This handles special-category data (discrimination, health). Personal/identifying case data must never be sent to a public/third-party LLM. De-identify at the boundary. Encrypt at rest and in transit.
- **Build discipline:** Thin vertical slice first. One claim type, end to end, genuinely good — before any breadth.

**Tech baseline assumptions (agent: confirm or flag at start):**
- Backend service exposing an API; thin web client (responsive, web-first).
- PostgreSQL as primary store, with `pgvector` for embeddings (avoids a separate vector DB at this stage).
- A controlled cloud "workhorse" model for classification/bulk reasoning; a stronger model for escalation and document generation. (Treat true on-device/local LLM as a later optimisation to test, NOT a foundation.)
- WASM used for client-side, privacy-sensitive computation only (deadline calc, document assembly/preview, validation) — NOT for running LLMs or core RAG.

---

## Phase 1 — Foundations & Data Spine

**Goal:** Stand up the project skeleton and the retrieval data spine. This is the moat; most effort lives here.

**Tasks:**
1. Initialise repo structure: `/backend` (orchestration + API), `/ingestion` (data pipelines), `/client` (web UI), `/shared` (types/schemas), `/docs`.
2. Provision PostgreSQL with `pgvector`. Define schemas for: `legislation`, `case_law`, `acas_guidance`, `rules` (deterministic legal facts: deadlines, caps, thresholds), each with `source_url`, `version`, `last_verified_at`, `effective_from`, `effective_to`.
3. Build ingestion pipeline for **legislation.gov.uk** (RESTful, XML/CLML, Open Government Licence; append `data.xml` to any page for raw data). Ingest, at minimum: Employment Rights Act 1996, Equality Act 2010, and the Renters'/employment reforms in force 2025/26. Respect the site's Fair Use Policy — throttle, no aggressive crawling.
4. Submit the **Find Case Law** (National Archives) free "computational analysis" application for bulk access (no charge; needed for bulk extraction). In parallel, build the ingestion for Employment Tribunal + Employment Appeal Tribunal decisions (XML / LegalDocML, Open Justice Licence). Note coverage limits: EAT digital records ~2021 onward; archive is incomplete.
5. Ingest **ACAS Code of Practice on Disciplinary and Grievance Procedures** and key guidance as static authoritative documents (no clean public API — treat as ingested reference content; verify no feed exists at build time).
6. Build the embedding + indexing job (chunk → embed → store in pgvector) plus structured-table population for the deterministic `rules` data.
7. Implement a "source freshness" report: list every source with `last_verified_at` and flag anything stale.

**GUARDRAILS:** Deterministic legal facts (time limits, compensation caps) go in structured `rules` tables with citations — never embedded as free text only. Store XML parsing as a maintainable module; CLML and LegalDocML are specialist schemas and need real parsing.

**Acceptance Criteria:**
- Querying the DB returns the correct, cited statute text for unfair dismissal (ERA 1996 relevant sections).
- The `rules` table returns the correct unfair-dismissal time limit and current compensation cap, each with a source citation and effective date.
- Find Case Law application submitted; at least a sample of EAT/ET decisions ingested and retrievable.
- Freshness report runs and lists all sources with verification dates.

---

## Phase 2 — Retrieval + Reasoning Core (the "brain")

**Goal:** Given a user query + facts, retrieve the right authority and produce a *structured, grounded* assessment. No UI polish yet; this is the engine.

**Tasks:**
1. **Intake/classification module:** classify an incoming query into (a) matter type — restrict to unfair dismissal for now, route others to "not yet supported" — and (b) intent (diagnosis / document / deadline check). Use rules for obvious cases, small model otherwise.
2. **Hybrid retrieval module:** vector search (pgvector) for semantic matches + structured lookups for deterministic facts. Always runs. Returns a bundle of cited sources.
3. **Reasoning module (tiered):**
   - Workhorse model applies retrieved law to user facts, outputs a **structured assessment object** (not prose): `{claim_type, has_viable_claim (bool/uncertain), strength (low/med/high), value_range, key_weaknesses[], deadline, recommended_next_step, citations[]}`.
   - Escalation: only when workhorse confidence is low AND grounding is solid. Send only **de-identified, abstracted** context to any stronger/third-party model.
4. **Deterministic deadline + value logic:** compute the limitation date (3 months less 1 day, plus ACAS Early Conciliation rules) and value ranges from structured rules in code — NOT from the LLM.
5. **Confidence + grounding scoring:** every assessment carries a grounding score (is each claim backed by a retrieved citation?) and a confidence score.

**GUARDRAILS:** If retrieval returns no adequate authority, the reasoning module must NOT fall through to ungrounded generation. It returns `insufficient_grounding` → triggers honest-uncertainty / human-route handling. Deadlines and caps are computed deterministically; the model never "remembers" them.

**Acceptance Criteria:**
- For 5+ realistic unfair-dismissal fact patterns, the engine returns a structured assessment with correct claim identification, a correctly computed deadline, and citations that actually support each stated point.
- For an out-of-scope query (e.g. a tenancy question), it correctly returns "not supported," not a guess.
- For a deliberately thin/ambiguous fact pattern, it returns `insufficient_grounding` and recommends human help rather than fabricating an answer.
- No personal data appears in any payload sent to a third-party model (verify by logging boundary payloads in a test).

---

## Phase 3 — MVP Product (the four core features)

**Goal:** Wrap the engine in the minimum product that delivers the UVP and the first revenue. These four features ARE the product.

**Features (build all four, nothing else):**
1. **Free Diagnosis:** guided plain-English intake → structured assessment shown to the user (claim viability, rough value, deadline, honest weaknesses). The hook and qualifier.
2. **Deadline Tracker:** captures key dates, surfaces the limitation date and ACAS clock, sends reminders. (Deadline maths can run client-side via WASM for privacy/speed.)
3. **Document Generation (PAID):** template-anchored generation of **Particulars of Claim** + **Schedule of Loss**, populated from the structured assessment + user facts. Templates carry the legal structure; the model fills/adapts. This is the paid moment.
4. **Honest Handoff / Referral Trigger:** logic that flags "beyond self-help" cases and routes to a (future) partner solicitor. For MVP, implement the trigger + a capture form; the live partner integration comes in Phase 6.

**Supporting build:**
- Web client: trust-first homepage, one-click-to-diagnosis, visible deadline urgency, clear "not a law firm" notice, founder/honesty story.
- Manual fact entry is fine for MVP (document upload comes in Phase 4).
- Payment integration for the paid document tier.
- Basic accounts (save a case, return to it).

**GUARDRAILS:** Generated documents must be clearly marked as user-owned drafts produced by a self-help tool, not legal advice. No "win your case" or outcome-guarantee language anywhere. The handoff must be free to the user.

**Acceptance Criteria:**
- A user can go: land → free diagnosis → see honest assessment + deadline → pay → download a correct, well-structured Particulars of Claim and Schedule of Loss for an unfair-dismissal case.
- The deadline tracker correctly warns as a limitation date approaches.
- A "beyond self-help" case triggers the handoff path and captures the lead.
- All legal-boundary notices present on every relevant surface.

---

## Phase 4 — Depth: Document Upload & Premium Tier

**Goal:** Raise output quality and revenue per user, now that the model is proven.

**Tasks:**
1. **Document upload + extraction:** user uploads dismissal letter, contract, email chain (PDF/image). OCR + extraction pulls facts (dates, parties, clauses) into the case. Major quality leap — makes output *theirs*, not generic.
2. **Full Tribunal Bundle (higher-priced tier):** add witness-statement structure, chronology, evidence checklist, ET1 support. The £149–199 tier.
3. **Case timeline / escalation tracking:** holds the dispute sequence ("they have 14 days," "escalate on X"). Drives retention.
4. Optional thin **subscription** (storage, "ask about any letter") — baseline retention only, not the focus.

**GUARDRAILS:** Uploaded documents are special-category data — encrypt, minimise, never route raw to third-party models. Extraction errors must be surfaced for user confirmation, never silently trusted.

**Acceptance Criteria:**
- A user can upload a real dismissal letter and see correctly extracted facts pre-filling their case (with a confirmation step).
- The premium bundle generates a coherent, correctly structured full set of tribunal documents.
- Timeline tracking advances and notifies correctly through a simulated dispute.

---

## Phase 5 — Validate, Harden, and Add the Second Claim Type

**Goal:** Prove the model with real users; harden; only then widen.

**Tasks:**
1. **Willingness-to-pay + conversion validation:** instrument the funnel (diagnosis-start → diagnosis-complete → pay). The key metric: do free-diagnosis users convert to paid prep, and do they recommend it?
2. **Accuracy QA loop:** assemble a test set of real anonymised fact patterns with known-correct outcomes; measure assessment accuracy and document quality; fix retrieval/reasoning gaps. Build a regression suite so future changes can't silently degrade legal accuracy.
3. **Security/compliance hardening:** UK GDPR Article 9 review, data-retention policy, encryption audit, de-identification boundary test, DPIA.
4. **Add the second claim type** (e.g. discrimination OR unpaid wages) by adding its rulebook + templates + test set — reusing the same engine. Proves the architecture generalises.

**GUARDRAILS:** Do not expand to a new claim type until its accuracy passes the same QA bar as unfair dismissal. Breadth only after depth is proven.

**Acceptance Criteria:**
- Funnel metrics captured; a clear conversion-rate figure exists.
- Accuracy regression suite passes for unfair dismissal; new claim type passes the same bar before launch.
- Security/compliance checklist complete and documented.

---

## Phase 6 — Revenue Engines & Scale (Partnerships + B2B)

**Goal:** Turn on the high-value revenue streams the consumer funnel was built to feed.

**Tasks:**
1. **Solicitor referral integration:** live partner firm(s) receiving qualified, pre-prepared leads from the handoff trigger. Implement lead packaging (the structured assessment + documents) and the referral-fee tracking. (Confirm referral-fee rules and rates with a real firm + proper regulatory advice before going live.)
2. **B2B / white-label layer:** brandable instance for unions, employers, insurers; admin + reporting; licensing controls.
3. **Scale infra:** review pgvector performance at volume; consider dedicated vector DB only if needed; cost-monitor the model tiers (workhorse vs escalation spend).
4. **Paid acquisition (only now):** with known cost-per-acquisition vs user value, buy growth profitably.
5. **Further domain expansion** (tenancy, consumer) reusing the engine — last, after employment is won.

**GUARDRAILS:** Referral arrangements must be structured within referral-fee rules from day one. The free NHS-style honesty layer / honest assessment must never be distorted by referral incentives — protect the free tier's integrity as a hard rule.

**Acceptance Criteria:**
- At least one live solicitor partner receiving and accepting real qualified leads, with referral-fee tracking working.
- One B2B/white-label instance deployable and demonstrable.
- Cost-per-case (model spend) and cost-per-acquisition known and within target vs revenue per user.

---

## Cross-Phase: How the Agent Should Work

- **Vertical slices, not horizontal layers.** Prefer "one claim type working end to end" over "all retrieval done, no reasoning yet."
- **Test the legal correctness, not just the code.** A passing unit test that produces wrong law is a failure. Maintain the fact-pattern regression set from Phase 2 onward.
- **Concentrate effort on retrieval + document generation** — these two ARE the value. Everything else is supporting cast.
- **Stop at phase boundaries** and report against Acceptance Criteria before continuing.
- **Flag, don't guess.** If a data source, rate limit, or schema differs from this plan's assumptions, stop and report rather than improvising around a legal data source.

## Open Items to Confirm Before / During Phase 1 (do not silently assume)

1. Find Case Law computational-analysis application turnaround and current terms.
2. Current legislation.gov.uk rate limits / Fair Use specifics.
3. Whether ACAS has any machine-readable feed (default: treat as static documents).
4. Whether the chosen "workhorse" model gives acceptable legal-reasoning quality (test early; if not, shift load to the stronger tier and revisit cost model).
5. Real solicitor referral-fee rates and the rules governing them (needed before Phase 6, ideally explored earlier).
