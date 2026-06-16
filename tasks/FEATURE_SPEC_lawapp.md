# LawApp — Feature Build Specification

**Version:** 1.0
**Date:** 16 June 2026
**Owner:** Khalid (Solution Architect)
**Audience:** LawApp dev team
**Companion docs:** Deployment Work Order v1.0 (knowledge tier), Architecture Decisions (schema, graph engine, taxonomy, licence, embedding dim)

---

## 1. Purpose

Define the user-facing features that sit on top of the 16-module corpus and the verification-gated pipeline, and tell the team exactly what data each feature needs, where the free line sits, and in what order to build. This is the operational and product layer. The knowledge tier (corpus, retrieval, gate) is specified in the Deployment Work Order and is a prerequisite.

---

## 2. Regulatory posture (this shapes every feature)

LawApp provides legal information and document drafting. It does not give regulated legal advice and does not represent users. Anything that crosses into advice or representation is handed to a regulated partner solicitor. This keeps LawApp on the clean side of the SRA line while the unregulated incumbents lean on founder reputation.

Three rules apply to every feature that produces output:

- Every served answer or document carries its source citation and a verified or unverified badge.
- Nothing the model generates reaches a user as settled law without passing the verification gate (see Work Order section 8).
- Employment dispute facts are sensitive personal data, and discrimination or health elements are special category data under UK GDPR. Any feature that persists case facts requires a registered account with explicit, logged consent. Anonymous tools must not persist special category data.

---

## 3. The free-versus-gated model (the boundary rule, stated once)

Run free, gate the save. Tools and knowledge run anonymously and free, because that is the acquisition and SEO engine. The moment a user wants to persist a result, save a case, track a deadline, or download a document, that is the registration trigger, and it is the highest-converting point in the journey.

Three boundaries exist:

- **Ungated free.** Anonymous use, no persistence. Triage, calculators, document decoder, knowledge base.
- **Registration (free, no payment).** Persistence: save a matter, the Case Hub, deadline tracking, one free document download.
- **Paid.** Subscription for depth and automation, or pay-per-document for one-off users, or referral and B2B for the high-value tail.

---

## 4. New data layer (operational tier)

These tables complement the knowledge tier. Note `case` is a reserved word in SQL, so the case entity is `matter`.

```sql
CREATE TABLE matter (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL REFERENCES app_user(id),
  title          TEXT,
  status         TEXT NOT NULL DEFAULT 'draft' CHECK (status IN
                   ('draft','active','acas','et1_filed','settled','closed')),
  claim_types    SMALLINT[],             -- module ids
  strength_score NUMERIC,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE key_event (                 -- the dated facts deadlines derive from
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id  UUID NOT NULL REFERENCES matter(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,              -- effective_date_of_termination | acas_ec_start | acas_ec_end | grievance_raised
  event_date DATE NOT NULL
);

CREATE TABLE deadline (                  -- computed limitation deadlines
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id    UUID NOT NULL REFERENCES matter(id) ON DELETE CASCADE,
  deadline_type TEXT NOT NULL,           -- et1_limitation | acas_ec_deadline | appeal
  due_date     DATE NOT NULL,
  computed_from UUID[],                  -- key_event ids
  rule_ref     TEXT NOT NULL,            -- which limitation rule produced it
  status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','met','missed'))
);

CREATE TABLE evidence_item (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id    UUID NOT NULL REFERENCES matter(id) ON DELETE CASCADE,
  kind         TEXT NOT NULL CHECK (kind IN ('upload','note','generated_doc')),
  filename     TEXT,
  storage_uri  TEXT,
  pii_redacted BOOLEAN NOT NULL DEFAULT false,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE claim_assessment (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id           UUID REFERENCES matter(id) ON DELETE CASCADE,  -- nullable for anonymous runs
  matched_module_ids  SMALLINT[],
  matched_tests       JSONB,
  strength_score      NUMERIC,
  rationale           TEXT,
  cited_provision_ids UUID[],
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE valuation (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id  UUID REFERENCES matter(id) ON DELETE CASCADE,           -- nullable for anonymous runs
  low        NUMERIC, mid NUMERIC, high NUMERIC,
  basis      JSONB,                       -- statutory caps, award bands, inputs
  as_at      DATE NOT NULL,               -- law-as-at date used
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE generated_document (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id    UUID NOT NULL REFERENCES matter(id) ON DELETE CASCADE,
  doc_type     TEXT NOT NULL,             -- grievance | et1 | witness_statement | chronology | scott_schedule | settlement_response
  candidate_id UUID REFERENCES answer_candidate(id),  -- ties drafting into the verification gate
  state        TEXT NOT NULL DEFAULT 'draft' CHECK (state IN ('draft','paid','downloaded')),
  citation_ids UUID[],
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE law_change_event (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provision_id   UUID NOT NULL REFERENCES provision(id),
  change_type    TEXT NOT NULL CHECK (change_type IN ('commenced','amended','repealed','superseded')),
  effective_date DATE NOT NULL,
  detected_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE watch_match (                -- links a law change to an affected matter
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  law_change_event_id UUID NOT NULL REFERENCES law_change_event(id),
  matter_id           UUID NOT NULL REFERENCES matter(id) ON DELETE CASCADE,
  notified            BOOLEAN NOT NULL DEFAULT false,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE referral (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id     UUID NOT NULL REFERENCES matter(id),
  partner_id    UUID,
  referral_type TEXT NOT NULL CHECK (referral_type IN ('settlement_signoff','representation')),
  status        TEXT NOT NULL DEFAULT 'open',
  fee_basis     TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 5. Feature catalogue

Each feature lists what it does, its data dependencies, the services it touches, the free-versus-gated boundary, and what it depends on.

### F1. Knowledge Base
Browsable, citation-backed, date-aware view of the 16 modules and their subtopics.
- **Data:** `module`, `provision`, `legal_source`, `embedding`.
- **Services:** RAG (8017).
- **Boundary:** ungated free.
- **Depends on:** Work Order Phases 1 to 3.

### F2. Time-Limit Clock
Calculates the three-months-less-one-day limitation, applying ACAS early conciliation stop-the-clock rules, from the user's key dates.
- **Data:** reads `provision` for the rule text; anonymous run computes in memory; on save writes `key_event` and `deadline`.
- **Services:** rules (8016).
- **Boundary:** calculator ungated free; saving the deadline to a matter is registration-gated.
- **Depends on:** F1 corpus, rules service.

### F3. Plain-English Document Decoder
Upload a contract, disciplinary letter, or settlement agreement and get a grounded, jargon-free breakdown.
- **Data:** retrieval over `provision` and `curated_answer`; uploads pass through redaction before any logging.
- **Services:** RAG (8017), redaction (8019), verification gate.
- **Boundary:** ungated free for the breakdown; saving the document to a matter is registration-gated. Anonymous uploads are processed in memory and not persisted (special category data rule).
- **Depends on:** F1, verification gate.

### F4. Claim Identifier
Guided triage mapping the user's facts to modules and the relevant legal tests.
- **Data:** retrieval over `provision`; writes `claim_assessment` (matter_id null when anonymous).
- **Services:** RAG (8017), rules (8016).
- **Boundary:** ungated free for the result; saving to a matter is registration-gated.
- **Depends on:** F1.

### F5. Case Hub
Persistent workspace: deadlines, document bundle, chronology, evidence log, rising strength meter. This is the retention spine.
- **Data:** `matter`, `key_event`, `deadline`, `evidence_item`, `claim_assessment`, `generated_document`.
- **Services:** case (8008), notification (8009).
- **Boundary:** registration-gated in full.
- **Depends on:** F2, F4, app_user and auth (existing).

### F6. Claim Strength Engine
Extends F4 with a strength score grounded in ET outcome data, showing the provisions and leading cases that drive the score.
- **Data:** `claim_assessment.strength_score` and `rationale`, `cited_provision_ids`; ET outcome dataset (ingested under the Find Case Law Computational Analysis Licence).
- **Services:** RAG (8017), graph traversal (Postgres).
- **Boundary:** basic score ungated free; the full rationale and case-by-case breakdown registration-gated.
- **Depends on:** F4, case-law corpus, Computational Analysis Licence approved.

### F7. Compensation and Settlement Estimator
Realistic award range grounded in statutory caps and award-band data, with the ERA 2025 cap removal flagged where relevant.
- **Data:** `valuation`; reads `provision` for caps at the correct as-at date.
- **Services:** rules (8016), RAG (8017).
- **Boundary:** single estimate ungated free; saving and re-running against a tracked matter registration-gated.
- **Depends on:** F1, temporal query helper.

### F8. Document Studio
Tribunal-ready drafting: grievance, ET1 grounds, witness statement, chronology, Scott schedule, settlement-response letter.
- **Data:** `generated_document` tied to `answer_candidate` so every draft runs through the gate; `citation_ids` mandatory.
- **Services:** RAG (8017), verification gate, admin (8007) for review, audit (8020).
- **Boundary:** draft preview registration-gated (one free download per account); tribunal-ready download is paid (subscription or pay-per-document).
- **Depends on:** F5, verification gate.

### F9. AI Q&A over your own documents
Ask grounded questions across the documents in your own matter.
- **Data:** `evidence_item`, per-matter embeddings, `provision`.
- **Services:** RAG (8017), redaction (8019).
- **Boundary:** subscription only.
- **Depends on:** F5, F8.

### F10. Law-Change Watch
Detects when a commencement or amendment affects an open matter and notifies the user. The hook competitors cannot copy, because it depends on the temporal corpus.
- **Data:** `law_change_event`, `watch_match`, `matter.claim_types`, `key_event`.
- **Services:** notification (8009), scheduled job over the corpus.
- **Boundary:** subscription only.
- **Depends on:** F5, temporal versioning, ingestion connectors.

### F11. Bilingual mode
Arabic and English to start, serving the underserved-community gap.
- **Data:** translated UI strings; retrieval stays on the English corpus with translated query and response layers.
- **Services:** RAG (8017), translation layer.
- **Boundary:** applies across all tiers; no separate gate.
- **Depends on:** F1 to F8 stable first.

### F12. Settlement decoder and referral handoff
Decode a settlement agreement, then hand sign-off and representation to a regulated partner.
- **Data:** `referral`; reuses F3 decoder.
- **Services:** case (8008), notification (8009).
- **Boundary:** decoder ungated free; referral creation registration-gated; partner fee is referral revenue.
- **Depends on:** F3, partner agreements in place.

---

## 6. Navigation and menu

1. **Check My Situation** — F4 Claim Identifier (free, ungated)
2. **Free Tools** — F2 Time-Limit Clock, F7 Estimator, F3 Document Decoder (free, ungated)
3. **Know Your Rights** — F1 Knowledge Base (free)
4. **My Case** — F5 Case Hub (registration)
5. **Documents** — F8 Document Studio (free preview, paid download)
6. **Settlement** — F7, F12 (mixed)
7. **Get Help** — F12 referral and human review

---

## 7. The retention hook

The loop is an open matter with a ticking clock and a rising score. Three forces pull the user back, all reading from the Case Hub:

- A visible countdown from `deadline.due_date` with the next action stated.
- A `matter.strength_score` that climbs as `evidence_item` and `generated_document` rows are added.
- `watch_match` alerts from Law-Change Watch, the genuine non-manufactured reason to return.

Build the first two with F5. The third arrives with F10 and is the part that is structurally unique to LawApp.

---

## 8. Monetization mapping

- **Free, ungated (acquisition and SEO):** F1, F2, F3, F4, F7 single-run.
- **Registration (lead capture at peak intent):** F5, plus save and one free document.
- **Subscription, around £15 to £25 a month (engaged litigant):** unlimited F8, F9, F10.
- **Pay-per-document, around £9 to £19 (one-off users):** single F8 tribunal-ready download.
- **Referral, not success fee (clean of regulation):** F12 partner handoff.
- **B2B white-label (the real margin):** licence the engine to firms, unions, and Citizens Advice.

---

## 9. Priority waves

Each wave has an acceptance gate. Do not start a wave until the previous one passes.

### Wave 1 — Free engine (the acquisition and SEO layer)
F1 Knowledge Base, F2 Time-Limit Clock, F3 Document Decoder, F4 Claim Identifier.
**Acceptance:** all four run anonymously with no persistence; every answer carries a citation and a verified or unverified badge; the time-limit clock correctly applies ACAS stop-the-clock to a worked example; no special category data is persisted in anonymous runs.

### Wave 2 — Registration and retention
F5 Case Hub, deadline tracking, F6 Claim Strength Engine, F7 Estimator.
**Acceptance:** a registered user can save a matter from a Wave 1 result; deadlines render with a live countdown and a next action; the strength score shows its driving provisions and cases; the estimator uses the correct law-as-at date.

### Wave 3 — Monetized depth
F8 Document Studio, F9 AI Q&A, F10 Law-Change Watch.
**Acceptance:** no document reaches a user without passing the gate and carrying citations; subscription gates F9 and F10; Law-Change Watch fires a `watch_match` when a seeded commencement affects an open matter's `claim_types`.

### Wave 4 — Differentiation and tail
F11 Bilingual mode, F12 Settlement decoder and referral, B2B white-label.
**Acceptance:** Arabic mode returns the same citation-backed answers as English on a parallel test set; a referral creates a `referral` row and notifies the partner; the engine runs in a white-label configuration with tenant isolation.

---

## 10. Out of scope

Payments integration detail, frontend visual design, and Ollama inference configuration are separate work orders. Court representation is never in scope; it is always referred to a regulated partner.
