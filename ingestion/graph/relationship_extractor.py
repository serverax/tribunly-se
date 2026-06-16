"""LLM graph relationship extraction (local Ollama) with JSON schema validation."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

ALLOWED_RELATIONS = frozenset({
    "AMENDS", "CITES", "INTERPRETS", "APPLIES", "REQUIRES", "EXCEPTION_TO",
})
ALLOWED_ENTITY_TYPES = frozenset({"Act", "Section", "Case", "Guidance", "Concept"})


class RelationshipExtractor:
    """Extract graph proposals from a chunk using local Ollama only."""

    def __init__(self) -> None:
        self.system_prompt = (_PROMPT_DIR / "graph_builder_system.txt").read_text(encoding="utf-8")
        self.user_template = (_PROMPT_DIR / "graph_builder_user.txt").read_text(encoding="utf-8")

    def build_user_prompt(
        self,
        *,
        document_id: str,
        chunk_id: str,
        source_type: str,
        authority_ref: str,
        chunk_text: str,
    ) -> str:
        return self.user_template.format(
            document_id=document_id,
            chunk_id=chunk_id,
            source_type=source_type,
            authority_ref=authority_ref,
            chunk_text=chunk_text[:8000],
        )

    def extract(
        self,
        *,
        document_id: str,
        chunk_id: str,
        source_type: str,
        authority_ref: str,
        chunk_text: str,
    ) -> dict[str, Any]:
        raw = self._call_ollama(
            self.build_user_prompt(
                document_id=document_id,
                chunk_id=chunk_id,
                source_type=source_type,
                authority_ref=authority_ref,
                chunk_text=chunk_text,
            )
        )
        return self.validate_payload(raw)

    def validate_payload(self, raw: str) -> dict[str, Any]:
        """Parse and validate extractor JSON. Fail closed on invalid shape."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            return {"entities": [], "edges": [], "rule_candidates": [], "error": f"invalid_json:{exc}"}

        entities = data.get("entities") or []
        edges = data.get("edges") or []
        rules = data.get("rule_candidates") or []

        valid_entities = []
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            if ent.get("type") not in ALLOWED_ENTITY_TYPES:
                continue
            if not ent.get("id") or not ent.get("label"):
                continue
            valid_entities.append(ent)

        valid_edges = []
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            if edge.get("relation") not in ALLOWED_RELATIONS:
                continue
            if not edge.get("from_id") or not edge.get("to_id"):
                continue
            if not edge.get("evidence_span"):
                continue
            valid_edges.append(edge)

        valid_rules = []
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            if not rule.get("rule_key") or not rule.get("authority_ref"):
                continue
            valid_rules.append(rule)

        return {
            "entities": valid_entities,
            "edges": valid_edges,
            "rule_candidates": valid_rules,
        }

    def _call_ollama(self, user_prompt: str) -> str:
        if os.getenv("ALLOW_EXTERNAL_LLM", "false").lower() in ("1", "true", "yes"):
            logger.warning("ALLOW_EXTERNAL_LLM=true but extractor uses Ollama only by policy")
        from backend.core.inference_policy import assert_no_external_llm_enabled, get_ollama_base_url
        assert_no_external_llm_enabled()
        import httpx

        base = get_ollama_base_url().rstrip("/")
        model = os.getenv("LAWAPP_OLLAMA_MODEL", "qwen2.5:3b-instruct-q6_K")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
        }
        try:
            resp = httpx.post(f"{base}/api/chat", json=payload, timeout=120.0)
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "{}")
        except Exception as exc:
            logger.warning("Ollama extraction unavailable: %s", exc)
            return json.dumps({"entities": [], "edges": [], "rule_candidates": []})
