# UK Employment Claim Co-Pilot — Project Documentation

**Project root (your machine):** `F:\lawapp`
**Docs location:** `F:\lawapp\docs\`
**Status:** Planning/spec complete for build. Hand phase by phase to a coding agent (Claude Code / similar).

---

## What this project is

A UK employment-law self-help platform. It gives a worker an honest diagnosis of whether they have a claim (starting with **unfair dismissal**), prepares **tribunal-ready documents** at a fraction of solicitor cost, tracks deadlines, and — when a case is beyond self-help — hands off to a real solicitor. The differentiator is **honesty** (telling people when they DON'T have a case) and **domain depth**, in a market where the former leader (DoNotPay) was discredited for overpromising.

**Legal model:** information + assessment + document drafting only — all *unreserved* activities under the Legal Services Act 2007. It NEVER conducts litigation, claims rights of audience, or implies it is a solicitor/law firm.

---

## Document set (read in this order)

| # | File | What it covers |
|---|---|---|
| 00 | `00_README.md` | This index |
| 01 | `01_BUILD_PLAN.md` | The 6 phases, tasks, guardrails, acceptance criteria. **Start here.** |
| 01a | `01a_PHASE1_API_APPENDIX.md` | Concrete API detail for Phase 1 ingestion (legislation.gov.uk, Find Case Law, ACAS) |
| 02 | `02_HLD_ARCHITECTURE.md` | High-level design — the 5 layers + data flow |
| 03 | `03_DATABASE_DESIGN.md` | PostgreSQL + pgvector schemas (legislation, case_law, acas, rules, cases, etc.) |
| 03a | `03a_UNFAIR_DISMISSAL_SEED_SPEC.md` | Unfair dismissal `rules` seed spec — which sections to fetch, all rule rows with effective dates across ERA 2025 transition, deadline arithmetic, live-verification checklist |
| 04 | `04_RAG_REASONING_SPEC.md` | The "algorithm brain" — RAG pipeline, structured-assessment schema, scoring, governance, de-identification |
| 05 | `05_WASM_SPEC.md` | What runs client-side in WASM and why (deadline calc, doc preview, validation) |
| 06 | `06_USER_STORIES.md` | User stories + acceptance criteria, mapped to phases and architecture |

---

## The 6 phases at a glance (full detail in `01_BUILD_PLAN.md`)

1. **Foundations & Data Spine** — repo, DB (pgvector), ingestion pipelines (the moat). Detailed APIs in `01a`.
2. **Retrieval + Reasoning Core** — the brain: hybrid RAG → structured assessment, scoring, governance. Spec in `04`.
3. **MVP Product** — the 4 core features: diagnosis (free), deadline tracker, document generation (paid), honest handoff.
4. **Depth** — document upload + extraction, full tribunal bundle, case timeline tracking.
5. **Validate, Harden, 2nd claim type** — prove willingness-to-pay, accuracy regression suite, GDPR/DPIA, add discrimination or unpaid-wages.
6. **Revenue & Scale** — solicitor referral integration, B2B/white-label, paid acquisition, further domains.

---

## Where the key concepts you asked about live

- **All phases** → `01_BUILD_PLAN.md` (6 phases, with per-phase acceptance criteria)
- **Databases** → `03_DATABASE_DESIGN.md` (full schemas) + `02_HLD` Layer 5
- **RAG** → `04_RAG_REASONING_SPEC.md` (hybrid retrieval, §3) + `02_HLD` Layer 4
- **The algorithm / reasoning brain** → `04_RAG_REASONING_SPEC.md` (tiered reasoning §4, scoring §5, governance §6)
- **WASM** → `05_WASM_SPEC.md` + `02_HLD` Layer 1
- **AI agents / orchestration** → `02_HLD_ARCHITECTURE.md` Layer 2
- **Legal data sources / APIs** → `01a_PHASE1_API_APPENDIX.md`

---

## Non-negotiable guardrails (apply across all docs)

1. **Legal boundary:** information/assessment/drafting only. No conducting litigation, no rights of audience, no implying solicitor status.
2. **Grounding always:** legal answers come from retrieved, cited sources — never model memory.
3. **Determinism for exact facts:** deadlines, caps, thresholds from the `rules` table — never generated.
4. **Honesty gate:** insufficient grounding/confidence → flag uncertainty / route to human, never fabricate.
5. **Data protection:** special-category data (Art.9) — encrypt, minimise, de-identify before any third-party model.
6. **Depth before breadth:** one claim type (unfair dismissal) end-to-end first; expand only after it's proven.

---

## Open items to verify with live calls before/while building (do not assume)
1. Find Case Law computational-analysis application — submit first; wait for grant before bulk crawl.
2. Current legislation.gov.uk fair-use / rate specifics.
3. Whether ACAS has any machine-readable feed (default: treat as static docs); current ACAS Code edition.
4. Whether the chosen workhorse model is good enough for legal reasoning (test early; if not, shift to stronger tier and revisit cost model).
5. Exact Act chapter numbers, the first-tier ET court code, and all `rules` values/caps — pull and verify from the live API, never hardcode from memory.
6. Real solicitor referral-fee rates and the rules governing them (needed before Phase 6).

---

## How the agent should work (summary — full version in `01_BUILD_PLAN.md`)
- Vertical slices, not horizontal layers. One claim type end-to-end first.
- Test legal CORRECTNESS, not just code. Maintain the fact-pattern regression set from Phase 2.
- Concentrate effort on retrieval + document generation — they ARE the value.
- Stop at phase boundaries; report against acceptance criteria before continuing.
- Flag, don't guess, when a data source/schema differs from these docs.
