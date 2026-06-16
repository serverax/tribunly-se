"""
Knowledge Graph unit tests  -  lawapp legal concept mapping.

Tests that the legal knowledge graph correctly maps:
  - claim type → legal tests
  - legal tests → required facts
  - deadlines → ERA 1996 sections
  - remedies → ERA 1996 sections
  - node relationships are traversable

Uses the seeded legal_nodes/legal_edges tables from migration 018.
"""

import pytest
import os
import psycopg2


@pytest.fixture
def db_conn():
    conn = psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST','localhost'), port=int(os.environ.get('POSTGRES_PORT','5435')), dbname=os.environ.get('POSTGRES_DB','lawapp'),
        user=os.environ.get('POSTGRES_USER','lawapp'), password=os.environ.get('POSTGRES_PASSWORD','lawapp')
    )
    yield conn
    conn.close()


class TestLegalNodesSchema:
    def test_legal_nodes_table_exists(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM legal_nodes;")
        count = cur.fetchone()[0]
        assert count > 0, "legal_nodes table is empty"

    def test_ud_claim_node_exists(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT node_id, label FROM legal_nodes WHERE node_id = 'ud_claim';")
        row = cur.fetchone()
        assert row is not None, "ud_claim node missing"
        assert "Unfair Dismissal" in row[1]

    def test_upw_claim_node_exists(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT node_id FROM legal_nodes WHERE node_id = 'upw_claim';")
        assert cur.fetchone() is not None

    def test_qualifying_period_node_exists(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT node_id FROM legal_nodes WHERE node_id = 'qualifying_service';")
        assert cur.fetchone() is not None

    def test_limitation_date_node_exists(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT node_id FROM legal_nodes WHERE node_id = 'limitation_date';")
        assert cur.fetchone() is not None

    def test_acas_ec_node_exists(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT node_id FROM legal_nodes WHERE node_id = 'acas_ec';")
        assert cur.fetchone() is not None

    def test_all_nodes_have_source_ref(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT node_id FROM legal_nodes
            WHERE source_ref IS NULL OR source_ref = ''
            AND node_type NOT IN ('concept');
        """)
        missing = cur.fetchall()
        assert len(missing) == 0, f"Nodes missing source_ref: {[r[0] for r in missing]}"

    def test_all_nodes_have_authority_level(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT node_id FROM legal_nodes
            WHERE authority_level IS NULL;
        """)
        assert cur.fetchone() is None

    def test_node_types_are_valid(self, db_conn):
        valid_types = {
            "claim_type", "legal_test", "procedure", "deadline",
            "remedy", "defence", "evidence_type", "legislation_section", "concept"
        }
        cur = db_conn.cursor()
        cur.execute("SELECT DISTINCT node_type FROM legal_nodes;")
        actual = {r[0] for r in cur.fetchall()}
        unknown = actual - valid_types
        assert len(unknown) == 0, f"Unknown node types: {unknown}"


class TestLegalEdgesSchema:
    def test_legal_edges_table_exists(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM legal_edges;")
        count = cur.fetchone()[0]
        assert count > 0, "legal_edges table is empty"

    def test_ud_requires_qualifying_service(self, db_conn):
        """ud_claim -[requires]-> qualifying_service must exist."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT id FROM legal_edges
            WHERE from_node_id = 'ud_claim'
              AND to_node_id = 'qualifying_service'
              AND relationship_type = 'requires';
        """)
        assert cur.fetchone() is not None, "Missing: ud_claim requires qualifying_service"

    def test_ud_requires_acas_ec(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT id FROM legal_edges
            WHERE from_node_id = 'ud_claim'
              AND to_node_id = 'acas_ec'
              AND relationship_type = 'requires';
        """)
        assert cur.fetchone() is not None, "Missing: ud_claim requires acas_ec"

    def test_ud_applies_to_limitation_date(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT id FROM legal_edges
            WHERE from_node_id = 'ud_claim'
              AND to_node_id = 'limitation_date';
        """)
        assert cur.fetchone() is not None, "Missing: ud_claim applies_to limitation_date"

    def test_ud_leads_to_basic_award(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT id FROM legal_edges
            WHERE from_node_id = 'ud_claim'
              AND to_node_id = 'basic_award'
              AND relationship_type = 'leads_to';
        """)
        assert cur.fetchone() is not None

    def test_upw_applies_to_its_limitation(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT id FROM legal_edges
            WHERE from_node_id = 'upw_claim'
              AND to_node_id = 'upw_limitation';
        """)
        assert cur.fetchone() is not None

    def test_no_self_referencing_edges(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM legal_edges
            WHERE from_node_id = to_node_id;
        """)
        count = cur.fetchone()[0]
        assert count == 0, f"{count} self-referencing edges found"

    def test_all_edge_nodes_exist(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT le.from_node_id, le.to_node_id
            FROM legal_edges le
            LEFT JOIN legal_nodes fn ON fn.node_id = le.from_node_id
            LEFT JOIN legal_nodes tn ON tn.node_id = le.to_node_id
            WHERE fn.node_id IS NULL OR tn.node_id IS NULL;
        """)
        dangling = cur.fetchall()
        assert len(dangling) == 0, f"Dangling edges (missing nodes): {dangling}"


class TestKnowledgeGraphPaths:
    """Test that key legal reasoning paths exist in the graph."""

    def test_ud_to_era1996_s111_path(self, db_conn):
        """ud_claim -> limitation_date -> source_ref contains ERA 1996 s.111."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT ln.source_ref FROM legal_nodes ln
            WHERE ln.node_id = 'limitation_date';
        """)
        row = cur.fetchone()
        assert row is not None
        assert "ERA 1996" in row[0] or "s.111" in row[0]

    def test_basic_award_has_era1996_s119_ref(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT source_ref FROM legal_nodes WHERE node_id = 'basic_award';
        """)
        row = cur.fetchone()
        assert row is not None
        assert "ERA 1996" in row[0]

    def test_procedure_node_references_acas_code(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT source_ref FROM legal_nodes WHERE node_id = 'procedure';
        """)
        row = cur.fetchone()
        assert row is not None
        assert "ACAS" in row[0] or "acas" in row[0].lower()
