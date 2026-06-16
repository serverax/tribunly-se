# Owner Decisions  -  16 June 2026

**Status:** RESOLVED  
**Branch:** `release/lawapp-clean-snapshot`  
**Sources:** Deployment Plan §6, Feature Spec §5, Agentic Foundation Questions  
**Cross-cutting principle:** Replace forks, do not sync forever (`matter` > `cases`, `provision` > `corpus_chunks`, `evidence_item` > `documents`, `infra/k8s` > `k8s/`).

---

## Owner-action items (not agent decisions)

| Item | Owner |
|------|-------|
| FCL / Computational Analysis Licence grant status | Owner to confirm |
| Partner org selection and signing | Owner org action |
| Companies House API key registration | Owner action |
| ACAS / EHRC / HSE licence sign-off per `legal_source` row | Owner action |
| Staging separate cluster provisioning | Owner action |
| Track C production entry | Independent of knowledge layer completion |

---

## Deployment Plan §6 (15 questions)

### Q1 Schema strategy

Adopt the greenfield `provision` / `module` / `legal_source` / `answer_candidate` / `curated_answer` as the canonical domain. Re-point `corpus_chunks` to be the embedding layer referencing `provision.id`. Backfill the 889 chunks' sources into `legal_source` + `provision`, run a time-boxed dual-write during cutover, then make `provision` authoritative. Not permanent dual-write; that is tech debt with a consistency hazard.

### Q2 Graph engine

Keep Postgres `legal_nodes` / `legal_edges` and update the work order. The codebase already went Postgres, the traversals are shallow, and adding Neo4j now reintroduces the exact sync burden crash-looping 8018. Refactor 8018 to traverse Postgres and fail closed. No Neo4j container.

### Q3 Module taxonomy

16 canonical module codes plus a mapping table from the 24 `employment_modules` keys, with a subtopic/tag layer for the finer detail. Do not destructively replace; map and resolve. Coverage stays honest: 11 production now, 13 partial, growing to full 16-module depth. (Same answer drives Feature §5 Q3 and Deployment Q13.)

### Q4 FCL licence

Status is yours to confirm, and the gap table says it is not granted (`FCL_BULK_LICENCE_GRANTED=false`, no written grant). Decision: sample-only for Phase 2, with a precise boundary. Reading a handful of judgments to hand-author curated content or test fixtures is fine under the Open Justice Licence. Embedding judgments into the RAG pipeline at any scale is computational analysis and needs the Computational Analysis Licence, so keep that off until the written grant lands. Apply now.

### Q5 Embedding model and dimension

1024, local, and yes re-embed. Resolve the three-way mismatch by standardising on one 1024 local model (`bge-large-en-v1.5` or `mxbai-embed-large`, both Ollama-runnable, which matches your local-Ollama standing order). Delete the `text-embedding-3-small` / 1536 env reference; that is an external OpenAI model and violates local-only anyway. The corpus is only ~889 chunks, so re-embedding is cheap and now is the moment, before it grows. Store model name and dimension per row.

### Q6 Phase 0 in parallel or defer

Parallel. Phase 0 is additive and non-risky, and the 8018 fix unblocks testing of everything, so run it alongside the k6/Ollama/assessment fixes. Gate the risky phases (ingestion, schema cutover) behind the Track A+B re-ACCEPT. The graph-RAG stub goes first regardless.

### Q7 Corpus DB isolation

Shared `lawapp` database with a dedicated `knowledge.*` schema. The tiers cross-reference (`provision` to `matter` via citations), so a separate physical database buys cross-database join pain and ops overhead for no real gain. The schema namespace gives you logical separation, schema-scoped least-privilege roles (`knowledge` read-only to the app role), and RLS where needed, on one engine.

### Q8 K8s source of truth

`infra/k8s/` is canonical (full namespaces plus monitoring CronJobs). Deprecate the partial `k8s/` subtree, migrate anything unique out of it, then delete it. Two manifest trees is config drift waiting to happen, which is a security risk, not just an annoyance.

### Q9 Admin reviewer workflow

Build the gate UI in the dedicated `lawapp-admin-service` (8007), not monolith routes. The reviewer is the human in the verification gate, a privileged role, so it gets its own auth boundary and audit. Require SSO with MFA for reviewers. Keep it off the public monolith surface.

### Q10 ERA 2025 commencement owner

Scheduled job for detection (`legislation.gov.uk` checksum plus a maintained commencement-date table), with a human sign-off before flipping `prospective` to `in_force`. Pure manual misses a commencement; pure automated flips the law without review. Owner of the approval is the legal/verification function. (Same shape as Feature §5 Q9.)

### Q11 Licensing sign-off

Yours to action. gov.uk and legislation.gov.uk are Open Government Licence, permissive with attribution. Confirm ACAS, EHRC, and HSE terms individually and record the licence on each `legal_source` row, using the metadata spine you already have. No source goes live in Phase 2 until its licence is confirmed and recorded.

### Q12 Staging cluster

Separate staging cluster, not namespace isolation on prod. For special-category data, a namespace is too weak a boundary between a looser, frequently-deployed staging and prod. If cost forces it, a strongly isolated separate node pool with network policy is the floor, but separate is the right answer.

### Q13 Beta messaging

The API returns true per-module status (`production`, `partial`, `unavailable`) and a real coverage count, never the 16 target while 11 are live. Your own "what not to do" forbids conflating the 16-module layer with the 11-topic beta, so the API is the place to enforce honesty.

### Q14 Ollama placement

In-cluster Ollama Deployment in the AI namespace, internal-only, for the gate auto-check, which is a light scoring call not heavy generation. Dev uses the local host. Keep inference inside the cluster boundary with no external egress, per local-Ollama standing order. A Deployment with node affinity, not a DaemonSet, unless you specifically need one per node.

### Q15 Track C entry

Independent. Completing this order is a prerequisite milestone, not the Track C trigger. Track C keeps its own gates: secrets rotation, Stripe live, backup drill, pen test, DPIA, and the P0 blockers (k6, corpus under 1000, live accuracy). Do not let "knowledge layer done" imply "ready for prod."

---

## Feature Spec §5 (10 questions)

### 1 Matter vs cases

Replace over time. `matter` is canonical; assumption #1 (`matter` with optional `case_id` FK) is the correct bridge. Migrate, keep `/cases/*` as aliases during transition, then deprecate. Not forever-sync.

### 2 Knowledge schema

Adopt `provision` / `module`; `corpus_chunks` becomes the embedding layer; `employment_modules` maps to 16 via the mapping table. Same as Deployment Q1 and Q5.

### 3 Module taxonomy

Map 24 to 16 plus tags. Do not expand marketing ahead of corpus. Advertise the 11 production topics, grow to 16. Same as Deployment Q3 and Q13.

### 4 ET outcome dataset

Status is yours; the gap table says not granted. Until then F6 strength runs on rules plus corpus only, exactly as assumption #6 states. Ship the rules-and-corpus score now, enrich with ET outcome data once the Computational Analysis Licence lands. Do not block F6 on FCL.

### 5 Partner referrals

Partner selection is your org action; none are signed yet. Build the mechanism now: a partner registry table with per-partner webhook and email config, routed through notification (8009). Model is a referral fee, not a success fee, with SRA-style disclosure to the client logged in `referral`. Do not hardcode partners.

### 6 Payments sequencing

After the Wave 2 hub. Build the hub and an entitlement-check scaffold in Wave 2 to capture free registrations, then wire real Stripe SKUs at the start of Wave 3. Do not gate the hub itself behind payment. Keep test mode until the separate payments work order.

### 7 Document decode storage

`evidence_item` only. Do not dual-write to the legacy `documents` table, which recreates the matter/cases problem at the document layer. Migrate legacy `documents` into `evidence_item` over time. One source of truth.

### 8 Anonymous teaser persistence

Drop it, or strip it to non-special-category metadata. Encryption is not a lawful basis, and storing anonymous users' case facts has no Article 9 condition, which contradicts both the spec and the security posture given the DPP and Levales fines. Keep only non-sensitive funnel signals (tool used, timestamp, coarse outcome) under legitimate interest. Strict GDPR alignment wins; rebuild the funnel on signals that are not special-category.

### 9 Law-change detection

Scheduled checksum job plus human sign-off before promotion. Same as Deployment Q10. Not manual-only.

### 10 Bilingual provider

Split it. UI strings can use pre-translated bundles or any API, since they carry no personal data. Anything containing user case facts must be translated on-device or self-hosted, because sending special-category data to a third-party translation API is a processing and likely a transfer risk. Deferred to Wave 4 regardless.

---

## Agentic Foundation Questions (6 endorsements)

### Mastra vs Python Brain

**Endorse, strongly.** Rationale is exactly right: a second orchestration runtime is a second place CitationGuard and the gate can be bypassed. Only an ADR proving a hard requirement Python cannot meet should change it, and there isn't one.

### RLHF

**Endorse.** Feedback queue only is correct given local Ollama and fail-closed grounding. The DSPy optimizer planned for Phase 2 is the right ceiling, prompt and program optimisation as a read-only queue consumer, but pass its outputs through the same eval harness so it cannot drift citations. Never RLHF the generator.

### Companies House

**Endorse.** Owner action: register for the free API key and confirm the rate limits (around 600 requests per five minutes) and terms. The high-value uses are verifying the respondent employer entity on the ET1, checking active/dissolved/administration status because it affects enforceability, and getting the registered office for service. Caching in Redis as planned is right. Public data, low privacy risk.

### EU AI Act retention

**Endorse** the Phase 1 default of no auto-purge, but with one correction that matters. The Act likely does not even apply (UK-only, and you are probably not high-risk under Annex III anyway), so treat its numbers (logs at least six months, technical documentation ten years) as a voluntary benchmark. Real driver is UK GDPR storage limitation, and "immutable plus never purge" directly conflicts with both storage limitation and the right to erasure if those logs hold case facts. Reconcile with a standing design rule: immutable traces hold metadata, decisions, and hashes, never raw special-category content. Then keep them indefinitely for defensibility, and erasing a matter never requires touching the immutable log. Set explicit windows before real users: case data on a limitation-driven policy then erase or anonymise; PII-free audit and traces retained twelve months or more.

### Domain expansion

**Endorse, strongly.** A half-populated immigration or housing domain emitting ungrounded answers is the misinformation risk in concentrated form. Keep `employment_uk` the only enabled domain; gate each new one on its own corpus, verification, tests, and case-law scope. Fail-closed on unsupported jurisdiction is correct.

### Tool calling

**Endorse.** Separate surfaces with shared deterministic implementations is good design and avoids drift. Add two things: the public preview surface enforces the no-anonymous-special-category-persistence rule, and the agent registry tools carry auth and audit.

---

## Implementation pointers

| Decision area | Phase 0 artifact |
|---------------|------------------|
| Q2 Postgres graph | `backend/core/rag/graphrag_traversal.py`, port 8018 |
| Q1/Q5/Q7 knowledge schema | `db/migrations/078_knowledge_schema_stubs.sql` |
| Q5 embeddings | `db/migrations/080_embedding_1024_prep.sql`, `scripts/reembed_corpus_1024.py` |
| Feature §5 #8 teaser | `db/migrations/079_teaser_funnel_partner.sql`, `backend/core/login_gate.py` |
| Q8 K8s | `k8s/DEPRECATED.md`, `docs/deployment/K8S_MANIFEST_MIGRATION.md` |
| Feature §5 #5 partners | `partner_registry` table, notification stub route |
| Feature §5 #1 matter | `docs/deployment/MATTER_CASES_ALIAS_PLAN.md` |
