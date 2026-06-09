#!/usr/bin/env python3
"""
T-003 legal-data-engineer transform.

INPUT  : SA-001 validated raw manifest + raw/*.xml (CLML) + raw/*.html (ACAS/GOV.UK)
OUTPUT : two SQL files that are piped into the in-cluster lawapp-rag Postgres
         via `kubectl exec -i ... psql`.

This script ONLY transforms local disk artefacts. It performs NO web scraping.
It is ADDITIVE: it emits INSERT statements only (ON CONFLICT DO NOTHING for the
licence-registry rows so a re-run is idempotent). It never DROP/TRUNCATE/UPDATE.

Provenance binding for every corpus_chunk:
  source_id      -> legal_sources.id (FK, resolved at insert time by subquery)
  source_url     -> precise per-section / page URL (legislation.gov.uk section URI
                    or the SA-001 page URL)
  chunk_hash     -> sha256(body_text)  (also the corpus_chunks UNIQUE key)
  authority_ref  -> human citation e.g. 'Employment Rights Act 1996 s.1'
  source_table   -> 'legal_sources'
  source_type    -> from manifest
Every chunk traces back to a real SA-001 content_hash via the legal_sources note.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from lxml import etree, html

ROOT = Path("/mnt/f/lawapp")
SCRAPE = ROOT / "reports/hard-exit/evidence/legal-data-scrape"
RAW = SCRAPE / "raw"
OUT = ROOT / "reports/hard-exit/evidence/legal-dataset-engineering"
MANIFEST = json.loads((SCRAPE / "raw-source-manifest.json").read_text())

NS = "http://www.legislation.gov.uk/namespaces/legislation"


def T(local: str) -> str:
    return f"{{{NS}}}{local}"


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sql_str(s) -> str:
    """Postgres single-quoted literal, NULL for None."""
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_text(element) -> str:
    parts = []

    def walk(el):
        if el.text:
            parts.append(el.text)
        for child in el:
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(element)
    return collapse(" ".join(parts))


# Map manifest jurisdiction strings to the DB legal_jurisdictions FK codes.
JURIS_MAP = {"UK": "UK", "EW": "EW", "GB": "GB", "NI": "NI", "S": "S"}

# Short authority prefixes for legislation.
ACT_PREFIX = {
    "era-1996": "Employment Rights Act 1996",
    "equality-act-2010": "Equality Act 2010",
    "eta-1996": "Employment Tribunals Act 1996",
}

# ---------------------------------------------------------------------------
# 1. legal_sources registry rows (one per SA-001 source_id)
# ---------------------------------------------------------------------------

LICENCE = {
    "legislation": ("ogl-v3", "active"),
    "acas_guidance": ("acas-web", "review"),
    "govuk_guidance": ("ogl-v3", "active"),
}


def build_sources_sql() -> str:
    lines = [
        "-- T-003 legal_sources registry rows (ADDITIVE, idempotent).",
        "-- base_url carries the precise SA-001 source_url; notes carries the",
        "-- SA-001 content_hash so every downstream chunk traces to a real scrape.",
        "BEGIN;",
    ]
    for m in MANIFEST:
        sid = m["source_id"]
        lic_name, lic_status = LICENCE.get(m["source_type"], ("ogl-v3", "active"))
        source_key = f"employment_uk:t003:{sid}"
        note = (
            f"SA-001 scrape source_url={m['source_url']}; "
            f"content_hash={m['content_hash']}; "
            f"format={m['format']}; retrieved_at={m['retrieved_at']}; "
            f"raw_path={m['raw_path']}"
        )
        lines.append(
            "INSERT INTO legal_sources "
            "(domain, source_id, source_name, source_type, base_url, jurisdiction, "
            "licence_type, licence_status, licence_name, source_key, active, "
            "last_verified_at, notes) VALUES ("
            f"'employment_uk', {sql_str(sid)}, {sql_str(m['source_title'])}, "
            f"{sql_str(m['source_type'])}, {sql_str(m['source_url'])}, "
            f"{sql_str(JURIS_MAP[m['jurisdiction']])}, {sql_str(lic_name)}, "
            f"{sql_str(lic_status)}, {sql_str(lic_name)}, {sql_str(source_key)}, "
            f"true, '2026-06-07', {sql_str(note)}) "
            "ON CONFLICT (domain, source_id) DO NOTHING;"
        )
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 2. Legislation chunks (P1group = section)
# ---------------------------------------------------------------------------

def parse_act(source_id: str):
    m = next(x for x in MANIFEST if x["source_id"] == source_id)
    raw = (RAW / Path(m["raw_path"]).name).read_bytes()
    root = etree.fromstring(raw)
    doc_uri = root.get("DocumentURI") or m["source_url"]
    eff_from = root.get("RestrictStartDate")
    extent = root.get("RestrictExtent", "")
    juris = "UK" if "N.I." in extent or "+" in extent else JURIS_MAP[m["jurisdiction"]]
    body = root.find(".//" + T("Body"))
    prefix = ACT_PREFIX[source_id]
    chunks = []
    seen = set()
    for grp in body.findall(".//" + T("P1group")):
        title_el = grp.find(T("Title"))
        p1 = grp.find(T("P1"))
        heading = extract_text(title_el) if title_el is not None else None
        sec_uri = p1.get("DocumentURI") if p1 is not None else None
        sec_id = p1.get("id") if p1 is not None else None  # e.g. section-1
        body_text = extract_text(grp)
        if not body_text or len(body_text) < 40:
            continue
        sec_num = None
        if sec_id and sec_id.startswith("section-"):
            sec_num = sec_id.split("section-", 1)[1]
        if sec_num:
            authority_ref = f"{prefix} s.{sec_num}"
        elif heading:
            authority_ref = f"{prefix} - {heading}"
        else:
            authority_ref = prefix
        url = sec_uri or doc_uri
        ch = sha256(body_text)
        if ch in seen:
            continue
        seen.add(ch)
        chunks.append({
            "heading": heading,
            "body_text": body_text,
            "source_url": url,
            "authority_ref": authority_ref,
            "jurisdiction": juris,
            "source_type": m["source_type"],
            "title": m["source_title"],
            "effective_from": eff_from,
        })
    return m, chunks


# ---------------------------------------------------------------------------
# 3. HTML guidance chunks
# ---------------------------------------------------------------------------

STRIP_TAGS = {"script", "style", "nav", "form", "button", "svg", "noscript",
              "header", "footer", "aside"}


def parse_html(source_id: str):
    m = next(x for x in MANIFEST if x["source_id"] == source_id)
    doc = html.parse(str(RAW / Path(m["raw_path"]).name)).getroot()
    mains = doc.xpath('//main | //*[@role="main"]')
    main = mains[0] if mains else doc
    # remove noise
    for tag in STRIP_TAGS:
        for el in main.iter(tag):
            el.getparent().remove(el) if el.getparent() is not None else None
    # walk in document order, grouping paragraphs under their heading
    chunks = []
    seen = set()
    cur_heading = m["source_title"]
    buf = []

    def flush():
        nonlocal buf
        if not buf:
            return
        text = collapse("\n".join(buf))
        buf = []
        if len(text) < 60:
            return
        ch = sha256(text)
        if ch in seen:
            return
        seen.add(ch)
        chunks.append({
            "heading": cur_heading,
            "body_text": text,
            "source_url": m["source_url"],
            "authority_ref": f"{m['source_title']} ({m['source_url']})",
            "jurisdiction": JURIS_MAP[m["jurisdiction"]],
            "source_type": m["source_type"],
            "title": m["source_title"],
            "effective_from": None,
        })

    for el in main.iter():
        tag = el.tag if isinstance(el.tag, str) else None
        if tag in ("h1", "h2", "h3", "h4"):
            flush()
            ht = collapse(el.text_content())
            if ht:
                cur_heading = ht
        elif tag in ("p", "li"):
            txt = collapse(el.text_content())
            if len(txt) > 20:
                buf.append(txt)
                # cap chunk size ~2500 chars at paragraph boundary
                if sum(len(b) for b in buf) > 2500:
                    flush()
    flush()
    return m, chunks


# ---------------------------------------------------------------------------
# Emit chunk SQL
# ---------------------------------------------------------------------------

def chunk_insert(c, source_id_literal_subquery, idx) -> str:
    ch = sha256(c["body_text"])
    eff = sql_str(c["effective_from"]) if c["effective_from"] else "NULL"
    return (
        "INSERT INTO corpus_chunks "
        "(source_table, source_id, domain, jurisdiction_code, authority_ref, "
        "source_url, title, heading, body_text, chunk_index, chunk_hash, "
        "source_type, effective_from, is_current, legal_topics) VALUES ("
        f"'legal_sources', {source_id_literal_subquery}, 'employment_uk', "
        f"{sql_str(c['jurisdiction'])}, {sql_str(c['authority_ref'])}, "
        f"{sql_str(c['source_url'])}, {sql_str(c['title'])}, "
        f"{sql_str(c['heading'])}, {sql_str(c['body_text'])}, {idx}, "
        f"{sql_str(ch)}, {sql_str(c['source_type'])}, {eff}, true, "
        "ARRAY['employment']::text[]) "
        "ON CONFLICT (chunk_hash) DO NOTHING;"
    )


def build_chunks_sql():
    lines = ["BEGIN;"]
    summary = {}
    LEG = ["era-1996", "equality-act-2010", "eta-1996"]
    HTML = ["acas-dismissals", "acas-disciplinary-grievance", "acas-early-conciliation",
            "govuk-et-make-a-claim", "govuk-redundancy", "govuk-holiday-entitlement"]
    for sid in LEG:
        m, chunks = parse_act(sid)
        subq = f"(SELECT id FROM legal_sources WHERE domain='employment_uk' AND source_id={sql_str(sid)})"
        lines.append(f"-- {sid}: {len(chunks)} legislation chunks")
        for i, c in enumerate(chunks):
            lines.append(chunk_insert(c, subq, i))
        summary[sid] = len(chunks)
    for sid in HTML:
        m, chunks = parse_html(sid)
        subq = f"(SELECT id FROM legal_sources WHERE domain='employment_uk' AND source_id={sql_str(sid)})"
        lines.append(f"-- {sid}: {len(chunks)} guidance chunks")
        for i, c in enumerate(chunks):
            lines.append(chunk_insert(c, subq, i))
        summary[sid] = len(chunks)
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n", summary


def main():
    (OUT / "insert-sources.sql").write_text(build_sources_sql())
    chunks_sql, summary = build_chunks_sql()
    (OUT / "insert-chunks.sql").write_text(chunks_sql)
    print("SOURCES SQL bytes:", (OUT / "insert-sources.sql").stat().st_size)
    print("CHUNKS  SQL bytes:", (OUT / "insert-chunks.sql").stat().st_size)
    total = 0
    for k, v in summary.items():
        print(f"  {k:32s} {v:5d} chunks")
        total += v
    print("TOTAL chunks to insert:", total)


if __name__ == "__main__":
    main()
