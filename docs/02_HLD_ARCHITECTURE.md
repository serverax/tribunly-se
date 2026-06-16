# High-Level Design (HLD)  -  UK Employment Claim Co-Pilot

**Pairs with:** `01_BUILD_PLAN.md`, `03_DATABASE_DESIGN.md`, `04_RAG_REASONING_SPEC.md`, `05_WASM_SPEC.md`.
**Read `00_README.md` and the build plan's Section 0 (constraints/guardrails) first.**

---

## 1. System overview

A five-layer system. Data flows top→bottom on the way in, bottom→top on the way out. The retrieval + data layers are the moat; the governance gate is the honesty proposition made into architecture.

```
┌───────────────────────────────────────────────────────────────┐
│ LAYER 1  CLIENT (web, responsive)                                │
│  intake UI · diagnosis view · payment · document view            │
│  WASM: deadline calc · doc assembly/preview · validation         │
└───────────────▲───────────────────────────────┬─────────────────┘
                │ responses (grounded, cited)    │ requests (API)
┌───────────────┴───────────────────────────────▼─────────────────┐
│ LAYER 2  ORCHESTRATION (AI agents)                               │
│  classify → retrieve → reason → generate → govern → respond      │
│  GUARDRAIL: orchestrate + draft only; never decide law / file    │
└───────────────▲───────────────────────────────┬─────────────────┘
                │ structured assessment          │ task calls
┌───────────────┴───────────────────────────────▼─────────────────┐
│ LAYER 3  REASONING (tiered)                                      │
│  workhorse model (bulk) → escalation model (low-confidence only, │
│  de-identified). Output = STRUCTURED ASSESSMENT object, not prose│
└───────────────▲───────────────────────────────┬─────────────────┘
                │ cited sources                  │ retrieval query
┌───────────────┴───────────────────────────────▼─────────────────┐
│ LAYER 4  RETRIEVAL (RAG, hybrid)   -  always runs first            │
│  vector search (pgvector) + structured lookups (exact facts)     │
└───────────────▲───────────────────────────────┬─────────────────┘
                │                                │
┌───────────────┴───────────────────────────────▼─────────────────┐
│ LAYER 5  DATA SPINE (PostgreSQL + pgvector)                      │
│  legislation · case_law · acas_guidance · rules(deterministic)   │
│  + cases · users. Ingestion + change-detection keep it current.  │
└───────────────────────────────────────────────────────────────────┘
        ▲ ingestion: legislation.gov.uk · Find Case Law · ACAS
```

## 2. The layers in detail

### Layer 1  -  Client
Responsive web app (web-first; people research claims at a laptop but arrive on mobile). Responsibilities: guided intake, rendering the diagnosis, payment, document display/download, the "not a law firm / not legal advice" notices on every relevant surface. **WASM** runs privacy-sensitive, latency-sensitive computation in-browser (see `05_WASM_SPEC.md`): deadline maths, document assembly/preview, form validation  -  so sensitive data can be handled without a server round-trip. Talks to the backend via one HTTP API.

### Layer 2  -  Orchestration (agents)
Coordinates the pipeline per request: **classify → retrieve → reason → generate → govern → respond.** Agents call tools (retrieval, generation, deadline calc, lead-routing) and manage state. **GUARDRAIL:** agents orchestrate the *workflow* and produce *drafts*; they never make the final legal judgment and never take a reserved action (filing, representing). Start as modules in one service; split into services only if scale demands.

### Layer 3  -  Reasoning (tiered "brain")
Applies retrieved law to the user's facts. Tiered for cost + safety:
- **Workhorse tier** (cheap, controlled): classification + the bulk of reasoning.
- **Escalation tier** (stronger model): only when workhorse confidence is low AND grounding is solid; receives **de-identified, abstracted** context only.
Output is a **structured assessment object** (claim type, viability, strength, value range, weaknesses, deadline, next step, citations)  -  validated before display. Full schema in `04_RAG_REASONING_SPEC.md`.
> Note: a genuinely on-device/"local" LLM for legal reasoning is treated as a later optimisation to test, not a foundation. The workhorse is a controlled cloud model until proven otherwise.

### Layer 4  -  Retrieval (RAG, hybrid)  -  the moat
**Always runs first.** Two retrieval modes:
- **Semantic** (pgvector): finds relevant legislation sections, tribunal/EAT decisions, ACAS guidance by meaning.
- **Structured** (SQL on `rules`): returns exact, deterministic facts  -  time limits, compensation caps, thresholds  -  which must never be fuzzy.
Returns a bundle of **cited, current** sources. The reasoning layer answers *from this*, never from model memory. Detail in `04_RAG_REASONING_SPEC.md`.

### Layer 5  -  Data spine
PostgreSQL + pgvector. Tables: `legislation`, `case_law`, `acas_guidance`, `rules` (deterministic legal facts), plus `users`, `cases`, `documents`. Every legal record carries `source_url`, `version`/effective dates, `last_verified_at`. Ingestion pipelines (Phase 1) populate it; a change-detection job (content-hash based) keeps it current cheaply. Schemas in `03_DATABASE_DESIGN.md`.

## 3. Core data flow (request lifecycle)

1. **User submits** query + facts (client).
2. **Orchestrator classifies**: matter type (unfair dismissal only, for now) + intent (diagnosis / document / deadline).
3. **Retrieval always runs**: hybrid pull of cited authority + exact rules.
4. **Reasoning** applies law to facts → structured assessment with confidence + grounding scores.
5. **Governance gate**: is every claim backed by a citation? is confidence sufficient? does anything cross the reserved-activity line?
   - Pass → continue.
   - Insufficient grounding/confidence → **do not guess**; flag uncertainty honestly and/or route to human/solicitor.
6. **Generation** (paid path only): template-anchored documents from the assessment + facts.
7. **Response** to client; WASM renders deadline + document preview locally.
8. **Beyond self-help** → honest handoff: package the assessment as a qualified lead to a partner solicitor (Phase 6).

## 4. Cross-cutting principles (apply everywhere)

- **Grounding always**: legal output comes from retrieved, cited sources  -  never model memory.
- **Determinism for exact facts**: deadlines, caps, thresholds from `rules` tables/code  -  never generated.
- **Generation only for genuine interpretation**: the "does this fact pattern meet this legal test" judgment, constrained by retrieved authority.
- **Inverse data-exposure rule**: the more a request leans on a general/third-party model, the more it must be de-identified and constrained.
- **Honesty gate**: insufficient grounding → flag/route, never fabricate. This is the UVP in code.
- **Legal boundary**: information + assessment + drafting only. No conducting litigation, no rights of audience, no implying it is a solicitor/law firm.
- **Special-category data**: discrimination/health facts → encrypt at rest + transit, minimise, de-identify at the third-party boundary (UK GDPR Article 9).

## 5. Technology summary

| Concern | Choice | Why |
|---|---|---|
| Client | Responsive web, web-first | Disputes are document-heavy; laptop-primary, mobile-capable |
| Client-side compute | WASM | Fast + privacy-preserving for deadline/doc/validation |
| Backend | One orchestration service exposing an API (split later) | Avoid premature microservices |
| Agents | Orchestration framework, on rails | Coordinate workflow; never decide law / file |
| Reasoning | Tiered: controlled workhorse + stronger escalation | Cost + safety; de-identify on escalation |
| Retrieval | Hybrid: pgvector semantic + SQL structured | Semantic for text, deterministic for exact facts |
| Data | PostgreSQL + pgvector | Reuses existing stack; one store for vectors + structured |
| Sources | legislation.gov.uk, Find Case Law, ACAS | Official, free, machine-readable (see `01a_PHASE1_API_APPENDIX.md`) |

## 6. What is deliberately NOT in the architecture
- No component that files, submits, or represents on a user's behalf (reserved activity).
- No general "ask me anything about law" free-chat (off-strategy, shallow, the DoNotPay failure mode).
- No path that sends raw personal/case data to a third-party model.
- No outcome-guarantee / "win your case" logic.
