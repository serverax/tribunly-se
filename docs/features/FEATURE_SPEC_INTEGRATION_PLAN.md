# Feature Spec Integration Plan

**Version:** 0.1  
**Date:** 16 June 2026  
**Source:** [`tasks/FEATURE_SPEC_lawapp.md`](../../tasks/FEATURE_SPEC_lawapp.md)  
**Branch:** `release/lawapp-clean-snapshot`  
**Companion:** [`docs/deployment/UK_EMPLOYMENT_LAW_DEPLOYMENT_PLAN.md`](../deployment/UK_EMPLOYMENT_LAW_DEPLOYMENT_PLAN.md)

---

## 1. Spec summary (plain English)

LawApp's feature layer sits on top of a 16-module UK employment law corpus and a verification-gated answer pipeline. The product must:

- Provide **free anonymous tools** for acquisition and SEO (knowledge browse, deadline clock, document decoder, claim triage, single-run compensation estimate).
- **Gate persistence** behind free registration (save matter, Case Hub, deadline tracking, one free document).
- **Gate depth** behind subscription or pay-per-document (full Document Studio, matter Q&A, law-change alerts).
- **Hand regulated advice** to partner solicitors via referral (F12), never in-app representation.
- Carry **citations and verified/unverified badges** on every served answer; never present unverified model output as settled law.
- **Not persist special-category data** in anonymous flows (document decoder, triage).

Priority waves:

| Wave | Features | Acceptance theme |
|------|----------|------------------|
| 1 | F1-F4 | Anonymous free tools, citations, ACAS stop-clock, no anonymous persistence of sensitive data |
| 2 | F5-F7 | Registration retention: Case Hub, strength engine, estimator save |
| 3 | F8-F10 | Paid depth: Document Studio gate, matter Q&A, law-change watch |
| 4 | F11-F12 | Bilingual, settlement referral, B2B white-label |

---

## 2. Feature map: spec vs current codebase

| ID | Feature | Spec data | Current lawapp | Gap |
|----|---------|-----------|----------------|-----|
| F1 | Knowledge Base | `module`, `provision`, embeddings | `employment_modules` (24 keys), `corpus_chunks`, `legal_sources`; no `provision` table | Partial UI + RAG; needs browse API and nav |
| F2 | Time-Limit Clock | `key_event`, `deadline` on save | `tools.calculate_deadline`, `/api/tools/deadline-calculator`, `cases.key_dates`, `/cases/{id}/deadline` | Anonymous OK; normalized `key_event`/`deadline` tables missing |
| F3 | Document Decoder | retrieval + redaction, no anonymous persist | Upload/extract on **registered** cases only (`/cases/{id}/uploads`) | Need anonymous in-memory decode route + page |
| F4 | Claim Identifier | `claim_assessment` (nullable matter) | `tools.check_claim`, `/api/tools/claim-checker`, `classify.py`, brain pipeline | No `claim_assessment` table; save-to-matter flow partial |
| F5 | Case Hub | `matter`, evidence, deadlines, docs | `cases`, dashboard, `case_detail.html`, timeline, bundle | Spec `matter` entity; strength meter not on hub |
| F6 | Claim Strength Engine | `claim_assessment.strength_score`, ET data | Assessment `strength` in pipeline JSON | No ET outcome dataset; full rationale gated |
| F7 | Compensation Estimator | `valuation` | `tools.estimate_compensation`, `compensation.html` | Single-run OK; `valuation` table missing |
| F8 | Document Studio | `generated_document` + gate | `/api/documents/generate`, bundle routes | No `generated_document` table; gate tie-in partial |
| F9 | Matter Q&A | per-matter embeddings | Not implemented | Subscription scaffold only |
| F10 | Law-Change Watch | `law_change_event`, `watch_match` | Not implemented | Needs temporal corpus + notification job |
| F11 | Bilingual | UI strings + translated layer | English only | Deferred wave 4 |
| F12 | Settlement + referral | `referral` | `referrals` table, `handoff/leads` | Align schema; partner agreements out of scope |

### Service topology (unchanged)

| Port | Service | Features using it |
|------|---------|-------------------|
| 8000 | Monolith + static UI | All feature routes |
| 8016 | Rules | F2, F4, F7 |
| 8017 | RAG | F1, F3, F4, F6, F8, F9 |
| 8018 | Graph-RAG | F6 (Postgres graph today) |
| 8019 | Redaction | F3, F9 |
| 8020 | Audit | F8 gate transitions |
| 8008 | Case service | F5, F12 |
| 8009 | Notification | F5, F10, F12 |

---

## 3. Integration assumptions (documented, safe scaffolds)

Owner decisions RESOLVED 16 June 2026 ([`OWNER_DECISIONS_2026-06-16.md`](../decisions/OWNER_DECISIONS_2026-06-16.md)). Integration assumptions updated:

1. **`matter` bridges `cases`:** New `matter` table references `users(id)` with optional `case_id` FK to existing `cases`. Case Hub APIs continue to use `/cases/*`; feature routes expose `/api/features/matter/*` as the spec-facing layer.
2. **`users` not `app_user`:** Spec DDL uses `app_user`; lawapp canonical table is `users` (migration 047).
3. **No FK to missing knowledge tables:** `cited_provision_ids`, `law_change_event.provision_id`, `generated_document.candidate_id` are UUID columns **without FK** until deployment-order `provision` / `answer_candidate` tables land.
4. **`referral` vs `referrals`:** Spec `referral` table is additive; existing `referrals` remains for legacy handoff until unified.
5. **11-module beta scope:** Product copy stays honest ("11 employment topics"); knowledge API returns `employment_modules` status, not fabricated 16-module coverage.
6. **FCL bulk crawl:** Off-limits; strength engine uses rules + corpus only until licence granted.
7. **Neo4j:** Not added in this integration; graph-RAG uses Postgres `legal_nodes`/`legal_edges` (8018 healthy).

---

## 4. Phased implementation

### Phase 0 (this session): Plan + Wave 1 wiring

| Task | Deliverable |
|------|-------------|
| A | This document |
| B | Migration `077_feature_spec_operational.sql` (additive operational tables) |
| C | `backend/api/features_routes.py` + `backend/core/feature_spec_service.py` |
| D | F1 browse API + `knowledge.html` |
| E | F3 anonymous `POST /api/features/document-decode` (in-memory, redacted) |
| F | F4 `POST /api/features/claim-assessment` (anonymous + optional persist) |
| G | Nav update on `index.html` per spec section 6 |
| H | Tests `tests/test_feature_spec_integration.py` |
| I | Docker smoke proof → `reports/feature_spec_integration_cursor.txt` |

### Phase 1 (next): Wave 1 hardening

- Verified/unverified badge on all tool responses (align with CitationGuard trace).
- ACAS stop-clock fields on deadline calculator UI (wire `ec_day_a`/`ec_day_b` to `/api/deadline/calculate`).
- Knowledge module detail pages with date-scoped retrieval (`as_at_date`).

### Phase 2: Wave 2 registration retention

- `POST /api/features/matter` create from Wave 1 tool result.
- Case Hub: live countdown from `deadline.due_date`, strength meter from `claim_assessment`.
- Save `valuation` from compensation tool.
- Subscription entitlement checks (scaffold; payments work order separate).

### Phase 3: Wave 3 monetized depth

- `generated_document` + answer_candidate gate (when knowledge tier DDL lands).
- F9 matter Q&A (subscription gate).
- F10 law-change watch job + `watch_match` notifications.

### Phase 4: Wave 4 differentiation

- F11 Arabic UI layer.
- F12 partner referral workflow.
- B2B tenant isolation (separate work order).

---

## 5. Blocking questions for owner  -  RESOLVED

All 10 questions answered 16 June 2026. Full verbatim record: [`docs/decisions/OWNER_DECISIONS_2026-06-16.md`](../decisions/OWNER_DECISIONS_2026-06-16.md).

| # | Topic | Decision summary |
|---|-------|----------------|
| 1 | Matter vs cases | `matter` canonical; `/cases/*` aliases during transition; migrate then deprecate |
| 2 | Knowledge schema | `provision`/`module` canonical; `corpus_chunks` = embedding layer |
| 3 | Module taxonomy | Map 24 to 16 + tags; honest 11 production marketing |
| 4 | ET outcomes | Rules + corpus only until FCL Computational Analysis Licence |
| 5 | Partner referrals | `partner_registry` + notification (8009); owner selects partners |
| 6 | Payments | After Wave 2 hub; Stripe SKUs at Wave 3 start |
| 7 | Document storage | `evidence_item` only; migrate legacy `documents` |
| 8 | Teaser persistence | Funnel signals only; no special-category anonymous persist |
| 9 | Law-change | Scheduled checksum + human sign-off |
| 10 | Bilingual | UI bundles any provider; case facts on-device/self-hosted only (Wave 4) |

---

## 6. API surface (feature layer)

| Method | Route | Feature | Auth |
|--------|-------|---------|------|
| GET | `/api/features/knowledge/modules` | F1 list | Public |
| GET | `/api/features/knowledge/modules/{key}` | F1 detail | Public |
| POST | `/api/features/document-decode` | F3 | Public (no persist) |
| POST | `/api/features/claim-assessment` | F4 | Public; persist if `matter_id` + auth |
| POST | `/api/features/matter` | F5 create | Registration |
| GET | `/api/features/matter/{id}/hub` | F5 hub | Registration |
| POST | `/api/features/matter/{id}/deadlines` | F2 save | Registration |
| POST | `/api/features/valuation` | F7 save | Registration |
| POST | `/api/features/strength` | F6 | Public preview; full gated |
| POST | `/api/features/referral` | F12 | Registration |

Existing tools remain: `/api/tools/*` (Wave 1 funnel).

---

## 7. Verification

```powershell
# Local Docker
docker compose up -d --build backend db redis lawapp-rules-service lawapp-rag-service

# Health
curl -s http://localhost:8000/health
curl -s http://localhost:8016/health
curl -s http://localhost:8017/health

# Wave 1 feature paths
curl -s http://localhost:8000/api/features/knowledge/modules
curl -s -X POST http://localhost:8000/api/tools/deadline-calculator -H "Content-Type: application/json" -d "{\"event_date\":\"2026-01-15\",\"event_type\":\"dismissal\"}"
curl -s -X POST http://localhost:8000/api/features/claim-assessment -H "Content-Type: application/json" -d "{\"facts\":\"I was dismissed after 3 years\"}"
curl -s -X POST http://localhost:8000/api/features/document-decode -H "Content-Type: application/json" -d "{\"text\":\"Your employment is terminated effective immediately.\"}"

pytest tests/test_feature_spec_integration.py -q
```

Artifact: `reports/feature_spec_integration_cursor.txt`

---

## 8. What NOT to do

- No push to `main`, no production K8s, no secret rotation.
- No FCL bulk crawl or fabricated legal rows.
- No bypass of Brain / CitationGuard on generative paths.
- No claiming 16-module coverage in UI while beta is 11 topics.
- No em dashes in new user-facing copy.

---

*Owner decisions recorded 2026-06-16. Phase 0+ on `release/lawapp-clean-snapshot`; partner signing and FCL grant remain owner actions.*
