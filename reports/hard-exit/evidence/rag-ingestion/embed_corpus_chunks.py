"""
T-004  -  Embed NULL-embedding corpus_chunks using the SAME model as existing rows.

Model: BAAI/bge-small-en-v1.5 via fastembed (384-dim, ONNX)  -  matches the 92
existing embedded chunks (embedding_model='bge-small-en-v1.5', vector(384)).

ADDITIVE only: UPDATE embedding column on rows WHERE embedding IS NULL.
Never DROP/TRUNCATE/DELETE. Real vectors only (no random/placeholder).

Runs inside lawapp-ai/lawapp-brain (fastembed cached at /app/fastembed_cache,
DATABASE_URL -> lawapp-rag DB).
"""
from __future__ import annotations

import os
import sys

EMBED_MODEL = "BAAI/bge-small-en-v1.5"   # 384-dim, fastembed ONNX
STORE_MODEL = "bge-small-en-v1.5"        # value already used by 92 existing rows
EMBED_DIM = 384
BATCH = 64
CACHE = os.environ.get("FASTEMBED_CACHE_PATH", "/app/fastembed_cache")

import psycopg2
from fastembed import TextEmbedding

url = os.environ["DATABASE_URL"]
print(f"[embed] model={EMBED_MODEL} dim={EMBED_DIM} cache={CACHE}")
model = TextEmbedding(model_name=EMBED_MODEL, cache_dir=CACHE)
print("[embed] model loaded")

conn = psycopg2.connect(url)
conn.autocommit = False
cur = conn.cursor()

cur.execute(
    "SELECT id, body_text FROM corpus_chunks "
    "WHERE embedding IS NULL ORDER BY created_at, id"
)
rows = cur.fetchall()
print(f"[embed] NULL-embedding rows to process: {len(rows)}")
if not rows:
    print("[embed] nothing to do")
    sys.exit(0)

embedded = 0
zero_vectors = 0
ids_b, texts_b = [], []


def flush(ids, texts):
    global embedded, zero_vectors
    vecs = list(model.embed([(t or "")[:2000] for t in texts]))
    for rid, v in zip(ids, vecs):
        lst = v.tolist()
        assert len(lst) == EMBED_DIM, f"bad dim {len(lst)} for {rid}"
        if not any(abs(x) > 1e-9 for x in lst):
            zero_vectors += 1
            raise RuntimeError(f"all-zero vector produced for {rid}  -  refusing")
        cur.execute(
            "UPDATE corpus_chunks "
            "SET embedding = %s::vector, embedding_model = %s, "
            "    embedding_created_at = now(), updated_at = now() "
            "WHERE id = %s AND embedding IS NULL",
            (lst, STORE_MODEL, rid),
        )
    conn.commit()
    embedded += len(ids)
    print(f"[embed] committed {embedded}/{len(rows)}")


for rid, body in rows:
    ids_b.append(rid)
    texts_b.append(body)
    if len(ids_b) >= BATCH:
        flush(ids_b, texts_b)
        ids_b, texts_b = [], []
if ids_b:
    flush(ids_b, texts_b)

print(f"[embed] DONE embedded={embedded} zero_vectors={zero_vectors}")
conn.close()
