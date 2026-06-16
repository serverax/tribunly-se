"""Dual-write indexer tests with mocked Neo4j."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ingestion.workers.unified_indexer import UnifiedIndexer


@patch.dict("os.environ", {"NEO4J_ENABLED": "true"})
@patch("ingestion.workers.unified_indexer.UnifiedIndexer._write_postgres", return_value=True)
@patch("ingestion.workers.unified_indexer.UnifiedIndexer._queue_proposals", return_value=1)
@patch("ingestion.workers.base_worker.RedisQueue.enqueue", return_value="job-1")
@patch("ingestion.graph.neo4j_batch_writer.Neo4jBatchWriter")
def test_unified_indexer_dual_write_neo4j_enabled(mock_writer_cls, _mock_rq, _mock_prop, _mock_pg):
    writer = MagicMock()
    writer.write_batch.return_value = True
    mock_writer_cls.return_value = writer

    indexer = UnifiedIndexer()
    assert indexer.neo4j_enabled is True

    result = indexer.index_chunk(
        document_id="doc-1",
        chunk_id="doc-1#0",
        body_text="Section 98 ERA 1996",
        source_type="legislation",
        source_url="https://example.test/1",
        authority_ref="ERA 1996 s.98",
        graph_entities=[{"id": "sec-98", "type": "Section", "label": "s.98", "authority_ref": "ERA 1996 s.98"}],
        graph_edges=[],
        rule_candidates=[{"rule_key": "test.rule", "authority_ref": "ERA 1996 s.98"}],
    )
    assert result["postgres_ok"] is True
    assert result["neo4j_ok"] is True
    writer.write_batch.assert_called_once()


@patch.dict("os.environ", {"NEO4J_ENABLED": "false"})
@patch("ingestion.workers.unified_indexer.UnifiedIndexer._write_postgres", return_value=True)
@patch("ingestion.workers.unified_indexer.UnifiedIndexer._write_postgres_graph", return_value=True)
@patch("ingestion.workers.base_worker.RedisQueue.enqueue", return_value="job-1")
def test_unified_indexer_postgres_graph_when_neo4j_disabled(_mock_rq, _mock_graph, _mock_pg):
    indexer = UnifiedIndexer()
    result = indexer.index_chunk(
        document_id="doc-2",
        chunk_id="doc-2#0",
        body_text="ACAS guidance text",
        source_type="acas_guidance",
        source_url="https://acas.org.uk/test",
        authority_ref="ACAS dismissal",
        graph_entities=[{"id": "g1", "type": "Guidance", "label": "G", "authority_ref": "ACAS"}],
    )
    assert result["postgres_ok"] is True
    assert result["postgres_graph_ok"] is True
    assert result["neo4j_enabled"] is False
    assert result["neo4j_ok"] is False


@patch.dict("os.environ", {"NEO4J_ENABLED": "false"})
@patch("ingestion.workers.unified_indexer.UnifiedIndexer._write_postgres", return_value=True)
@patch("ingestion.workers.base_worker.RedisQueue.enqueue", return_value="job-1")
def test_unified_indexer_postgres_only_when_neo4j_disabled(_mock_rq, _mock_pg):
    indexer = UnifiedIndexer()
    result = indexer.index_chunk(
        document_id="doc-2",
        chunk_id="doc-2#0",
        body_text="ACAS guidance text",
        source_type="acas_guidance",
        source_url="https://acas.org.uk/test",
        authority_ref="ACAS dismissal",
        graph_entities=[{"id": "g1", "type": "Guidance", "label": "G", "authority_ref": "ACAS"}],
    )
    assert result["postgres_ok"] is True
    assert result["neo4j_enabled"] is False
    assert result["neo4j_ok"] is False
