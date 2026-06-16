-- 078_knowledge_schema_stubs.sql
-- Owner decision Q1/Q7: knowledge.* schema in shared lawapp DB.
-- Additive stubs for provision/module/legal_source governance tables.
-- corpus_chunks.provision_id prepares dual-write cutover (not yet authoritative).

BEGIN;

CREATE SCHEMA IF NOT EXISTS knowledge;

-- 16 canonical module codes (deployment work order)
CREATE TABLE IF NOT EXISTS knowledge.module (
    id              SMALLSERIAL PRIMARY KEY,
    code            TEXT NOT NULL UNIQUE,
    label           TEXT NOT NULL,
    coverage_status TEXT NOT NULL DEFAULT 'unavailable'
                    CHECK (coverage_status IN ('production','partial','unavailable')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO knowledge.module (code, label, coverage_status) VALUES
('UNFAIR_DISMISSAL', 'Unfair dismissal', 'production'),
('CONSTRUCTIVE_DISMISSAL', 'Constructive dismissal', 'partial'),
('WRONGFUL_DISMISSAL', 'Wrongful dismissal', 'unavailable'),
('REDUNDANCY', 'Redundancy', 'unavailable'),
('DISCRIMINATION', 'Discrimination', 'unavailable'),
('PREGNANCY_MATERNITY', 'Pregnancy and maternity', 'unavailable'),
('WHISTLEBLOWING', 'Whistleblowing', 'unavailable'),
('WAGES_HOLIDAY', 'Wages and holiday pay', 'production'),
('WORKING_TIME', 'Working time', 'unavailable'),
('FLEXIBLE_WORKING', 'Flexible working', 'unavailable'),
('TUPE', 'TUPE transfers', 'unavailable'),
('EMPLOYMENT_STATUS', 'Employment status', 'partial'),
('GRIEVANCE_DISCIPLINARY', 'Grievance and disciplinary', 'partial'),
('SETTLEMENT', 'Settlement agreements', 'unavailable'),
('DATA_PROTECTION', 'Data protection at work', 'unavailable'),
('ATYPICAL_WORKERS', 'Atypical workers', 'unavailable')
ON CONFLICT (code) DO UPDATE SET
    label = EXCLUDED.label,
    updated_at = now();

CREATE TABLE IF NOT EXISTS knowledge.legal_source (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    authority_key       TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    source_url          TEXT,
    licence_name        TEXT,
    licence_confirmed   BOOLEAN NOT NULL DEFAULT false,
    bulk_ingestion_allowed BOOLEAN NOT NULL DEFAULT false,
    gate_env_var        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge.provision (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_source_id     UUID NOT NULL REFERENCES knowledge.legal_source(id),
    module_id           SMALLINT REFERENCES knowledge.module(id),
    authority_ref       TEXT NOT NULL,
    title               TEXT,
    body_text           TEXT NOT NULL,
    effective_from      DATE,
    effective_to        DATE,
    is_prospective      BOOLEAN NOT NULL DEFAULT false,
    content_hash        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (legal_source_id, authority_ref, effective_from)
);

CREATE INDEX IF NOT EXISTS provision_module_idx ON knowledge.provision (module_id);
CREATE INDEX IF NOT EXISTS provision_effective_idx ON knowledge.provision (effective_from, effective_to);

-- Map 24 employment_modules keys to 16 canonical modules (owner Q3)
CREATE TABLE IF NOT EXISTS knowledge.employment_module_map (
    employment_module_key TEXT NOT NULL REFERENCES employment_modules(module_key),
    module_id             SMALLINT NOT NULL REFERENCES knowledge.module(id),
    subtopic_tags         TEXT[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (employment_module_key, module_id)
);

INSERT INTO knowledge.employment_module_map (employment_module_key, module_id, subtopic_tags) VALUES
('unfair_dismissal', (SELECT id FROM knowledge.module WHERE code = 'UNFAIR_DISMISSAL'), '{}'),
('constructive_dismissal', (SELECT id FROM knowledge.module WHERE code = 'CONSTRUCTIVE_DISMISSAL'), '{}'),
('wrongful_dismissal', (SELECT id FROM knowledge.module WHERE code = 'WRONGFUL_DISMISSAL'), '{}'),
('redundancy', (SELECT id FROM knowledge.module WHERE code = 'REDUNDANCY'), '{}'),
('discrimination', (SELECT id FROM knowledge.module WHERE code = 'DISCRIMINATION'), '{}'),
('pregnancy_maternity_discrimination', (SELECT id FROM knowledge.module WHERE code = 'PREGNANCY_MATERNITY'), '{discrimination}'),
('equal_pay', (SELECT id FROM knowledge.module WHERE code = 'DISCRIMINATION'), '{equal_pay}'),
('whistleblowing', (SELECT id FROM knowledge.module WHERE code = 'WHISTLEBLOWING'), '{}'),
('health_and_safety', (SELECT id FROM knowledge.module WHERE code = 'WHISTLEBLOWING'), '{health_safety}'),
('trade_union_rights', (SELECT id FROM knowledge.module WHERE code = 'GRIEVANCE_DISCIPLINARY'), '{trade_union}'),
('flexible_working', (SELECT id FROM knowledge.module WHERE code = 'FLEXIBLE_WORKING'), '{}'),
('maternity_rights', (SELECT id FROM knowledge.module WHERE code = 'PREGNANCY_MATERNITY'), '{maternity}'),
('paternity_rights', (SELECT id FROM knowledge.module WHERE code = 'PREGNANCY_MATERNITY'), '{paternity}'),
('parental_leave', (SELECT id FROM knowledge.module WHERE code = 'PREGNANCY_MATERNITY'), '{parental}'),
('shared_parental_leave', (SELECT id FROM knowledge.module WHERE code = 'PREGNANCY_MATERNITY'), '{shared_parental}'),
('holiday_pay', (SELECT id FROM knowledge.module WHERE code = 'WAGES_HOLIDAY'), '{holiday}'),
('working_time', (SELECT id FROM knowledge.module WHERE code = 'WORKING_TIME'), '{}'),
('national_minimum_wage', (SELECT id FROM knowledge.module WHERE code = 'WAGES_HOLIDAY'), '{nmw}'),
('part_time_workers', (SELECT id FROM knowledge.module WHERE code = 'ATYPICAL_WORKERS'), '{part_time}'),
('fixed_term_workers', (SELECT id FROM knowledge.module WHERE code = 'ATYPICAL_WORKERS'), '{fixed_term}'),
('agency_workers', (SELECT id FROM knowledge.module WHERE code = 'ATYPICAL_WORKERS'), '{agency}'),
('tupe', (SELECT id FROM knowledge.module WHERE code = 'TUPE'), '{}'),
('employment_contracts', (SELECT id FROM knowledge.module WHERE code = 'EMPLOYMENT_STATUS'), '{contract}'),
('unpaid_wages', (SELECT id FROM knowledge.module WHERE code = 'WAGES_HOLIDAY'), '{unpaid_wages}')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS knowledge.answer_candidate (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id           SMALLINT REFERENCES knowledge.module(id),
    question_hash       TEXT NOT NULL,
    answer_text         TEXT NOT NULL,
    cited_provision_ids UUID[] NOT NULL DEFAULT '{}',
    auto_check_score    NUMERIC,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','rejected')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at         TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS knowledge.curated_answer (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id           SMALLINT REFERENCES knowledge.module(id),
    question_hash       TEXT NOT NULL,
    answer_text         TEXT NOT NULL,
    cited_provision_ids UUID[] NOT NULL DEFAULT '{}',
    effective_from      DATE,
    effective_to        DATE,
    promoted_from_id    UUID REFERENCES knowledge.answer_candidate(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dual-write prep: corpus_chunks may reference provision (nullable until backfill)
ALTER TABLE corpus_chunks
    ADD COLUMN IF NOT EXISTS provision_id UUID REFERENCES knowledge.provision(id);

CREATE INDEX IF NOT EXISTS corpus_chunks_provision_idx
    ON corpus_chunks (provision_id)
    WHERE provision_id IS NOT NULL;

COMMIT;
