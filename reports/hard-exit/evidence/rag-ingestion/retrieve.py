"""
T-004 retrieval proof  -  embeds real queries with the SAME model (bge-small-en-v1.5)
and runs pgvector cosine nearest-neighbour over corpus_chunks, joining legal_sources
for provenance. Read-only.
"""
import os
import psycopg2
from fastembed import TextEmbedding

model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
pw = os.environ["PGPW"]
conn = psycopg2.connect(host="127.0.0.1", port=15432, dbname="lawapp",
                        user="lawapp_user", password=pw)
cur = conn.cursor()

QUERIES = [
    "unfair dismissal qualifying period",
    "employment tribunal time limit",
]

SQL = """
SELECT cc.id, round((cc.embedding <=> %s::vector)::numeric, 4) AS cos_dist,
       cc.source_id, cc.source_url, cc.authority_ref, cc.chunk_hash,
       cc.source_type, ls.source_name AS source_name, ls.base_url AS source_base_url,
       ls.licence_status AS licence_status,
       left(regexp_replace(cc.body_text, '\\s+', ' ', 'g'), 220) AS snippet
FROM corpus_chunks cc
LEFT JOIN legal_sources ls ON ls.id = cc.source_id
WHERE cc.embedding IS NOT NULL
ORDER BY cc.embedding <=> %s::vector
LIMIT 5;
"""

for q in QUERIES:
    qv = list(model.embed([q]))[0].tolist()
    print("=" * 90)
    print(f"QUERY: {q!r}   (cosine NN, top-5)")
    print("=" * 90)
    cur.execute(SQL, (qv, qv))
    for i, r in enumerate(cur.fetchall(), 1):
        cid, dist, sid, url, auth, chash, stype, sname, sbase, lic, snip = r
        print(f"\n[{i}] cos_dist={dist}  chunk_id={cid}")
        print(f"    source_id={sid}  source_type={stype}  licence={lic}")
        print(f"    authority_ref={auth}")
        print(f"    source_url={url}")
        print(f"    parent_source_name={sname}  base_url={sbase}")
        print(f"    chunk_hash={chash}")
        print(f"    snippet: {snip}")
    print()

conn.close()
