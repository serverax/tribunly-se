#!/usr/bin/env python3
"""
Prove connector idempotency: re-run upsert adds zero new versions for same content_hash.

Uses legislation upsert ON CONFLICT — second run must not increase row count.
"""

from __future__ import annotations

import hashlib

from ingestion.db import get_connection, upsert_legislation


def _sample_row() -> dict:
    body = "ERA 1996 s.98 unfair dismissal reasonableness (idempotency probe)."
    url = "https://www.legislation.gov.uk/idempotency-probe/era1996/s98"
    return {
        "act_title": "Employment Rights Act 1996",
        "leg_type": "ukpga",
        "year": 1996,
        "chapter": "18",
        "section_ref": "s.98",
        "jurisdiction": "EW",
        "heading": "Fairness",
        "body_text": body,
        "chunk_index": 0,
        "source_url": url,
        "version_date": None,
        "effective_from": "1996-11-22",
        "effective_to": None,
        "is_prospective": False,
        "country_code": "GB",
        "domain": "employment_uk",
        "source_type": "legislation",
        "licence_status": "ogl",
        "parser_type": "probe",
        "parent_source_id": None,
        "jurisdiction_code": "EW",
        "legal_system": "EW",
        "applies_to_gb": True,
        "applies_to_england_wales": True,
        "applies_to_scotland": False,
        "applies_to_ni": False,
    }


def _count_for_url(url: str) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM legislation WHERE source_url = %s",
                (url,),
            )
            return int(cur.fetchone()[0])
    finally:
        conn.close()


def main() -> int:
    row = _sample_row()
    url = row["source_url"]
    before = _count_for_url(url)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            upsert_legislation(cur, row)
        conn.commit()
    finally:
        conn.close()
    after_first = _count_for_url(url)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            upsert_legislation(cur, row)
        conn.commit()
    finally:
        conn.close()
    after_second = _count_for_url(url)

    print("before:", before)
    print("after_first:", after_first)
    print("after_second:", after_second)
    print("content_hash:", hashlib.sha256(row["body_text"].encode()).hexdigest()[:16])

    if after_second != after_first:
        print("FAIL: row count changed on re-run")
        return 1
    print("PASS: idempotent re-run (zero new versions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
