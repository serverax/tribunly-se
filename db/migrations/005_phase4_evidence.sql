-- Migration 005: Phase 4 evidence intelligence
-- Placeholder — finalised before Phase 4 build starts.

CREATE TABLE IF NOT EXISTS evidence_items (
    id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id              uuid        REFERENCES cases(id) ON DELETE CASCADE,
    document_id          uuid        REFERENCES documents(id) ON DELETE SET NULL,
    evidence_type        text        NOT NULL,   -- dismissal_letter | contract | appeal_outcome
                                                  -- pay_slip | email_chain | witness_statement | other
    extracted_facts      jsonb,      -- raw OCR extraction — not trusted until user confirms
    user_confirmed_facts jsonb,      -- confirmed subset of extracted_facts
    supports             jsonb,      -- {"assertions": [...], "assessment_fields": [...]}
    weakens              jsonb,      -- {"assertions": [...], "assessment_fields": [...]}
    missing_links        jsonb,      -- evidence types still needed
    confidence_score     numeric(4,3),
    user_confirmed       boolean     NOT NULL DEFAULT false,  -- must be true before entering assessment
    created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ei_case_idx ON evidence_items (case_id);
CREATE INDEX IF NOT EXISTS ei_confirmed_idx ON evidence_items (case_id, user_confirmed);
