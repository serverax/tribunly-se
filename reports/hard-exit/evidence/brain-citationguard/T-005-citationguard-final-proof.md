# T-005  -  CitationGuard / Hallucination Guard  -  Final Proof

**Date:** 2026-06-07
**Branch:** recovery/lawapp-autonomous-stabilisation
**Agent:** project-manager (autonomous) via ai-brain-citationguard path
**Result:** ✅ **PASS at local-runtime level** (3 evidence layers, live DB + live API).
**Caveat (honest):** the 798-chunk/890-embedding production corpus lives on the AKS
`lawapp-rag` cluster, which is currently **unreachable** (DNS no-host  -  owner-blocked).
Proof below is against the **live local Docker stack** (`lawapp-db-1`, `lawapp-backend-1`)
which carries a real but smaller 8-chunk UK-employment corpus. The CitationGuard
*mechanism*  -  accept-real / reject-fake / regenerate / fail-closed-fallback  -  is proven
end to end; the large-corpus re-confirmation is gated on owner G1 (AKS access).

---

## Runtime environment proven against
- `lawapp-db-1`  -  PostgreSQL, healthy. `corpus_chunks=8`, `legal_sources=8`, all REAL
  UK employment authorities (ERA 1996 ss.94/95/98/108/111, ACAS Code, ACAS Dismissals
  guidance, ETA 1996). No placeholder/fake rows.
- `lawapp-backend-1`  -  monolith API, healthy, `db:connected`.
- `lawapp-ollama`  -  qwen2.5:3b loaded (not wired to local backend; backend = StubReasoningModel).

---

## Layer 1  -  Unit tests vs LIVE DB (pytest)
`DATABASE_URL=postgresql://lawapp:lawapp@localhost:5435/lawapp python -m pytest tests/test_corpus_citation_guard.py -v`

```
tests/test_corpus_citation_guard.py::test_extract_uuids_pure PASSED
tests/test_corpus_citation_guard.py::test_fake_uuid_is_not_a_valid_citation PASSED
tests/test_corpus_citation_guard.py::test_real_uuid_is_a_valid_citation PASSED
tests/test_corpus_citation_guard.py::test_enforce_accepts_response_with_real_uuid PASSED
tests/test_corpus_citation_guard.py::test_enforce_rejects_uncited_and_falls_back PASSED
======================== 5 passed in 3.56s =========================
```
DB-gated (`@db_required`)  -  these ran against the real DB, not skipped.

## Layer 2  -  Function proof vs LIVE DB
`t005-live/live-guard-proof.txt` (regenerable):
- real corpus UUID `e4b669f1-…` → valid citation = **True**
- fake UUID `00000000-…` → valid set = **empty**, valid citation = **False**
- `enforce_or_regenerate` with real-cited draft → **accepted**, attempts=1
- `enforce_or_regenerate` uncited → **fallback** after 3 attempts (initial + 2 regen),
  deterministic guide returned. **No ungrounded model text accepted.**

## Layer 3  -  Runtime API + DB persistence (`/api/brain/trace`)
`t005-live/live-brain-trace.json` (HTTP 200):
- `trace_id = 1c1a8d0f-6266-423d-899d-e0916e3dfa91`
- `claim_type = unfair_dismissal`, `legal_area = employment_law`
- `agents_selected` includes **`citation_verification`**
- `sources_retrieved = 8`, **`citations_verified = 3`**, **`citations_failed = 5`**
  → guard ran in the live pipeline and **rejected 5 invalid citations**, kept 3 real.
- DB: `SELECT trace_id FROM brain_traces WHERE trace_id='1c1a8d0f-…'` → **row present**
  (brain_traces total = 67). Trace persisted, not in-memory only.

---

## CitationGuard wiring (source)
- `backend/core/agentic/corpus_citation_guard.py`  -  `valid_corpus_uuids()` resolves cited
  UUIDs against `corpus_chunks.id`; `enforce_or_regenerate()` drives bounded regen + fail-closed fallback.
- `backend/core/brain.py:303,795`  -  pipeline `assess` invokes the guard (LLM Fabric directive);
  no generative lane bypasses it.
- `/api/brain/trace` (`backend/api/main.py:2418`)  -  single governed entrypoint; "No direct LLM calls bypass this endpoint."

## Acceptance matrix
| T-005 criterion | Status | Evidence |
|---|---|---|
| valid source accepted | ✅ | Layer 1/2/3 |
| fake source rejected | ✅ | Layer 1/2 (fake set empty); Layer 3 (5 failed) |
| unsupported claim → regenerate then fallback | ✅ | Layer 2 (attempts=3 → deterministic) |
| trace created + persisted | ✅ | Layer 3 (brain_traces row) |
| RAG + CitationGuard stages in trace | ✅ | Layer 3 (rag_sources, citation_verification, citations_verified/failed) |
| large production corpus re-confirm | ⏳ owner-blocked | AKS lawapp-rag unreachable (G1/G9) |

## Owner-blocked residual
- AKS cluster DNS unresolvable → cannot re-run guard against the 798-chunk corpus.
- Local backend brain uses StubReasoningModel (T-008 config: repoint to `ollama-inference`)
   -  does not affect guard validity (guard validates citations regardless of draft source),
  but a full "local model live answer + verified citations" demo needs the ollama wiring (T-008 owner item).
