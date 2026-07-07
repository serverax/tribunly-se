-- 088_legal_node_type_canonical.sql
-- Normalize extractor/Neo4j-style labels into the Postgres legal_nodes taxonomy.

BEGIN;

UPDATE legal_nodes
   SET node_type = 'legislation_section'
 WHERE node_type IN ('Section', 'section', 'Statute', 'statute', 'Act', 'act');

UPDATE legal_nodes
   SET node_type = 'procedure'
 WHERE node_type IN ('Guidance', 'guidance');

UPDATE legal_nodes
   SET node_type = 'concept'
 WHERE node_type NOT IN (
    'claim_type', 'legal_test', 'procedure', 'deadline',
    'remedy', 'defence', 'evidence_type', 'legislation_section', 'concept'
 );

COMMIT;
