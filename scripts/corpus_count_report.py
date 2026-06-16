#!/usr/bin/env python3
"""Print corpus + graph counts for beta threshold documentation."""

from __future__ import annotations

from ingestion.db import get_connection


def main() -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM corpus_chunks")
            corpus = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM legislation")
            legislation = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM acas_guidance")
            acas = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM legal_nodes WHERE is_active = true")
            nodes = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM legal_edges")
            edges = cur.fetchone()[0]
            cur.execute(
                """
                SELECT vector_dims(embedding)
                FROM corpus_chunks
                WHERE embedding IS NOT NULL
                LIMIT 1
                """
            )
            dim_row = cur.fetchone()
            dim = dim_row[0] if dim_row else None
    finally:
        conn.close()

    print("corpus_chunks:", corpus)
    print("legislation_rows:", legislation)
    print("acas_guidance_rows:", acas)
    print("legal_nodes_active:", nodes)
    print("legal_edges:", edges)
    print("embedding_dim_sample:", dim)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
