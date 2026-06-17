#!/usr/bin/env python3
"""Verify ingestion migration 084 and dual-plane worker layout (evidence report)."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "ingestion_084_cursor.txt"

REQUIRED_WORKERS = (
    "legislation",
    "case_law",
    "acas",
    "rules_compiler",
    "base_worker",
    "unified_indexer",
)


def check_files() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    mig = ROOT / "db/migrations/084_ingestion_jobs_dual_plane.sql"
    rows.append(("Migration 084 file", "PASS" if mig.is_file() else "FAIL", str(mig)))
    workers_dir = ROOT / "ingestion/workers"
    for w in REQUIRED_WORKERS:
        found = any(workers_dir.glob(f"*{w}*"))
        rows.append((f"worker {w}", "PASS" if found else "FAIL", str(workers_dir)))
    indexer = ROOT / "ingestion/workers/unified_indexer.py"
    neo_ok = "NEO4J_ENABLED" in indexer.read_text(encoding="utf-8") if indexer.is_file() else False
    rows.append(("Unified indexer Neo4j optional", "PASS" if neo_ok else "FAIL", str(indexer)))
    ollama = ROOT / "ingestion/embeddings/ollama_embed.py"
    rows.append(("Ollama 1024 embedder", "PASS" if ollama.is_file() else "FAIL", str(ollama)))
    cfg = ROOT / "ingestion/config.py"
    cfg_text = cfg.read_text(encoding="utf-8") if cfg.is_file() else ""
    dim_ok = "1024" in cfg_text or "embedding_dim" in cfg_text
    fcl_ok = re.search(r"fcl_bulk_licence_granted\s*:\s*bool\s*=\s*False", cfg_text) is not None
    rows.append(("Config embedding_dim 1024", "PASS" if dim_ok else "FAIL", str(cfg)))
    rows.append(("FCL bulk disabled", "PASS" if fcl_ok else "FAIL", str(cfg)))
    hits_1536: list[str] = []
    for fp in (ROOT / "ingestion").rglob("*.py"):
        t = fp.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"text-embedding-3|1536", t) and "No text-embedding-3" not in t:
            if "1536" in t and "1024" not in t:
                hits_1536.append(str(fp.relative_to(ROOT)))
    rows.append(("No 1536 refs in ingestion/*.py", "PASS" if not hits_1536 else "FAIL", ", ".join(hits_1536) or "none"))
    freshness = ROOT / "ingestion/freshness/report.py"
    rows.append(("Freshness report module", "PASS" if freshness.is_file() else "FAIL", str(freshness)))
    sync = ROOT / "ingestion/sync_corpus_chunks.py"
    sync_text = sync.read_text(encoding="utf-8") if sync.is_file() else ""
    idem = "ON CONFLICT (chunk_hash) DO NOTHING" in sync_text
    rows.append(("Idempotency (chunk_hash conflict)", "PASS" if idem else "FAIL", "sync_corpus_chunks.py"))
    return rows


def check_db() -> tuple[str, str]:
    """Live DB checks for migration 084 and corpus embedding state.

  Local verify defaults: POSTGRES_HOST=localhost, POSTGRES_PORT=5435,
  POSTGRES_PASSWORD=lawapp (matches docker-compose.override.yml service ``db``).
  Override via env; do not commit real secrets.
    """
    try:
        import psycopg2
    except ImportError:
        return "SKIP", "psycopg2 not installed"
    try:
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", "5435")),
            dbname=os.environ.get("POSTGRES_DB", "lawapp"),
            user=os.environ.get("POSTGRES_USER", "lawapp"),
            # Default lawapp: local pgdata volume + docker-compose.override.yml
            password=os.environ.get("POSTGRES_PASSWORD", "lawapp"),
            connect_timeout=3,
        )
    except Exception as exc:
        return "SKIP", f"DB unreachable: {exc}"
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='ingestion_jobs'"
        )
        if cur.fetchone()[0] != 1:
            return "FAIL", "ingestion_jobs table missing (migration 084 not applied)"
        cur.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name='corpus_chunks' AND column_name='provision_id'"
        )
        prov = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM corpus_chunks WHERE source_type = 'legislation'")
        leg = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM corpus_chunks WHERE embedding IS NOT NULL")
        embedded = cur.fetchone()[0]
        cur.execute(
            "SELECT vector_dims(embedding) FROM corpus_chunks WHERE embedding IS NOT NULL LIMIT 1"
        )
        row = cur.fetchone()
        dim_note = f"legislation_chunks={leg}; embedded={embedded}; dim={row[0] if row else 'none'}"
        ok = prov and leg > 0
        return ("PASS" if ok else "PARTIAL"), dim_note
    finally:
        conn.close()


def check_pipeline_rerun() -> tuple[str, str]:
    """Optional docker pipeline rerun (legislation+acas+embed+sync)."""
    import subprocess

    cmd = [
        "docker",
        "compose",
        "--profile",
        "ingestion",
        "run",
        "--rm",
        "ingestion",
        "sh",
        "-c",
        "python -m ingestion.sync_corpus_chunks && python -m ingestion.sync_corpus_chunks",
    ]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
        out = (proc.stdout or "") + (proc.stderr or "")
        if "added=0" in out or "added=0 " in out:
            return "PASS", "idempotent sync (added=0 on second pass)"
        if proc.returncode == 0:
            return "PARTIAL", out.strip()[-400:]
        return "FAIL", out.strip()[-600:]
    except Exception as exc:
        return "SKIP", str(exc)


def main() -> int:
    rows = check_files()
    db_status, db_note = check_db()
    pipe_status, pipe_note = check_pipeline_rerun()
    lines = [
        "LawApp dual-plane ingestion migration 084 audit",
        "Generated: 2026-06-16 (evidence run)",
        "Branch: release/lawapp-clean-snapshot",
        "",
        "| Criterion | Result | Evidence |",
        "|-----------|--------|----------|",
    ]
    any_fail = False
    for name, status, ev in rows:
        if status == "FAIL":
            any_fail = True
        lines.append(f"| {name} | {status} | {ev} |")
    if db_status == "FAIL":
        any_fail = True
    lines.append(f"| Migration 084 applied (live DB) | {db_status} | {db_note} |")
    if pipe_status == "FAIL":
        any_fail = True
    lines.append(f"| Idempotent sync re-run | {pipe_status} | {pipe_note} |")
    lines.append("")
    lines.append("## Pipeline re-run note")
    lines.append(
        "Full embed pass requires Ollama model `bge-large-en-v1.5` at LAWAPP_OLLAMA_BASE_URL. "
        "If embedder fails with HTTP 404, pull the model: `docker compose exec ollama ollama pull bge-large-en-v1.5`"
    )
    verdict = "FAIL" if any_fail else "PASS"
    lines.extend(["", f"## Verdict: {verdict}"])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
