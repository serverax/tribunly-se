# Retrieval Pipeline  -  Proof Report

- **Timestamp:** 2026-06-05  **Branch:** main  **Commit:** a0968b0
- **Command:** `bash scripts/prove_retrieval_pipeline.sh`
- **Final status:** **PASS**

Proves the jurisdiction-aware retrieval contract at the data layer (the order in §9):

1. **Validate jurisdiction**  -  GB is a supported employment-law jurisdiction (controlled table).
2. **Exact rules**  -  11 current GB unfair-dismissal rules retrievable by claim+jurisdiction+date.
3. **Keyword (full-text)** filtered by jurisdiction  -  41 GB hits for "unfair dismissal".
4. **Vector** candidates filtered by jurisdiction  -  5 GB top-k candidates (HNSW).
5. **Bundle provenance**  -  every GB chunk carries source_url + authority_ref.
6. **Audit**  -  `legal_retrieval_audit` accepts a jurisdiction-tagged write.
7. **NI fail-closed**  -  NI rules/chunks empty → NI bundle empty → assessment unsupported.
8. **No leakage**  -  NI-scoped query returns no GB rule values.

## Status of the backend code path
- Data-layer contract: **DONE AND PROVEN**.
- Wiring this exact ordering (rules → keyword → vector → merge → audit → reason) into the
  live `backend/core/retrieve.py` + `/assess` path with an explicit jurisdiction_code
  parameter on every call: **IMPLEMENTED BUT PARTIAL**  -  `retrieve()` already does hybrid
  lexical+semantic with citation→DB resolution; adding the jurisdiction_code filter argument
  and the `legal_retrieval_audit` write into the request path is the next code step.
