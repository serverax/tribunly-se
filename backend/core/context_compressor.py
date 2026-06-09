"""
Context Compressor — lawapp Brain Step 13.

Compresses the retrieved legal context bundle before passing it to the model.
This reduces token count while preserving legal substance.

GUARDRAIL: No citation (cite + url) may be removed during compression.
GUARDRAIL: No rule_key reference may be dropped.
GUARDRAIL: Compression ratio is recorded for every call (audit trail).

The compressor applies three passes:
  1. Rule deduplication — deduplicate rules with identical rule_key (keep first)
  2. Authority truncation — trim verbose text fields; preserve cite, url, type
  3. Context summary — build a compact string representation for the model prompt

Token estimation: rough approximation (char_count / 4) matching common LLM
tokeniser behaviour for English text.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_MAX_AUTHORITY_TEXT_CHARS = 400   # max chars retained per authority text field
_MAX_RULES_PER_KEY = 1            # deduplicate rules with same rule_key


# ── Public API ────────────────────────────────────────────────────────────────

def compress_bundle(
    exact_rules: list[dict],
    authorities: list[dict],
    trace_id: str | None = None,
) -> dict:
    """
    Compress a retrieval bundle for the model context window.

    Args:
        exact_rules:  list of rule dicts from the rules table
        authorities:  list of authority dicts from the retrieval layer
        trace_id:     brain trace ID for audit logging (optional)

    Returns:
        {
          "rules":            deduplicated rule list (all rule_keys preserved),
          "authorities":      truncated authority list (all cites/urls preserved),
          "citations":        list[str] — every cite reference (guaranteed complete),
          "context_text":     compact string for model prompt injection,
          "stats": {
            "rules_in":        int,
            "rules_out":       int,
            "authorities_in":  int,
            "authorities_out": int,
            "tokens_in":       int,   (estimated)
            "tokens_out":      int,   (estimated)
            "compression_ratio": float,
            "citations_preserved": int,
          }
        }
    """
    rules_in = len(exact_rules)
    auths_in = len(authorities)

    # ── Pass 1: Rule deduplication ────────────────────────────────────────────
    seen_keys: set[str] = set()
    deduped_rules: list[dict] = []
    for rule in exact_rules:
        key = rule.get("rule_key", "")
        if key not in seen_keys:
            seen_keys.add(key)
            deduped_rules.append(rule)
        # Duplicate rule_key — skip but do NOT drop the key from seen_keys

    # ── Pass 2: Authority truncation (preserve cite + url) ───────────────────
    truncated_auths: list[dict] = []
    all_citations: list[str] = []
    for auth in authorities:
        cite = auth.get("cite") or auth.get("title") or ""
        url = auth.get("url") or auth.get("source_url") or ""
        if cite:
            all_citations.append(cite)

        compressed = {
            "cite":  cite,
            "url":   url,
            "type":  auth.get("type", "unknown"),
        }
        # Preserve short text; truncate only long text fields
        for field in ("text", "excerpt", "summary", "description"):
            raw = auth.get(field)
            if raw:
                compressed[field] = (raw[:_MAX_AUTHORITY_TEXT_CHARS] + "…"
                                     if len(raw) > _MAX_AUTHORITY_TEXT_CHARS
                                     else raw)
                break  # only include the first available text field

        truncated_auths.append(compressed)

    # ── Pass 3: Build compact context string ──────────────────────────────────
    lines: list[str] = []

    if deduped_rules:
        lines.append("RULES ENGINE:")
        for r in deduped_rules:
            key = r.get("rule_key", "?")
            val = r.get("value_text") or r.get("value_numeric") or "?"
            ref = r.get("authority_ref", "")
            lines.append(f"  {key}: {val} [{ref}]")

    if truncated_auths:
        lines.append("LEGAL AUTHORITIES:")
        for a in truncated_auths:
            cite_str = a["cite"] or a.get("url", "?")
            text_str = a.get("text") or a.get("excerpt") or a.get("summary") or ""
            entry = f"  [{a['type']}] {cite_str}"
            if text_str:
                entry += f" — {text_str[:200]}"
            lines.append(entry)

    context_text = "\n".join(lines)

    # ── Token estimation (char / 4) ───────────────────────────────────────────
    raw_text = (
        " ".join(str(r) for r in exact_rules) +
        " ".join(str(a) for a in authorities)
    )
    tokens_in  = max(1, len(raw_text) // 4)
    tokens_out = max(1, len(context_text) // 4)
    ratio      = round(tokens_out / tokens_in, 3)

    stats = {
        "rules_in":            rules_in,
        "rules_out":           len(deduped_rules),
        "authorities_in":      auths_in,
        "authorities_out":     len(truncated_auths),
        "tokens_in":           tokens_in,
        "tokens_out":          tokens_out,
        "compression_ratio":   ratio,
        "citations_preserved": len(all_citations),
    }

    # ── Audit log (non-fatal) ─────────────────────────────────────────────────
    _log_compression(trace_id, stats)

    logger.debug(
        "Context compressed: rules %d→%d, auths %d→%d, tokens %d→%d (%.2fx)",
        rules_in, len(deduped_rules),
        auths_in, len(truncated_auths),
        tokens_in, tokens_out, ratio,
    )

    return {
        "rules":        deduped_rules,
        "authorities":  truncated_auths,
        "citations":    all_citations,
        "context_text": context_text,
        "stats":        stats,
    }


def _log_compression(trace_id: str | None, stats: dict) -> None:
    """Write compression metrics to context_compression_log. Fails silently."""
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO context_compression_log (
                        trace_id, original_tokens, compressed_tokens,
                        citations_preserved, rules_preserved, compression_ratio
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        trace_id,
                        stats["tokens_in"],
                        stats["tokens_out"],
                        stats["citations_preserved"],
                        stats["rules_out"],
                        stats["compression_ratio"],
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("context_compression_log write skipped: %s", exc)
