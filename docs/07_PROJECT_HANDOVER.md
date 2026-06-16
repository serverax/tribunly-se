> **STALE  -  HISTORICAL ONLY (banner added 2026-06-10).** This document predates the current release state. The active source of truth is [docs/GO_LIVE_HANDOFF_2026-06-10.md](../docs/GO_LIVE_HANDOFF_2026-06-10.md) and branch `release/lawapp-clean-snapshot`. Do not use this file for release decisions.

# PROJECT HANDOVER - UK Employment Claim Co-Pilot

**What this is:** the single document to open a fresh conversation or a new Claude Code session with. It carries full context so nobody re-derives decisions already made. Read this top to bottom, then the spec docs it points to (00 to 08, in order).

**Project root (local):** `F:\lawapp`  |  **Docs:** `F:\lawapp\docs\`  |  **Repo:** `https://github.com/serverax/lawapp`

**Note on paths:** The original planning archive lives at `E:\lawapp\docs\` (read-only). The active implementation is at `F:\lawapp`. Always use `F:\lawapp`. Do not write to `E:\lawapp`. Do not touch `F:\SakinaAL` - that is a separate unrelated project on the same drive.

**Owner context:** already runs a related legal-AI platform (IterLaw) on Postgres/Railway with tiered cloud models. Reuse that thinking. This product is a lighter, mass-market front end on the same kind of engine.

**Status in one line:** Phase 1 (data spine and ingestion) is complete and committed; Phase 2 engine (classify, retrieve, reason, govern, de-id) is coded and partially verified; the unfair-dismissal rules seed spec (08) is written and approved as a fetch plan; the Section 7 verification checklist is in progress against the live API.

---

## 1. What the product is (one paragraph)

A UK employment-law self-help web platform. It gives a worker an honest diagnosis of whether they have a claim (starting with **unfair dismissal only**), prepares **tribunal-ready documents** at a fraction of solicitor cost, tracks the **limitation deadline**, and hands off to a **real solicitor** when a case is beyond self-help. The wedge is **honesty plus domain depth** in a market where the former leader (DoNotPay) was discredited and fined for overpromising. Primary revenue is **solicitor referral fees plus B2B/union licensing**; paid document tiers are the proof-of-demand layer, not the end game.

---

## 2. Why this wins (positioning, settled)

- The space is **forming, not empty**. Real competitors exist: Yerty and Valla in employment; Remedy, RentFix, Lando, SpotIt in tenancy. This is a **win-by-depth-and-trust-in-one-niche** play, not blue ocean. Do not pitch it as novel.
- **Founder-fit is the moat.** Chosen because it fits the owner's deep employment-tribunal expertise. That depth, plus a curated cited data spine, is what competitors cannot cheaply copy.
- **Honesty is the product, not a feature.** The differentiator is telling people plainly when they do *not* have a case. That is the opposite of the DoNotPay failure mode and the reason a referral-fee model stays clean.
- **Narrowed deliberately:** employment first, unfair dismissal first. Consumer-disputes was rejected (price floor around £2.99, commoditised). Breadth comes only after the niche is won.
- **Legal model settled:** information, assessment, and document drafting are **unreserved** activities under the Legal Services Act 2007 - legal without SRA authorisation. The forbidden zone, which must never be crossed: conducting litigation, rights of audience, or implying solicitor/law-firm status.

---

## 3. The six non-negotiable guardrails (carry into every session)

These bind everything. Treat each as a hard constraint, not a preference.

1. **Legal boundary.** Information, assessment, and drafting only. No conducting litigation, no rights of audience, no implying it is a solicitor or law firm. A clear "not a law firm / not legal advice" notice sits on every relevant surface.
2. **Grounding always.** Legal answers come from retrieved, cited, current sources - never from a model's unaided memory.
3. **Determinism for exact facts.** Deadlines, caps, and thresholds come from the structured `rules` table by code - never generated or recalled by a model.
4. **Honesty gate.** Insufficient grounding or confidence means flag the uncertainty and route to a human. Never fabricate, never overstate strength or value, never use "win your case" language.
5. **Data protection.** Special-category data (discrimination, health, UK GDPR Article 9) is encrypted at rest and in transit, minimised, and de-identified before any third-party model call.
6. **Depth before breadth.** One claim type (unfair dismissal) working end to end and genuinely excellent before any expansion.

---

## 4. The architecture (five layers, settled)

Data flows top to bottom on the way in, bottom to top on the way out. The retrieval and data layers are the moat. The governance gate is the honesty proposition turned into code.

| Layer | Role | Hard rule |
|---|---|---|
| 1 - Client (responsive web, web-first) | Guided intake, diagnosis view, payment, document view. **WASM** for deadline calc, doc assembly/preview, validation. | Notices on every relevant surface. Sensitive compute stays client-side where feasible. |
| 2 - Orchestration (agents) | Coordinates the pipeline: classify -> retrieve -> reason -> generate -> govern -> respond. | Orchestrate and draft only. Never decide law, never take a reserved action. |
| 3 - Reasoning (tiered) | Applies retrieved law to facts. Workhorse model for bulk; stronger escalation model only when confidence is low **and** grounding is solid. | Escalation receives de-identified context only. Output is a structured object, not prose. |
| 4 - Retrieval (hybrid RAG) | Always runs first. Semantic (pgvector) plus structured (SQL on `rules`). Returns a cited bundle. | Reasoning answers from this bundle, never from model memory. |
| 5 - Data spine (Postgres + pgvector) | `legislation`, `case_law`, `acas_guidance`, `rules`, plus `users`, `cases`, `documents`, `referrals`. Ingestion plus change-detection keep it current. | Every legal row carries source_url, version/effective dates, last_verified_at. |

**Deliberately not in the architecture:** anything that files or represents on a user's behalf; a general "ask me anything about law" free-chat (the DoNotPay trap); any path sending raw personal data to a third-party model; any outcome-guarantee logic.

---

## 5. The reasoning brain (the pipeline, settled)

Per request: `classify -> retrieve (always) -> reason -> score -> govern -> respond (+ generate on paid path)`.

- **Classify:** matter type (unfair dismissal only for now) plus intent (diagnosis / document / deadline check). Out-of-scope returns "not supported", never a guess.
- **Retrieve (always first):** structured SQL on `rules` for exact facts, plus pgvector top-k over legislation, case law, and ACAS guidance. Empty or weak bundle sets `insufficient_grounding = true` and stops generative guessing.
- **Reason:** workhorse tier by default; escalate only on low confidence with solid grounding, sending de-identified context only. Output is the canonical **structured assessment object** (claim_type, has_viable_claim, strength, value_range, key_weaknesses, deadline, recommended_next_step, citations, grounding_score, confidence_score, insufficient_grounding). Full schema in `04_RAG_REASONING_SPEC.md`.
- **Score:** grounding score (every legal claim traces to a citation) plus confidence score.
- **Govern (the honesty layer in code):** checks grounding, confidence, determinism of exact facts, the legal boundary, and that weaknesses are stated plainly. Only a passing assessment reaches display or generation.
- **De-identify before any third-party call:** strip names, employer, addresses, DOB, contact details, case-identifying specifics; send the abstracted question plus retrieved authority; re-attach identity locally.

---

## 6. The data model (condensed)

Postgres 15+ with `pgvector` and `pgcrypto`. UUID primary keys, `timestamptz` defaults, `vector(N)` embeddings sized to the chosen model.

- **Legal source tables (the moat):** `legislation` (CLML XML, chunked, point-in-time aware via version_date / effective_from / effective_to / is_prospective), `case_law_documents` + `case_law_chunks` (Akoma Ntoso XML, stable `document_uri`, `content_hash` for change detection), `acas_guidance` (static docs, track edition).
- **`rules` (the critical table):** deterministic legal facts keyed by `rule_key` + `claim_type` + `jurisdiction`, each row citing its authority and versioned by `effective_from`/`effective_to`. Caps and limits change (annual uprating), so never hardcode - read the correct figure for the relevant date from here.
- **Application tables:** `users`, `cases` (facts_encrypted as bytea, latest assessment as jsonb, key_dates, status, payment_tier), `documents` (generated outputs and uploads, extracted_facts needing user confirmation), `referrals` (Phase 6).
- **`source_freshness` view** backs the Phase 1 freshness report.
- **Article 9:** `cases.facts_encrypted` and `documents.storage_ref` hold special-category data - encrypt, minimise, define retention and deletion, never copy raw facts into logs or third-party payloads. DPIA before launch (Phase 5).

---

## 7. WASM scope (settled)

WASM does only what it is genuinely good at: fast, sandboxed, privacy-preserving client compute. **In scope:** deadline calculator (arithmetic only; rule *values* come from the server `rules` table), document assembly/preview, form validation, optional light parsing. **Out of scope:** LLM inference, RAG/retrieval, model generation, anything needing the legal database. The deadline module reads rule values passed in from the server so a legal change updates the `rules` table, not the WASM binary. Provide a non-WASM JS fallback.

---

## 8. The six phases (full detail in `01_BUILD_PLAN.md`)

1. **Foundations and Data Spine.** Repo skeleton, Postgres + pgvector, ingestion pipelines for legislation.gov.uk, Find Case Law, and ACAS, embedding/indexing, `rules` population, freshness report. **DONE - commit 23f6efa.**
2. **Retrieval + Reasoning Core.** Hybrid RAG -> structured assessment, deterministic deadline/value logic, grounding and confidence scoring, governance gate. **PARTIAL - commit 5768078. Semantic retrieval pending embeddings (OPENAI_API_KEY quota); model reasoning done with Haiku but semantic citations untested.**
3. **MVP Product.** Four features only: free diagnosis, deadline tracker, document generation (paid: Particulars of Claim + Schedule of Loss), honest handoff trigger plus capture form. Web client, manual fact entry, payment, basic accounts.
4. **Depth.** Document upload plus OCR/extraction (with user confirmation), full tribunal bundle tier, case timeline/escalation tracking, optional thin subscription.
5. **Validate, Harden, 2nd Claim Type.** Willingness-to-pay and conversion funnel, accuracy regression suite with CI gate, GDPR/Article 9 review and DPIA, add a second claim type (discrimination or unpaid wages) only after it passes the same accuracy bar.
6. **Revenue and Scale.** Live solicitor referral integration with fee tracking, B2B/white-label layer, infra scale review, paid acquisition (only once CAC vs value is known), further domains last.

Discipline across phases: vertical slices not horizontal layers; test legal correctness not just code; concentrate effort on retrieval and document generation; stop at each phase boundary and report against acceptance criteria; flag, do not guess, when a source or schema differs from the docs.

---

## 9. Current status (updated)

- **Phase 1:** PASS. Committed 23f6efa. Ingestion pipelines, DB schema, rules seed (14 rows, all verified against SI 2026/310), EAT sample (5 decisions), freshness report. Find Case Law bulk licence application pending (user action).
- **Phase 2:** PARTIAL. Commit 5768078. Classify, retrieve (rules leg real, semantic leg coded but embeddings unpopulated), deadline arithmetic, de-identification, governance gate, real Haiku model calls - all working. Semantic retrieval and citation-backed fact patterns blocked by OPENAI_API_KEY quota.
- **Seed spec (08):** Written at `F:\lawapp\docs\08_UNFAIR_DISMISSAL_SEED_SPEC.md`. Approved as a fetch plan. Section 7 verification checklist in progress against live APIs. No rules rows written yet from this spec - values remain VERIFY until live-fetched results are reviewed.
- **Docs location:** `F:\lawapp\docs\` (not E:\lawapp).

---

## 10. Immediate next actions (in order)

1. **Complete the Section 7 verification checklist** from `08_UNFAIR_DISMISSAL_SEED_SPEC.md`. Run all live API fetches, report pulled values with source URLs and fetch dates. Do not write any rules rows until the owner reviews the verified values.
2. **Resolve OPENAI_API_KEY quota** to unblock embeddings and semantic retrieval. Once resolved: run embedder, confirm non-zero embedding counts, re-run the two skipped Phase 2 tests.
3. **Submit the Find Case Law computational-analysis application.** Prep doc at `F:\lawapp\docs\FCL_APPLICATION_PREP.md`. Free, no charges. Longest-lead external dependency.
4. **Phase 3 (MVP product)** only after Phase 2 acceptance criteria are fully met (semantic retrieval returning real cited authority).

---

## 11. Open items to verify with live calls (never assume from memory)

1. Find Case Law computational-analysis application - turnaround and current terms. Submit first; wait for grant before any bulk crawl.
2. legislation.gov.uk current Fair Use / rate-limit specifics.
3. Whether ACAS has any machine-readable feed (default assumption: no, treat as static docs); the current ACAS Code edition.
4. Whether the chosen workhorse model is good enough for legal reasoning. Test early. If not, shift load to the stronger tier and revisit the cost model. **This is the main open technical risk.**
5. ERA 2025 commencement SIs for s.25 (qualifying period/cap) and s.152 (time limits) - not yet published as of last check. Monitor monthly.
6. Real solicitor referral-fee rates and the rules governing them - needed before Phase 6, worth exploring earlier.
7. What major UK unions already offer members - decides whether they are partner or competitor in GTM.
8. d-{uuid}/data.xml endpoint for Find Case Law post-Apr-2025 decisions - confirmed 404 in testing; flagged to FCL team for clarification before building change-detection refresh.

---

## 12. Key risks and how the plan already handles them

| Risk | Mitigation already in the design |
|---|---|
| Crossing the reserved-activity line | Hard legal boundary in guardrail 1; governance gate blocks reserved-action language; no filing/representing component exists in the architecture. |
| Wrong legal facts (the killer risk) | Determinism guardrail: exact values live in versioned `rules` rows with citations, verified against the live API, never generated. Accuracy regression suite from Phase 2 onward. |
| Overpromising (the DoNotPay trap) | Honesty gate surfaces weaknesses and routes to a human on weak grounding. No outcome-guarantee logic. Referral incentives must never distort the assessment (hard rule). |
| Special-category data leakage | De-identification boundary before any third-party model, proven by a logged boundary-payload test in Phase 2. Encryption at rest and in transit. DPIA in Phase 5. |
| Workhorse model not good enough | Open item 4 - test early; tiered design lets load shift to the stronger model, with the cost model revisited. |
| Stale legal data | Change-detection job (content-hash based) plus the freshness report; point-in-time URIs and effective-date columns. |
| ERA 2025 commencement slipping | Prospective rows in rules table marked is_prospective=true; documented promotion procedure in LEGAL_ACCURACY_PROCEDURES.md; deadline calc stays on 3-month rule until commencement SI confirmed. |

---

## 13. The document set (in `F:\lawapp\docs\`)

| # | File | Covers |
|---|---|---|
| 00 | `00_README.md` | Project index and "where each concept lives" |
| 01 | `01_BUILD_PLAN.md` | The 6 phases - tasks, guardrails, acceptance criteria. Start here. |
| 01a | `01a_PHASE1_API_APPENDIX.md` | Concrete API detail: legislation.gov.uk, Find Case Law, ACAS |
| 02 | `02_HLD_ARCHITECTURE.md` | The 5-layer high-level design and data flow |
| 03 | `03_DATABASE_DESIGN.md` | PostgreSQL + pgvector schemas |
| 03a | `03a_UNFAIR_DISMISSAL_SEED_SPEC.md` | Earlier seed spec draft (superseded by 08) |
| 04 | `04_RAG_REASONING_SPEC.md` | RAG pipeline, structured-assessment schema, scoring, governance, de-identification |
| 05 | `05_WASM_SPEC.md` | Client-side WASM scope |
| 06 | `06_USER_STORIES.md` | User stories and acceptance criteria mapped to phases |
| 07 | `07_PROJECT_HANDOVER.md` | This document (project root: F:\lawapp) |
| 08 | `08_UNFAIR_DISMISSAL_SEED_SPEC.md` | Unfair dismissal rules seed spec - fetch plan and deadline arithmetic |
| - | `FCL_APPLICATION_PREP.md` | Find Case Law application draft answers |
| - | `LEGAL_ACCURACY_PROCEDURES.md` | Commencement promotion procedure for ERA 2025 rows |

---

## 14. Working style the owner expects

Direct, sharp, practical, honest about uncertainty. No filler, no fake certainty. Hyphens not em-dashes. When stating legal facts, ground them or flag them as needing verification - never invent a section number, deadline, or cap. Flag, do not guess. Show evidence, do not assert.

---

**To start a new session:** open with this document from `F:\lawapp\docs\07_PROJECT_HANDOVER.md`. Confirm understanding of Section 3 (guardrails) and Section 9 (current status). Then proceed with Section 10 action 1 unless told otherwise. Always work from `F:\lawapp`.
