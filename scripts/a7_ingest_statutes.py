#!/usr/bin/env python3
"""A7 full UK employment statute spine ingestion.

Reads the verified manifest at reports/a7_statute_manifest.json,
fetches each Act/SI data.xml from legislation.gov.uk, parses CLML,
inserts into legislation + corpus_chunks with 1024-dim embeddings.
Also ingests ACAS guidance into acas_guidance + corpus_chunks.

OGL sources only. No Find Case Law requests.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Force unbuffered stdout
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ---------------------------------------------------------------------------
# DB connection (reuse the container's ingestion.db module)
# ---------------------------------------------------------------------------

def get_conn():
    try:
        from ingestion.db import get_connection
        return get_connection()
    except ImportError:
        import psycopg2
        return psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", os.environ.get("DB_HOST", "db")),
            port=int(os.environ.get("POSTGRES_PORT", os.environ.get("DB_PORT", "5432"))),
            dbname=os.environ.get("POSTGRES_DB", "lawapp"),
            user=os.environ.get("POSTGRES_USER", "lawapp"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
        )


# ---------------------------------------------------------------------------
# Ollama embeddings (1024-dim bge-large-en-v1.5)
# ---------------------------------------------------------------------------

EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "bge-large-en-v1.5")
EMBED_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
OLLAMA_URL = os.getenv(
    "LAWAPP_OLLAMA_BASE_URL",
    os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_URL", "http://ollama:11434")),
).rstrip("/")


def _embed_once(payload: bytes) -> list[float]:
    """Single embedding attempt with hard socket timeout."""
    import http.client
    import socket
    url_parts = OLLAMA_URL.replace("http://", "").split(":")
    host = url_parts[0]
    port = int(url_parts[1]) if len(url_parts) > 1 else 11434
    conn = http.client.HTTPConnection(host, port, timeout=30)
    try:
        conn.request("POST", "/api/embeddings", body=payload,
                      headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}: {resp.read()[:200]}")
        body = json.loads(resp.read().decode("utf-8"))
    finally:
        conn.close()
    vec = body.get("embedding")
    if not vec or len(vec) != EMBED_DIM:
        raise RuntimeError(f"Embedding dim {len(vec) if vec else 0} != {EMBED_DIM}")
    return vec


def embed_text(text: str, _retries: int = 3) -> list[float]:
    """Get 1024-dim embedding from Ollama with retry."""
    payload = json.dumps({"model": EMBED_MODEL, "prompt": text[:8000]}).encode("utf-8")
    last_err = None
    for attempt in range(_retries):
        try:
            return _embed_once(payload)
        except Exception as e:
            last_err = e
            logger.warning(f"  embed_text attempt {attempt+1}/{_retries} failed: {e}")
            time.sleep(2 ** attempt)
    raise last_err


def vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def chunk_text(text: str, size: int = 800) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [text[i:i + size] for i in range(0, len(text), size)]


def chunk_hash(source_url: str, idx: int, body: str) -> str:
    return hashlib.sha256(f"a7ingest:{source_url}:{idx}:{body}".encode()).hexdigest()


XML_CACHE_DIR = os.environ.get("XML_CACHE_DIR", "/app/xml_cache_dir")


def _cache_key_for_url(url: str) -> str:
    """Convert a legislation.gov.uk data.xml URL to a cache filename."""
    # https://www.legislation.gov.uk/ukpga/1996/18/data.xml -> ukpga_1996_18
    import re
    m = re.search(r'legislation\.gov\.uk/(\w+)/(\d+)/(\d+)/data\.xml', url)
    if m:
        return f"{m.group(1)}_{m.group(2)}_{m.group(3)}"
    return None


def fetch_url(url: str, accept: str = "application/xml", retries: int = 5) -> str:
    """Fetch a URL, using local XML cache if available, with network retry."""
    # Try local cache first
    cache_key = _cache_key_for_url(url)
    if cache_key and os.path.isdir(XML_CACHE_DIR):
        cache_path = os.path.join(XML_CACHE_DIR, f"{cache_key}.xml")
        if os.path.exists(cache_path):
            logger.info(f"  Using cached XML: {cache_path}")
            with open(cache_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

    # Fall back to network fetch with retries
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "Accept": accept,
                "User-Agent": "LawApp-A7-Ingestion/1.0 (OGL compliance)",
            })
            with urllib.request.urlopen(req, timeout=90) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError, ConnectionError) as e:
            last_err = e
            wait = 3 * attempt
            logger.warning(f"  Fetch attempt {attempt}/{retries} failed for {url}: {e} -- retrying in {wait}s")
            time.sleep(wait)
    raise last_err


# ---------------------------------------------------------------------------
# CLML XML parsing
# ---------------------------------------------------------------------------

CLML_NS = "http://www.legislation.gov.uk/namespaces/legislation"
NS = {"leg": CLML_NS}


def _all_text(elem) -> str:
    """Recursively extract all text content from an element."""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(_all_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join(parts).strip()


def _clean_text(text: str) -> str:
    """Collapse whitespace."""
    import re
    return re.sub(r'\s+', ' ', text).strip()


def parse_clml_sections(xml_text: str) -> list[dict]:
    """Parse CLML XML and extract sections.

    Returns list of dicts with keys: section_ref, heading, body_text, id_attr
    """
    sections = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning(f"XML parse error: {e}")
        return sections

    # Strategy 1: Find P1group elements (most Acts)
    for p1g in root.iter(f"{{{CLML_NS}}}P1group"):
        id_attr = p1g.get("id", "")
        # Title
        title_el = p1g.find(f"{{{CLML_NS}}}Title")
        heading = _clean_text(_all_text(title_el)) if title_el is not None else ""
        # Section number from Pnumber
        pnum_el = p1g.find(f".//{{{CLML_NS}}}Pnumber")
        section_num = _clean_text(_all_text(pnum_el)) if pnum_el is not None else ""
        # Body text
        body_parts = []
        for p1 in p1g.iter(f"{{{CLML_NS}}}P1"):
            body_parts.append(_clean_text(_all_text(p1)))
        body = " ".join(body_parts).strip()
        if not body:
            body = _clean_text(_all_text(p1g))
        if body and len(body) > 20:
            section_ref = section_num if section_num else id_attr
            sections.append({
                "section_ref": section_ref,
                "heading": heading,
                "body_text": body,
                "id_attr": id_attr,
            })

    # Strategy 2: If no P1group found, try Pblock > P1
    if not sections:
        for pblock in root.iter(f"{{{CLML_NS}}}Pblock"):
            id_attr = pblock.get("id", "")
            title_el = pblock.find(f"{{{CLML_NS}}}Title")
            heading = _clean_text(_all_text(title_el)) if title_el is not None else ""
            body = _clean_text(_all_text(pblock))
            if body and len(body) > 20:
                sections.append({
                    "section_ref": id_attr,
                    "heading": heading,
                    "body_text": body,
                    "id_attr": id_attr,
                })

    # Strategy 3: If still nothing, try P1 elements directly
    if not sections:
        for p1 in root.iter(f"{{{CLML_NS}}}P1"):
            id_attr = p1.get("id", "")
            pnum_el = p1.find(f"{{{CLML_NS}}}Pnumber")
            section_num = _clean_text(_all_text(pnum_el)) if pnum_el is not None else ""
            body = _clean_text(_all_text(p1))
            if body and len(body) > 20:
                sections.append({
                    "section_ref": section_num if section_num else id_attr,
                    "heading": "",
                    "body_text": body,
                    "id_attr": id_attr,
                })

    # Strategy 4: Try <legItem> or <Regulation> (some SIs)
    if not sections:
        for tag_name in ["legItem", "Regulation", "Article", "Rule"]:
            for elem in root.iter(f"{{{CLML_NS}}}{tag_name}"):
                id_attr = elem.get("id", "")
                body = _clean_text(_all_text(elem))
                if body and len(body) > 20:
                    sections.append({
                        "section_ref": id_attr,
                        "heading": "",
                        "body_text": body,
                        "id_attr": id_attr,
                    })
            if sections:
                break

    # Strategy 5: Last resort - extract text from Body/Part/Chapter elements
    if not sections:
        for body_el in root.iter(f"{{{CLML_NS}}}Body"):
            body_text = _clean_text(_all_text(body_el))
            if body_text and len(body_text) > 50:
                # Split into ~2000 char blocks as pseudo-sections
                for i in range(0, len(body_text), 2000):
                    chunk = body_text[i:i+2000]
                    sections.append({
                        "section_ref": f"body-{i//2000 + 1}",
                        "heading": f"Section block {i//2000 + 1}",
                        "body_text": chunk,
                        "id_attr": f"body-block-{i//2000 + 1}",
                    })

    return sections


def build_section_url(base_uri: str, leg_type: str, section_ref: str, id_attr: str) -> str:
    """Build a per-section source URL."""
    # base_uri is like https://www.legislation.gov.uk/id/ukpga/1996/18
    # Convert /id/ to plain path
    base = base_uri.replace("/id/", "/")
    if not base.startswith("https://www.legislation.gov.uk"):
        base = f"https://www.legislation.gov.uk/{leg_type}"

    # Try to extract section number from section_ref
    ref = section_ref.strip().rstrip(".")
    if ref and ref.replace("(", "").replace(")", "").replace(" ", ""):
        # If it's a pure number like "94" or "94A"
        clean = ref.split()[0] if " " in ref else ref
        if clean and (clean[0].isdigit() or clean[0] == "("):
            if leg_type.startswith("uksi"):
                return f"{base}/regulation/{clean}"
            else:
                return f"{base}/section/{clean}"

    # Use id_attr if it encodes section info
    if id_attr:
        # id_attr like "section-94" or "regulation-3"
        if "section-" in id_attr or "regulation-" in id_attr:
            return f"{base}/{id_attr.replace('-', '/', 1)}"
        return f"{base}#{id_attr}"

    return base


# ---------------------------------------------------------------------------
# Ingestion functions
# ---------------------------------------------------------------------------

def ensure_unique_constraint(conn):
    """Ensure legislation has unique constraint on (source_url, chunk_index)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'legislation'::regclass
              AND conname = 'legislation_source_url_chunk_index_key'
        """)
        if not cur.fetchone():
            logger.info("Creating unique constraint on legislation(source_url, chunk_index)")
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS legislation_source_url_chunk_index_key
                ON legislation (source_url, chunk_index)
            """)
    conn.commit()


def ingest_act(conn, entry: dict, stats: dict) -> int:
    """Ingest a single Act/SI. Returns number of sections inserted.

    Key design: never hold a DB transaction open while calling Ollama.
    Phase 1: insert all legislation rows (fast, pure DB).
    Phase 2: for each chunk needing an embedding, commit current tx,
             call Ollama outside any tx, then insert chunk in a new tx.
    """
    title = entry["title"]
    resolved_uri = entry["resolved_uri"]
    leg_type = entry["type"]
    year = entry.get("year")
    number = entry.get("number")

    # Build data.xml URL
    data_xml_url = resolved_uri.replace("/id/", "/") + "/data.xml"
    logger.info(f"  Fetching {data_xml_url}")

    xml_text = fetch_url(data_xml_url)
    time.sleep(1)  # Throttle

    sections = parse_clml_sections(xml_text)
    if not sections:
        logger.warning(f"  No sections found for {title}")
        return 0

    source_type = "secondary_legislation" if leg_type.startswith("uksi") else "primary_legislation"
    sections_inserted = 0
    chunks_embedded = 0

    # Phase 1: Insert all legislation rows in one transaction
    with conn.cursor() as cur:
        for sec_idx, sec in enumerate(sections):
            if sec_idx > 0 and sec_idx % 50 == 0:
                conn.commit()
                logger.info(f"    ... {sec_idx}/{len(sections)} sections processed (phase 1)")
            section_url = build_section_url(resolved_uri, leg_type, sec["section_ref"], sec["id_attr"])
            body = sec["body_text"]
            h = content_hash(body)

            cur.execute("""
                INSERT INTO legislation (
                    act_title, leg_type, year, chapter, section_ref, jurisdiction,
                    heading, body_text, chunk_index, source_url, source_type,
                    jurisdiction_code, content_hash, last_verified_at,
                    licence_status, parser_type
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, now(),
                    %s, %s
                )
                ON CONFLICT (source_url, chunk_index) DO UPDATE SET
                    body_text = EXCLUDED.body_text,
                    heading = EXCLUDED.heading,
                    content_hash = EXCLUDED.content_hash,
                    last_verified_at = now()
            """, (
                title, leg_type, year, str(number) if number else None,
                sec["section_ref"], "EW",
                sec["heading"], body, 0, section_url, source_type,
                "EW", h,
                "OGL-v3", "clml_xml",
            ))
            sections_inserted += cur.rowcount
    conn.commit()
    logger.info(f"    Phase 1 done: {sections_inserted} legislation rows upserted")

    # Phase 2: Collect chunks needing embeddings, then embed outside transaction
    pending_chunks = []
    with conn.cursor() as cur:
        for sec_idx, sec in enumerate(sections):
            section_url = build_section_url(resolved_uri, leg_type, sec["section_ref"], sec["id_attr"])
            body = sec["body_text"]
            text_chunks = chunk_text(body, 800)
            for ci, chunk_body in enumerate(text_chunks):
                ch = chunk_hash(section_url, ci, chunk_body)
                cur.execute("SELECT 1 FROM corpus_chunks WHERE chunk_hash = %s", (ch,))
                if cur.fetchone():
                    continue
                pending_chunks.append((section_url, ci, chunk_body, ch))
    conn.commit()  # close the read transaction

    if not pending_chunks:
        logger.info(f"    Phase 2: all {len(sections)} sections already have chunks")
    else:
        logger.info(f"    Phase 2: {len(pending_chunks)} chunks need embedding")

    # Now embed and insert one at a time, with short transactions
    for chunk_idx, (section_url, ci, chunk_body, ch) in enumerate(pending_chunks):
        if chunk_idx > 0 and chunk_idx % 50 == 0:
            logger.info(f"    ... {chunk_idx}/{len(pending_chunks)} chunks embedded")

        try:
            emb = embed_text(chunk_body)
            emb_str = vec_literal(emb)
        except Exception as e:
            logger.warning(f"  Embedding failed for {section_url} chunk {ci}: {e}")
            continue

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO corpus_chunks (
                    source_table, source_url, authority_ref, jurisdiction_code,
                    domain, claim_type, title, body_text, chunk_index, chunk_hash,
                    tokens_estimate, embedding, embedding_model, embedding_created_at,
                    is_current, source_type, licence_status
                ) VALUES (
                    'legislation', %s, %s, %s,
                    'employment_uk', 'employment_statute', %s, %s, %s, %s,
                    %s, %s::vector, %s, now(),
                    true, %s, 'OGL-v3'
                )
                ON CONFLICT (chunk_hash) DO NOTHING
            """, (
                section_url, f"{leg_type}/{year}/{number}", "EW",
                title, chunk_body, ci, ch,
                max(1, len(chunk_body) // 4),
                emb_str, EMBED_MODEL,
                source_type,
            ))
            chunks_embedded += cur.rowcount
        conn.commit()

    stats["total_legislation_rows"] += sections_inserted
    stats["total_chunks"] += chunks_embedded
    return len(sections)


def ingest_acas_guidance(conn, stats: dict):
    """Ingest ACAS guidance pages into acas_guidance + corpus_chunks."""
    acas_pages = [
        {
            "url": "https://www.acas.org.uk/acas-code-of-practice-on-disciplinary-and-grievance-procedures",
            "title": "ACAS Code of Practice on Disciplinary and Grievance Procedures",
            "edition": "2015 (current)",
        },
        {
            "url": "https://www.acas.org.uk/early-conciliation",
            "title": "ACAS Early Conciliation Guidance",
            "edition": "current",
        },
    ]

    for page in acas_pages:
        try:
            logger.info(f"  Fetching ACAS: {page['url']}")
            html = fetch_url(page["url"], accept="text/html")
            time.sleep(1)

            # Extract text from HTML (simple approach - strip tags)
            import re
            # Remove script and style elements
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
            # Remove tags
            text = re.sub(r'<[^>]+>', ' ', text)
            # Decode entities
            import html as html_mod
            text = html_mod.unescape(text)
            # Collapse whitespace
            text = re.sub(r'\s+', ' ', text).strip()

            if len(text) < 100:
                logger.warning(f"  ACAS page too short ({len(text)} chars): {page['url']}")
                continue

            h = content_hash(text)
            chunks = chunk_text(text, 800)

            with conn.cursor() as cur:
                for ci, chunk_body in enumerate(chunks):
                    # Insert into acas_guidance
                    cur.execute("""
                        INSERT INTO acas_guidance (
                            doc_title, edition, section_ref, body_text, chunk_index,
                            source_url, last_verified_at, content_hash,
                            jurisdiction_code, domain, source_type,
                            licence_status, parser_type, is_current
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, now(), %s,
                            %s, %s, %s,
                            %s, %s, true
                        )
                        ON CONFLICT (source_url, chunk_index) DO UPDATE SET
                            body_text = EXCLUDED.body_text,
                            content_hash = EXCLUDED.content_hash,
                            last_verified_at = now()
                    """, (
                        page["title"], page["edition"], f"chunk-{ci}",
                        chunk_body, ci,
                        page["url"], h,
                        "EW", "employment_uk", "official_guidance",
                        "OGL-equivalent", "html_strip",
                    ))

                    # corpus_chunks with embedding
                    ch = chunk_hash(page["url"], ci, chunk_body)
                    # Skip if chunk already exists
                    cur.execute("SELECT 1 FROM corpus_chunks WHERE chunk_hash = %s", (ch,))
                    if cur.fetchone():
                        continue

                    try:
                        emb = embed_text(chunk_body)
                        emb_str = vec_literal(emb)
                    except Exception as e:
                        logger.warning(f"  ACAS embedding failed chunk {ci}: {e}")
                        emb_str = None

                    if emb_str:
                        cur.execute("""
                            INSERT INTO corpus_chunks (
                                source_table, source_url, authority_ref, jurisdiction_code,
                                domain, claim_type, title, body_text, chunk_index, chunk_hash,
                                tokens_estimate, embedding, embedding_model, embedding_created_at,
                                is_current, source_type, licence_status
                            ) VALUES (
                                'acas_guidance', %s, %s, %s,
                                'employment_uk', 'acas_guidance', %s, %s, %s, %s,
                                %s, %s::vector, %s, now(),
                                true, 'official_guidance', 'OGL-equivalent'
                            )
                            ON CONFLICT (chunk_hash) DO NOTHING
                        """, (
                            page["url"], "acas", "EW",
                            page["title"], chunk_body, ci, ch,
                            max(1, len(chunk_body) // 4),
                            emb_str, EMBED_MODEL,
                        ))
                        stats["total_chunks"] += cur.rowcount

            conn.commit()
            stats["acas_ingested"] += 1
            logger.info(f"  ACAS done: {page['title']} - {len(chunks)} chunks")

        except Exception as e:
            logger.error(f"  ACAS ingestion failed for {page['url']}: {e}")
            traceback.print_exc()
            try:
                conn.rollback()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    manifest_path = os.environ.get(
        "MANIFEST_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports", "a7_statute_manifest.json"),
    )
    # Also try container paths
    for candidate in [manifest_path, "/app/reports/a7_statute_manifest.json"]:
        if os.path.exists(candidate):
            manifest_path = candidate
            break

    logger.info(f"Loading manifest from {manifest_path}")
    with open(manifest_path) as f:
        manifest = json.load(f)

    conn = get_conn()

    # Before census
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM legislation")
        before_leg = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM corpus_chunks")
        before_chunks = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM acas_guidance")
        before_acas = cur.fetchone()[0]

    logger.info(f"=== BEFORE CENSUS: legislation={before_leg}, corpus_chunks={before_chunks}, acas_guidance={before_acas} ===")

    # Ensure unique constraint exists
    ensure_unique_constraint(conn)

    # Filter manifest: skip ambiguous entries
    resolved = [e for e in manifest if e.get("status") == "resolved"]
    skipped = [e for e in manifest if e.get("status") != "resolved"]
    for s in skipped:
        logger.info(f"SKIPPING (status={s.get('status')}): {s['title']}")

    total = len(resolved)
    logger.info(f"Will process {total} resolved statutes")

    stats = {
        "total_legislation_rows": 0,
        "total_chunks": 0,
        "acts_ingested": 0,
        "acts_failed": 0,
        "acas_ingested": 0,
    }

    for i, entry in enumerate(resolved, 1):
        title = entry["title"]
        try:
            logger.info(f"Processing [{i}/{total}]: {title}...")
            n_sections = ingest_act(conn, entry, stats)
            stats["acts_ingested"] += 1
            logger.info(f"  {title}: {n_sections} sections found, {stats['total_chunks']} total chunks so far")
        except Exception as e:
            stats["acts_failed"] += 1
            logger.error(f"  FAILED: {title}: {e}")
            traceback.print_exc()
            try:
                conn.rollback()
            except Exception:
                pass

        if i % 10 == 0:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM legislation")
                cur_leg = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM corpus_chunks")
                cur_chunks = cur.fetchone()[0]
            logger.info(f"=== PROGRESS: {i}/{total} acts processed, {cur_leg} legislation rows, {cur_chunks} corpus chunks ===")

    # Ingest ACAS guidance
    logger.info("=== ACAS GUIDANCE INGESTION ===")
    ingest_acas_guidance(conn, stats)

    # After census
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM legislation")
        after_leg = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM corpus_chunks")
        after_chunks = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM acas_guidance")
        after_acas = cur.fetchone()[0]
        cur.execute("SELECT count(DISTINCT act_title) FROM legislation")
        distinct_acts = cur.fetchone()[0]

    conn.close()

    logger.info("=" * 60)
    logger.info("=== A7 INGESTION COMPLETE ===")
    logger.info(f"  Acts processed:   {stats['acts_ingested']}/{total} (failed: {stats['acts_failed']})")
    logger.info(f"  ACAS pages:       {stats['acas_ingested']}")
    logger.info(f"  BEFORE: legislation={before_leg}, corpus_chunks={before_chunks}, acas_guidance={before_acas}")
    logger.info(f"  AFTER:  legislation={after_leg}, corpus_chunks={after_chunks}, acas_guidance={after_acas}")
    logger.info(f"  NEW:    legislation=+{after_leg - before_leg}, corpus_chunks=+{after_chunks - before_chunks}, acas_guidance=+{after_acas - before_acas}")
    logger.info(f"  Distinct act titles in legislation: {distinct_acts}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
