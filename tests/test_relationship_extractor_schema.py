"""Schema validation tests for graph relationship extractor."""

from __future__ import annotations

import json

from ingestion.graph.relationship_extractor import RelationshipExtractor


def test_validate_payload_accepts_well_formed_json():
    ext = RelationshipExtractor()
    raw = json.dumps({
        "entities": [{"id": "sec-98", "type": "Section", "label": "ERA s.98", "authority_ref": "ERA 1996 s.98"}],
        "edges": [{
            "from_id": "sec-98",
            "to_id": "sec-111",
            "relation": "REQUIRES",
            "evidence_span": "time limit in section 111",
        }],
        "rule_candidates": [{
            "rule_key": "unfair_dismissal.time_limit_months",
            "claim_type": "unfair_dismissal",
            "value_text": "3",
            "authority_ref": "ERA 1996 s.111",
            "confidence": 0.9,
        }],
    })
    result = ext.validate_payload(raw)
    assert len(result["entities"]) == 1
    assert len(result["edges"]) == 1
    assert len(result["rule_candidates"]) == 1


def test_validate_payload_rejects_invalid_relation():
    ext = RelationshipExtractor()
    raw = json.dumps({
        "entities": [{"id": "a", "type": "Section", "label": "A", "authority_ref": "A"}],
        "edges": [{"from_id": "a", "to_id": "b", "relation": "INVENTED", "evidence_span": "x"}],
        "rule_candidates": [],
    })
    result = ext.validate_payload(raw)
    assert result["edges"] == []


def test_validate_payload_handles_markdown_fenced_json():
    ext = RelationshipExtractor()
    raw = '```json\n{"entities":[],"edges":[],"rule_candidates":[]}\n```'
    result = ext.validate_payload(raw)
    assert result["entities"] == []
