-- Migration 018  -  lawapp Brain Architecture Tables
-- Creates tables for: brain traces, legal memory, semantic cache,
--                     legal graph nodes/edges, routing decisions,
--                     evaluation results, MCP tool calls.

-- ── brain_traces ────────────────────────────────────────────────────────────
-- Immutable record of every Brain run: agents used, sources, citations,
-- evaluation result, final status. Tamper-resistant (no UPDATE allowed).

CREATE TABLE IF NOT EXISTS brain_traces (
    id              BIGSERIAL PRIMARY KEY,
    trace_id        TEXT NOT NULL UNIQUE,
    user_id         UUID,
    case_id         UUID,
    claim_type      TEXT,
    agents_used     JSONB      NOT NULL DEFAULT '[]',
    rules_count     INTEGER    NOT NULL DEFAULT 0,
    sources_count   INTEGER    NOT NULL DEFAULT 0,
    citations_verified INTEGER NOT NULL DEFAULT 0,
    citations_failed   INTEGER NOT NULL DEFAULT 0,
    evidence_gaps   JSONB      NOT NULL DEFAULT '[]',
    evaluation_passed BOOLEAN,
    final_status    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS brain_traces_user_idx   ON brain_traces (user_id);
CREATE INDEX IF NOT EXISTS brain_traces_case_idx   ON brain_traces (case_id);
CREATE INDEX IF NOT EXISTS brain_traces_status_idx ON brain_traces (final_status);

-- Prevent UPDATE/DELETE on brain_traces (immutable audit)
-- Note: enforced at application layer; for DB-level enforcement
-- add a trigger if the DB user has TRIGGER privilege.

-- ── legal_memory ─────────────────────────────────────────────────────────────
-- Case-isolated memory. user_id + case_id are mandatory.
-- Sensitive fields are stored encrypted (encrypted=true).

CREATE TABLE IF NOT EXISTS legal_memory (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID        NOT NULL,
    case_id     UUID        NOT NULL,
    memory_type TEXT        NOT NULL,   -- case_facts | user_preference | timeline | deadlines | previous_answers | evidence_checklist
    memory_key  TEXT        NOT NULL,
    value       TEXT        NOT NULL,
    encrypted   BOOLEAN     NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, case_id, memory_type, memory_key)
);

CREATE INDEX IF NOT EXISTS legal_memory_user_case_idx ON legal_memory (user_id, case_id);
CREATE INDEX IF NOT EXISTS legal_memory_type_idx      ON legal_memory (memory_type);

-- ── semantic_cache ────────────────────────────────────────────────────────────
-- Generic, non-personal legal explanations only.
-- safe_to_cache=false rows should never exist (blocked at write time).

CREATE TABLE IF NOT EXISTS semantic_cache (
    id             BIGSERIAL PRIMARY KEY,
    cache_key      TEXT        NOT NULL UNIQUE,
    query_text     TEXT        NOT NULL,
    answer         TEXT        NOT NULL,
    jurisdiction   TEXT        NOT NULL DEFAULT 'EW',
    source_version TEXT        NOT NULL,
    safe_to_cache  BOOLEAN     NOT NULL DEFAULT true,
    hit_count      INTEGER     NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS semantic_cache_jurisdiction_idx ON semantic_cache (jurisdiction, source_version);

-- ── legal_nodes ──────────────────────────────────────────────────────────────
-- Nodes in the legal knowledge graph.
-- Each node represents a legal concept, act, section, test, or remedy.

CREATE TABLE IF NOT EXISTS legal_nodes (
    id              BIGSERIAL PRIMARY KEY,
    node_id         TEXT        NOT NULL UNIQUE,
    node_type       TEXT        NOT NULL,   -- legislation_section | claim_type | legal_test | remedy | defence | evidence_type | deadline | procedure
    label           TEXT        NOT NULL,
    description     TEXT,
    jurisdiction    TEXT        NOT NULL DEFAULT 'EW',
    authority_level INTEGER     NOT NULL DEFAULT 5,   -- 1=primary legislation, 5=commentary
    source_ref      TEXT,
    source_url      TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS legal_nodes_type_idx ON legal_nodes (node_type);
CREATE INDEX IF NOT EXISTS legal_nodes_j_idx    ON legal_nodes (jurisdiction);

-- ── legal_edges ──────────────────────────────────────────────────────────────
-- Directed edges in the legal knowledge graph.
-- relationship_type describes how from_node relates to to_node.

CREATE TABLE IF NOT EXISTS legal_edges (
    id                 BIGSERIAL PRIMARY KEY,
    from_node_id       TEXT        NOT NULL REFERENCES legal_nodes (node_id),
    to_node_id         TEXT        NOT NULL REFERENCES legal_nodes (node_id),
    relationship_type  TEXT        NOT NULL,   -- applies_to | requires | leads_to | interprets | extends | reduces | excludes
    weight             FLOAT       NOT NULL DEFAULT 1.0,
    notes              TEXT,
    jurisdiction       TEXT        NOT NULL DEFAULT 'EW',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS legal_edges_from_idx ON legal_edges (from_node_id);
CREATE INDEX IF NOT EXISTS legal_edges_to_idx   ON legal_edges (to_node_id);
CREATE INDEX IF NOT EXISTS legal_edges_rel_idx  ON legal_edges (relationship_type);

-- ── routing_decisions ─────────────────────────────────────────────────────────
-- Log of AI Router decisions for monitoring and tuning.

CREATE TABLE IF NOT EXISTS routing_decisions (
    id              BIGSERIAL PRIMARY KEY,
    trace_id        TEXT        REFERENCES brain_traces (trace_id),
    user_id         UUID,
    claim_type      TEXT,
    selected_path   TEXT        NOT NULL,
    risk_level      TEXT        NOT NULL,
    agents          JSONB       NOT NULL DEFAULT '[]',
    use_llm         BOOLEAN     NOT NULL DEFAULT false,
    evaluation_req  BOOLEAN     NOT NULL DEFAULT true,
    human_review    BOOLEAN     NOT NULL DEFAULT false,
    reason          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS routing_decisions_trace_idx ON routing_decisions (trace_id);
CREATE INDEX IF NOT EXISTS routing_decisions_path_idx  ON routing_decisions (selected_path);

-- ── evaluation_results ────────────────────────────────────────────────────────
-- Results of Legal Evaluation AI checks per assessment.

CREATE TABLE IF NOT EXISTS evaluation_results (
    id              BIGSERIAL PRIMARY KEY,
    trace_id        TEXT        REFERENCES brain_traces (trace_id),
    case_id         UUID,
    user_id         UUID,
    passed          BOOLEAN     NOT NULL,
    failure_reason  TEXT,
    critical_failures INTEGER   NOT NULL DEFAULT 0,
    high_failures   INTEGER     NOT NULL DEFAULT 0,
    checks          JSONB       NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS eval_results_trace_idx ON evaluation_results (trace_id);
CREATE INDEX IF NOT EXISTS eval_results_passed_idx ON evaluation_results (passed);

-- ── mcp_tool_calls ────────────────────────────────────────────────────────────
-- Audit log for MCP connector calls. Every tool call is logged.

CREATE TABLE IF NOT EXISTS mcp_tool_calls (
    id          BIGSERIAL PRIMARY KEY,
    trace_id    TEXT,
    user_id     UUID,
    case_id     UUID,
    tool_name   TEXT        NOT NULL,
    action      TEXT        NOT NULL,
    allowed     BOOLEAN     NOT NULL DEFAULT false,
    consent     BOOLEAN     NOT NULL DEFAULT false,
    result      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS mcp_tool_calls_trace_idx ON mcp_tool_calls (trace_id);
CREATE INDEX IF NOT EXISTS mcp_tool_calls_tool_idx  ON mcp_tool_calls (tool_name);

-- ── Seed legal graph for unfair dismissal ────────────────────────────────────

INSERT INTO legal_nodes (node_id, node_type, label, description, jurisdiction, authority_level, source_ref, source_url)
VALUES
  ('ud_claim',            'claim_type',          'Unfair Dismissal',                 'ERA 1996 Part X  -  right not to be unfairly dismissed',                               'EW', 1, 'ERA 1996 s.94',  'https://www.legislation.gov.uk/ukpga/1996/18/section/94'),
  ('employee_status',     'legal_test',          'Employee Status',                  'Must be an employee (not worker/self-employed)  -  ERA 1996 s.230',                    'EW', 1, 'ERA 1996 s.230', 'https://www.legislation.gov.uk/ukpga/1996/18/section/230'),
  ('qualifying_service',  'legal_test',          'Qualifying Period',                '2 years continuous employment (or day-one rights exception)',                         'EW', 1, 'ERA 1996 s.108', 'https://www.legislation.gov.uk/ukpga/1996/18/section/108'),
  ('dismissal',           'legal_test',          'Fact of Dismissal',                'Actual dismissal, constructive dismissal, or expiry of fixed-term contract',          'EW', 1, 'ERA 1996 s.95',  'https://www.legislation.gov.uk/ukpga/1996/18/section/95'),
  ('fair_reason',         'legal_test',          'Fair Reason for Dismissal',        'Capability, conduct, redundancy, statutory restriction, or SOSR  -  s.98(2)',           'EW', 1, 'ERA 1996 s.98',  'https://www.legislation.gov.uk/ukpga/1996/18/section/98'),
  ('reasonableness_test', 'legal_test',          'Range of Reasonable Responses',    'Was dismissal within band of reasonable responses?  -  s.98(4)',                       'EW', 1, 'ERA 1996 s.98',  'https://www.legislation.gov.uk/ukpga/1996/18/section/98'),
  ('procedure',           'procedure',           'Dismissal Procedure',              'ACAS Code of Practice  -  invite, meeting, appeal. Polkey reduction if not followed.',  'EW', 5, 'ACAS Code',      'https://www.acas.org.uk/acas-code-of-practice-on-disciplinary-and-grievance-procedures'),
  ('acas_ec',             'procedure',           'ACAS Early Conciliation',          'Mandatory before ET1. Pauses limitation period  -  ERA 1996 s.207B',                   'EW', 1, 'ERA 1996 s.207B','https://www.legislation.gov.uk/ukpga/1996/18/section/207B'),
  ('limitation_date',     'deadline',            'ET Limitation Date',               '3 months less one day from EDT (or EC floor). ERA 1996 s.111(2)',                     'EW', 1, 'ERA 1996 s.111', 'https://www.legislation.gov.uk/ukpga/1996/18/section/111'),
  ('basic_award',         'remedy',              'Basic Award',                      'Statutory formula: age × service years × weekly pay cap. ERA 1996 s.119',            'EW', 1, 'ERA 1996 s.119', 'https://www.legislation.gov.uk/ukpga/1996/18/section/119'),
  ('compensatory_award',  'remedy',              'Compensatory Award',               'Loss of earnings, future loss, benefits. Capped at lower of 52 weeks pay or £123,543', 'EW', 1, 'ERA 1996 s.123', 'https://www.legislation.gov.uk/ukpga/1996/18/section/123'),
  ('polkey_reduction',    'defence',             'Polkey Reduction',                 'Award reduced if fair outcome would have been same even with correct procedure',       'EW', 2, 'Polkey v Dayton Services [1988] AC 344', NULL),
  ('contributory_fault',  'defence',             'Contributory Fault',               'Award reduced for claimant conduct contributing to dismissal  -  ERA 1996 s.122/123',   'EW', 1, 'ERA 1996 s.122', 'https://www.legislation.gov.uk/ukpga/1996/18/section/122'),
  ('upw_claim',           'claim_type',          'Unpaid Wages / Unlawful Deduction','ERA 1996 Part II  -  right not to have unlawful deductions from wages',                 'EW', 1, 'ERA 1996 s.13',  'https://www.legislation.gov.uk/ukpga/1996/18/section/13'),
  ('upw_limitation',      'deadline',            'UPW Limitation Date',              '3 months less one day from date of deduction  -  ERA 1996 s.23(2)',                     'EW', 1, 'ERA 1996 s.23',  'https://www.legislation.gov.uk/ukpga/1996/18/section/23')
ON CONFLICT (node_id) DO NOTHING;

-- Edges: unfair dismissal graph
INSERT INTO legal_edges (from_node_id, to_node_id, relationship_type, notes)
VALUES
  ('ud_claim',           'employee_status',     'requires',    'Claimant must be employee, not worker'),
  ('ud_claim',           'qualifying_service',  'requires',    'Must have 2 years service (ERA 1996 s.108)'),
  ('ud_claim',           'dismissal',           'requires',    'Must show fact of dismissal'),
  ('ud_claim',           'limitation_date',     'applies_to',  'Must be presented before limitation date'),
  ('ud_claim',           'acas_ec',             'requires',    'ACAS EC mandatory before ET1'),
  ('dismissal',          'fair_reason',         'leads_to',    'Employer must show fair reason'),
  ('fair_reason',        'reasonableness_test', 'leads_to',    'Tribunal applies range of reasonable responses'),
  ('reasonableness_test','procedure',           'requires',    'Correct procedure expected (ACAS Code)'),
  ('procedure',          'polkey_reduction',    'leads_to',    'If not followed, award may be reduced'),
  ('ud_claim',           'basic_award',         'leads_to',    'If successful, basic award computed'),
  ('ud_claim',           'compensatory_award',  'leads_to',    'If successful, compensatory award computed'),
  ('compensatory_award', 'contributory_fault',  'reduces',     'Claimant conduct can reduce award'),
  -- UPW graph
  ('upw_claim',          'upw_limitation',      'applies_to',  'Must claim within 3 months of deduction'),
  ('upw_claim',          'acas_ec',             'requires',    'ACAS EC mandatory before ET1 for UPW too')
ON CONFLICT DO NOTHING;
