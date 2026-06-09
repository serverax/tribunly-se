-- 037_core_workspace_ingestion_errors.sql
-- Core modular tables (NOT payment): ingestion error log, workspace isolation,
-- bundle records, and document-generation audit. Idempotent; additive.

-- ── corpus_ingestion_errors: failed-fetch/parse log (ingestion errors are logged) ──
CREATE TABLE IF NOT EXISTS corpus_ingestion_errors (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingestion_run_id  UUID,
    domain            TEXT NOT NULL DEFAULT 'employment_uk',
    source_id         TEXT,
    source_url        TEXT,
    error_type        TEXT NOT NULL,            -- fetch_404|fetch_5xx|parse_error|licence_blocked|other
    error_message     TEXT,
    http_status       INT,
    retryable         BOOLEAN NOT NULL DEFAULT true,
    occurred_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS corpus_ingestion_errors_run_idx ON corpus_ingestion_errors (ingestion_run_id);
CREATE INDEX IF NOT EXISTS corpus_ingestion_errors_src_idx ON corpus_ingestion_errors (source_id);

-- ── workspaces + members (workspace/case isolation) ─────────────────────────
CREATE TABLE IF NOT EXISTS workspaces (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    owner_user_id UUID,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workspace_members (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL,
    role         TEXT NOT NULL DEFAULT 'member',   -- owner|admin|member|viewer
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, user_id)
);
CREATE INDEX IF NOT EXISTS workspace_members_user_idx ON workspace_members (user_id);

-- ── bundles: generated document-bundle records (per case) ───────────────────
CREATE TABLE IF NOT EXISTS bundles (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id           UUID,
    workspace_id      UUID,
    jurisdiction_code TEXT REFERENCES legal_jurisdictions(jurisdiction_code),
    status            TEXT NOT NULL DEFAULT 'generated',  -- preview|generated
    components        JSONB,            -- component name -> safety/metadata
    paid              BOOLEAN NOT NULL DEFAULT false,      -- DB-backed payment state
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS bundles_case_idx ON bundles (case_id);

-- ── document_generation_audit: prove every paid doc traces to grounded sources ──
CREATE TABLE IF NOT EXISTS document_generation_audit (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id           UUID,
    document_id       UUID,
    doc_type          TEXT NOT NULL,
    jurisdiction_code TEXT REFERENCES legal_jurisdictions(jurisdiction_code),
    grounded          BOOLEAN NOT NULL DEFAULT false,
    citations_count   INT NOT NULL DEFAULT 0,
    payment_status    TEXT,             -- snapshot of cases.payment_status at generation
    generated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS document_generation_audit_case_idx ON document_generation_audit (case_id);
