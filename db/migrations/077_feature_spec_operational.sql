-- 077_feature_spec_operational.sql
-- Feature Spec operational tier (tasks/FEATURE_SPEC_lawapp.md section 4).
-- Additive bridge to existing users + cases. No FK to provision/answer_candidate
-- until UK employment law knowledge DDL lands (see deployment work order).

-- ── matter (spec entity; bridges legacy cases) ───────────────────────────────
CREATE TABLE IF NOT EXISTS matter (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    case_id         UUID REFERENCES cases(id) ON DELETE SET NULL,
    title           TEXT,
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','active','acas','et1_filed','settled','closed')),
    claim_types     SMALLINT[],
    strength_score  NUMERIC,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS matter_user_idx ON matter (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS matter_case_uidx ON matter (case_id) WHERE case_id IS NOT NULL;

-- ── key_event ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS key_event (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id   UUID NOT NULL REFERENCES matter(id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL,
    event_date  DATE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS key_event_matter_idx ON key_event (matter_id);

-- ── deadline ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deadline (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id     UUID NOT NULL REFERENCES matter(id) ON DELETE CASCADE,
    deadline_type TEXT NOT NULL,
    due_date      DATE NOT NULL,
    computed_from UUID[],
    rule_ref      TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open','met','missed')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS deadline_matter_idx ON deadline (matter_id);

-- ── evidence_item ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evidence_item (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id    UUID NOT NULL REFERENCES matter(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL CHECK (kind IN ('upload','note','generated_doc')),
    filename     TEXT,
    storage_uri  TEXT,
    pii_redacted BOOLEAN NOT NULL DEFAULT false,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS evidence_item_matter_idx ON evidence_item (matter_id);

-- ── claim_assessment ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS claim_assessment (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id           UUID REFERENCES matter(id) ON DELETE CASCADE,
    matched_module_ids  SMALLINT[],
    matched_tests       JSONB,
    strength_score      NUMERIC,
    rationale           TEXT,
    cited_provision_ids UUID[],
    verification_badge  TEXT NOT NULL DEFAULT 'unverified'
                        CHECK (verification_badge IN ('verified','unverified')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS claim_assessment_matter_idx ON claim_assessment (matter_id);

-- ── valuation ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS valuation (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id  UUID REFERENCES matter(id) ON DELETE CASCADE,
    low        NUMERIC,
    mid        NUMERIC,
    high       NUMERIC,
    basis      JSONB,
    as_at      DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS valuation_matter_idx ON valuation (matter_id);

-- ── generated_document ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS generated_document (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id    UUID NOT NULL REFERENCES matter(id) ON DELETE CASCADE,
    doc_type     TEXT NOT NULL,
    candidate_id UUID,
    state        TEXT NOT NULL DEFAULT 'draft'
                 CHECK (state IN ('draft','paid','downloaded')),
    citation_ids UUID[],
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS generated_document_matter_idx ON generated_document (matter_id);

-- ── law_change_event (provision_id FK deferred) ────────────────────────────
CREATE TABLE IF NOT EXISTS law_change_event (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provision_id   UUID NOT NULL,
    change_type    TEXT NOT NULL
                   CHECK (change_type IN ('commenced','amended','repealed','superseded')),
    effective_date DATE NOT NULL,
    detected_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── watch_match ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watch_match (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    law_change_event_id UUID NOT NULL REFERENCES law_change_event(id),
    matter_id           UUID NOT NULL REFERENCES matter(id) ON DELETE CASCADE,
    notified            BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS watch_match_matter_idx ON watch_match (matter_id);

-- ── referral (spec table; legacy referrals table unchanged) ──────────────────
CREATE TABLE IF NOT EXISTS referral (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id     UUID NOT NULL REFERENCES matter(id),
    partner_id    UUID,
    referral_type TEXT NOT NULL CHECK (referral_type IN ('settlement_signoff','representation')),
    status        TEXT NOT NULL DEFAULT 'open',
    fee_basis     TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS referral_matter_idx ON referral (matter_id);
