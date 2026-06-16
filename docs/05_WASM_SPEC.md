# WASM Specification  -  Client-Side Computation

**Pairs with:** `02_HLD_ARCHITECTURE.md` (Layer 1).
**Principle:** WASM is used for what it is genuinely good at  -  fast, sandboxed, privacy-preserving computation in the browser. It is NOT used to run LLMs or the core RAG. Right tool, specific jobs.

---

## 1. Why WASM here (the rationale)
Two real wins for this product:
1. **Privacy:** sensitive computation (e.g. on case facts/dates) can run in the browser without sending data to the server  -  reduces special-category data exposure.
2. **Speed:** instant, no network round-trip, for interactive UX (live deadline recalculation as the user edits a date).

It is deliberately scoped. Heavy reasoning, retrieval, and generation stay server-side.

## 2. What runs in WASM (in scope)

### 2.1 Deadline calculator
- Computes the limitation date and ACAS Early Conciliation windows from user-entered dates.
- Inputs: dismissal/effective date, EC start/end dates.
- Logic source: the rules (time-limit values) are fetched once from the server `rules` table; the *arithmetic* runs client-side.
- Live recalculation as the user edits  -  instant feedback, no round-trip.
> Note: the rule VALUES (e.g. 3 months) come from the server `rules` table (deterministic source of truth). WASM does the date arithmetic, not the legal-value lookup.

### 2.2 Document assembly / preview
- Merges the generated content + user facts into the document template for on-screen preview and local export.
- Runs client-side so the assembled document (containing personal data) can be previewed without an extra server round-trip.

### 2.3 Form validation
- Validates intake inputs (date formats, required fields, internal consistency e.g. EC end after EC start) instantly in-browser.

### 2.4 Light parsing (optional)
- Lightweight client-side parsing/normalisation of pasted text or simple inputs before submission.

## 3. What does NOT run in WASM (out of scope  -  server-side)
- LLM inference (workhorse or escalation tiers).
- RAG / vector search / retrieval.
- Document generation by the model (the *generation* is server-side; only *assembly/preview* of already-generated content is client-side).
- Anything requiring the curated legal database.

## 4. Data-handling rule
- WASM modules process data locally; where data stays on-device (deadline calc, validation), it should not be transmitted unless needed for a server step.
- This supports the Article 9 minimisation principle  -  keep sensitive computation client-side where feasible.

## 5. Implementation notes (for the agent)
- Implement WASM modules in a language with good WASM tooling (e.g. Rust → wasm-bindgen, or AssemblyScript)  -  choose per team capability; flag the choice.
- Keep modules small and single-purpose (deadline, assembly, validation as separate modules).
- The deadline module must read rule values passed in from the server, not embed them  -  so a legal change updates the `rules` table, not the WASM binary.
- Provide a non-WASM JS fallback for environments where WASM is unavailable, so the app degrades gracefully.

## 6. Acceptance criteria (ties to build plan)
- Deadline calculator returns the correct limitation date for given inputs, recalculating live, using rule values supplied by the server.
- Document preview renders the assembled document client-side without sending data for the preview step.
- Validation catches malformed/inconsistent inputs instantly.
- Sensitive client-side computation does not transmit data except where a server step requires it (verify in test).
