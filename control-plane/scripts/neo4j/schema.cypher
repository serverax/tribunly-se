// Graph RAG Layer v1 - Neo4j schema (constraints + indexes)
// Apply: cypher-shell -u neo4j -p lawapp_dev_only -f schema.cypher
// Dev credentials only. Do not use lawapp_dev_only in production.

// ── Uniqueness constraints ─────────────────────────────────────────────
CREATE CONSTRAINT statute_id IF NOT EXISTS
  FOR (n:Statute) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT section_id IF NOT EXISTS
  FOR (n:Section) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT case_id IF NOT EXISTS
  FOR (n:Case) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT legal_test_id IF NOT EXISTS
  FOR (n:LegalTest) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT rule_id IF NOT EXISTS
  FOR (n:Rule) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT outcome_id IF NOT EXISTS
  FOR (n:Outcome) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT concept_id IF NOT EXISTS
  FOR (n:Concept) REQUIRE n.id IS UNIQUE;

// ── Lookup indexes ───────────────────────────────────────────────────────
CREATE INDEX statute_title IF NOT EXISTS
  FOR (n:Statute) ON (n.title);

CREATE INDEX section_ref IF NOT EXISTS
  FOR (n:Section) ON (n.source_ref);

CREATE INDEX legal_test_label IF NOT EXISTS
  FOR (n:LegalTest) ON (n.label);

CREATE INDEX concept_label IF NOT EXISTS
  FOR (n:Concept) ON (n.label);

CREATE INDEX case_citation IF NOT EXISTS
  FOR (n:Case) ON (n.neutral_citation);

CREATE INDEX node_jurisdiction IF NOT EXISTS
  FOR (n:LegalTest) ON (n.jurisdiction);

// Full-text search for graph search API
CREATE FULLTEXT INDEX legal_graph_search IF NOT EXISTS
  FOR (n:LegalTest|Concept|Section|Case)
  ON EACH [n.label, n.description, n.source_ref, n.neutral_citation];
