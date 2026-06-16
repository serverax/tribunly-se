-- Migration 019  -  Brain Phase 1 Schema Updates
-- Adds new columns to brain_traces for 19-step pipeline.
-- Adds safety_boundary_checks audit table.
-- Adds document_facts table for real document extraction.
-- Adds wasm_calculations table for client-side WASM audit.

-- ── brain_traces additions ────────────────────────────────────────────────────
ALTER TABLE brain_traces
    ADD COLUMN IF NOT EXISTS missing_facts   JSONB       NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS rag_sources     JSONB       NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS safety_passed   BOOLEAN,
    ADD COLUMN IF NOT EXISTS memory_saved    BOOLEAN     NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS legal_area      TEXT,
    ADD COLUMN IF NOT EXISTS compression_stats JSONB;

-- ── safety_boundary_checks ───────────────────────────────────────────────────
-- Immutable record of every safety policy check.
-- Backs up the legal boundary gate at Brain step 16.

CREATE TABLE IF NOT EXISTS safety_boundary_checks (
    id              BIGSERIAL PRIMARY KEY,
    trace_id        TEXT,
    user_id         UUID,
    check_name      TEXT        NOT NULL,
    passed          BOOLEAN     NOT NULL,
    failure_reason  TEXT,
    blocked         BOOLEAN     NOT NULL DEFAULT false,
    severity        TEXT        NOT NULL DEFAULT 'medium',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS safety_checks_trace_idx  ON safety_boundary_checks (trace_id);
CREATE INDEX IF NOT EXISTS safety_checks_passed_idx ON safety_boundary_checks (passed, blocked);

-- ── document_facts ───────────────────────────────────────────────────────────
-- Stores facts extracted from uploaded documents.
-- Status must be 'unconfirmed' until user explicitly accepts.
-- GUARDRAIL: extracted_at and confirmed_at are always recorded for audit.

CREATE TABLE IF NOT EXISTS document_facts (
    id              BIGSERIAL PRIMARY KEY,
    upload_id       UUID        NOT NULL,
    case_id         UUID,
    user_id         UUID,
    field_name      TEXT        NOT NULL,
    raw_value       TEXT,
    normalised_value TEXT,
    confidence      FLOAT       NOT NULL DEFAULT 0.0,
    status          TEXT        NOT NULL DEFAULT 'unconfirmed',  -- unconfirmed | confirmed | rejected | corrected
    source_page     INTEGER,
    source_text     TEXT,
    extraction_method TEXT      DEFAULT 'pdf_text',             -- pdf_text | ocr | docx | manual
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at    TIMESTAMPTZ,
    confirmed_by    UUID
);

CREATE INDEX IF NOT EXISTS doc_facts_upload_idx  ON document_facts (upload_id);
CREATE INDEX IF NOT EXISTS doc_facts_case_idx    ON document_facts (case_id);
CREATE INDEX IF NOT EXISTS doc_facts_status_idx  ON document_facts (status);

-- ── wasm_calculations ────────────────────────────────────────────────────────
-- Audit trail for WASM client-side calculations (deadline arithmetic).
-- Proves no sensitive data is sent to server for local calculations.
-- Server always validates the same computation and records any mismatch.

CREATE TABLE IF NOT EXISTS wasm_calculations (
    id                  BIGSERIAL PRIMARY KEY,
    calculation_type    TEXT        NOT NULL,    -- deadline | notice_period | eligibility
    input_hash          TEXT        NOT NULL,    -- SHA256 of inputs (no PII stored)
    client_result       TEXT        NOT NULL,    -- result from WASM/JS fallback
    server_result       TEXT,                    -- server validation result
    results_match       BOOLEAN,
    wasm_loaded         BOOLEAN     NOT NULL DEFAULT false,
    fallback_used       BOOLEAN     NOT NULL DEFAULT false,
    execution_time_ms   FLOAT,
    jurisdiction        TEXT        NOT NULL DEFAULT 'EW',
    rules_version       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS wasm_calc_type_idx ON wasm_calculations (calculation_type);
CREATE INDEX IF NOT EXISTS wasm_calc_hash_idx ON wasm_calculations (input_hash);

-- ── canonical_api_routes ──────────────────────────────────────────────────────
-- Documents the canonical API routes (informational, not operational).
-- Helps admin verify which routes map to which handlers.

CREATE TABLE IF NOT EXISTS api_route_registry (
    id              BIGSERIAL PRIMARY KEY,
    canonical_path  TEXT        NOT NULL UNIQUE,
    handler_name    TEXT        NOT NULL,
    admin_only      BOOLEAN     NOT NULL DEFAULT false,
    enabled         BOOLEAN     NOT NULL DEFAULT true,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO api_route_registry (canonical_path, handler_name, admin_only, description) VALUES
    ('/api/brain/trace',            'brain_trace',          false, 'Brain Algorithm 19-step trace'),
    ('/api/agents',                 'list_agents',          false, 'List registered agents'),
    ('/api/router/test',            'test_router',          true,  'AI Router test (admin only in production)'),
    ('/api/rag/hybrid-search',      'rag_hybrid_search',    true,  'Hybrid search test'),
    ('/api/rag/graph',              'rag_graph',            true,  'Legal graph query'),
    ('/api/kg/entity',              'kg_entity_lookup',     false, 'Knowledge graph entity lookup'),
    ('/api/context/compress',       'context_compress',     true,  'Context compression'),
    ('/api/memory/save',            'memory_save',          false, 'Save case memory (auth required)'),
    ('/api/memory/get',             'memory_get',           false, 'Get case memory (auth required)'),
    ('/api/evaluate',               'evaluate_assessment',  true,  'Legal evaluation AI'),
    ('/api/mcp/tools',              'mcp_tools',            false, 'List MCP connector tools'),
    ('/api/documents/upload',       'documents_upload',     false, 'Document upload'),
    ('/api/documents/facts',        'documents_facts',      false, 'Extracted document facts'),
    ('/api/cache/test',             'cache_test',           true,  'Semantic cache test'),
    ('/api/security/cross-user-test','security_cross_user', false, 'Cross-user isolation verification')
ON CONFLICT (canonical_path) DO NOTHING;
