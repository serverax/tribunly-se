-- Migration 004: Phase 3 dashboard, retention, coaching, solicitor review
-- Placeholder migration — schemas finalised before Phase 3 build starts.

-- Document readiness tracking
CREATE TABLE IF NOT EXISTS document_readiness (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             uuid        REFERENCES cases(id) ON DELETE CASCADE,
    doc_type            text        NOT NULL,    -- particulars_of_claim | schedule_of_loss | chronology | evidence_checklist
    readiness_percent   int         NOT NULL DEFAULT 0,
    missing_facts       jsonb,                   -- list of required but absent fields
    missing_evidence    jsonb,                   -- evidence types not yet uploaded
    contradictions      jsonb,                   -- detected contradictions
    required_fields     jsonb,                   -- full required field list for this doc type
    can_generate        boolean     NOT NULL DEFAULT false,
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (case_id, doc_type)
);

-- Human case-support coaching sessions
-- Label: "Human case-support coaching" — NOT legal advice.
-- provider_type must be paralegal_coach; never label as solicitor without SRA authorisation.
CREATE TABLE IF NOT EXISTS support_sessions (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             uuid        REFERENCES cases(id) ON DELETE CASCADE,
    provider_type       text        NOT NULL DEFAULT 'paralegal_coach',  -- paralegal_coach only at MVP
    service_scope       text,       -- brief description of what was discussed
    price               numeric(10,2),
    status              text        NOT NULL DEFAULT 'pending',  -- pending | confirmed | completed | cancelled
    notes               text,       -- session notes (encrypted before storing in production)
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT support_sessions_provider_type_check CHECK (provider_type IN ('paralegal_coach'))
);

-- Solicitor review referrals
-- Only triggered on specific high-risk conditions; referral never alters the assessment.
CREATE TABLE IF NOT EXISTS solicitor_reviews (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             uuid        REFERENCES cases(id) ON DELETE CASCADE,
    provider_type       text        NOT NULL DEFAULT 'solicitor',
    partner_firm        text,
    referral_consent    boolean     NOT NULL DEFAULT false,   -- mandatory before handoff
    handoff_pack        jsonb,      -- assessment + deadline + evidence list + docs + audit summary
    price               numeric(10,2),
    status              text        NOT NULL DEFAULT 'triggered',  -- triggered | sent | accepted | rejected
    trigger_reason      text,       -- why solicitor review was triggered
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT solicitor_reviews_consent_check CHECK (
        status = 'triggered' OR referral_consent = true
    )
);

-- Reminder events
-- Message templates are static strings with placeholders — never LLM-generated.
CREATE TABLE IF NOT EXISTS reminder_events (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             uuid        REFERENCES cases(id) ON DELETE CASCADE,
    reminder_type       text        NOT NULL,    -- deadline_approaching | acas_not_started | acas_certificate_missing
                                                 -- evidence_missing | document_incomplete | paid_document_ready
                                                 -- solicitor_review_recommended
    due_at              timestamptz,
    channel             text        NOT NULL DEFAULT 'in_app',  -- in_app | email (later)
    status              text        NOT NULL DEFAULT 'pending',  -- pending | sent | dismissed
    payload             jsonb,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS dr_case_idx ON document_readiness (case_id);
CREATE INDEX IF NOT EXISTS ss_case_idx ON support_sessions (case_id);
CREATE INDEX IF NOT EXISTS sr_case_idx ON solicitor_reviews (case_id);
CREATE INDEX IF NOT EXISTS re_case_idx ON reminder_events (case_id);
CREATE INDEX IF NOT EXISTS re_due_idx  ON reminder_events (due_at) WHERE status = 'pending';
