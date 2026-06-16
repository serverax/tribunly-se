"""
T-004 local embedder  -  runs in /tmp/lawapp-audit-venv, connects to lawapp-rag DB
via port-forward (127.0.0.1:15432), embeds NULL corpus_chunks with the SAME model
as the 92 existing rows (BAAI/bge-small-en-v1.5, fastembed ONNX, 384-dim).

ADDITIVE only: UPDATE embedding WHERE embedding IS NULL. No DROP/TRUNCATE/DELETE.
Real vectors only  -  refuses all-zero outputs.
"""
import os, sys
import psycopg2
from fastembed import TextEmbedding

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
STORE_MODEL = "bge-small-en-v1.5"
DIM = 384
BATCH = 64

pw = os.environ["PGPW"]
print(f"[embed] loading {EMBED_MODEL}")
model = TextEmbedding(model_name=EMBED_MODEL)
print("[embed] loaded")

conn = psycopg2.connect(host="127.0.0.1", port=15432, dbname="lawapp",
                        user="lawapp_user", password=pw)
cur = conn.cursor()
cur.execute("SELECT id, body_text FROM corpus_chunks WHERE embedding IS NULL ORDER BY created_at, id")
rows = cur.fetchall()
print(f"[embed] NULL rows: {len(rows)}")
if not rows:
    sys.exit(0)

embedded = 0


def flush(ids, texts):
    global embedded
    vecs = list(model.embed([(t or "")[:2000] for t in texts]))
    for rid, v in zip(ids, vecs):
        lst = v.tolist()
        assert len(lst) == DIM, f"bad dim {len(lst)}"
        if not any(abs(x) > 1e-9 for x in lst):
            raise RuntimeError(f"all-zero vector for {rid}  -  refusing")
        cur.execute(
            "UPDATE corpus_chunks SET embedding=%s::vector, embedding_model=%s, "
            "embedding_created_at=now(), updated_at=now() "
            "WHERE id=%s AND embedding IS NULL",
            (lst, STORE_MODEL, rid),
        )
    conn.commit()
    embedded += len(ids)
    print(f"[embed] committed {embedded}/{len(rows)}")


ids_b, texts_b = [], []
for rid, body in rows:
    ids_b.append(rid); texts_b.append(body)
    if len(ids_b) >= BATCH:
        flush(ids_b, texts_b); ids_b, texts_b = [], []
if ids_b:
    flush(ids_b, texts_b)

print(f"[embed] DONE embedded={embedded}")
conn.close()
