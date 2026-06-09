# RAG + Reasoning Specification (the "Algorithm Brain")

**Pairs with:** `02_HLD_ARCHITECTURE.md` (Layers 3 & 4), `03_DATABASE_DESIGN.md`.
**Core rule (GUARDRAIL):** Retrieval ALWAYS runs first. The reasoning model answers FROM retrieved, cited sources — never from its own memory. Exact facts (deadlines/caps) come from the structured `rules` table, never from generation. If grounding is insufficient, the system does NOT guess — it flags uncertainty or routes to a human.

---

## 1. The pipeline (per request)

```
query + facts
   │
   ▼
[1] CLASSIFY  ── matter type (unfair_dismissal only for now) + intent
   │            (diagnosis | document | deadline_check)
   ▼
[2] RETRIEVE (always) ── hybrid:
   │   a) STRUCTURED: SQL on `rules` for exact facts (deadline, caps, qualifying period)
   │   b) SEMANTIC: pgvector top-k over legislation + case_law + acas_guidance
   │   → returns CITED source bundle
   ▼
[3] REASON ── apply law-to-facts over the retrieved bundle
   │   workhorse tier; escalate only if low confidence AND solid grounding
   │   (escalation receives DE-IDENTIFIED context only)
   │   → produces STRUCTURED ASSESSMENT object (not prose)
   ▼
[4] SCORE ── grounding score + confidence score on the assessment
   ▼
[5] GOVERN ── gate:
   │   pass? → continue
   │   insufficient grounding/confidence? → flag uncertainty / route to human
   │   reserved-activity attempt? → block
   ▼
[6] RESPOND (+ GENERATE documents on paid path, template-anchored)
```

## 2. Stage 1 — Classification
- Input: free text and/or guided answers.
- Output: `{matter_type, intent, in_scope: bool}`.
- Method: rules for obvious cases; small/workhorse model otherwise.
- Out-of-scope (e.g. tenancy) → return "not supported", never a guess.

## 3. Stage 2 — Retrieval (hybrid RAG)

### 3a. Structured retrieval (deterministic — runs for every legal question)
Query `rules` by `claim_type` + `jurisdiction` + relevant date. Returns exact values WITH citations:
```json
{
  "time_limit_months": {"value": 3, "authority": "ERA 1996 s.111(2)", "url": "..."},
  "qualifying_period": {"value": "...", "authority": "...", "url": "..."}
}
```
These values are passed through verbatim. The model may EXPLAIN them but must NOT alter or re-derive them.

### 3b. Semantic retrieval (pgvector)
- Embed the query (+ key fact terms) with the same model used at ingest.
- Top-k cosine search across `legislation`, `case_law`, `acas_guidance`, filtered by `jurisdiction` and in-force date.
- Return chunks with `source_url`, citation, and similarity score.
- Tune k per source; prefer in-force/current rows (`effective_to IS NULL` or covering the relevant date).

### 3c. Bundle
```json
{
  "exact_rules": [ ... structured rows ... ],
  "authorities": [ {"type":"legislation","cite":"ERA 1996 s.98","text":"...","url":"..."},
                   {"type":"case_law","cite":"[YYYY] EAT ...","text":"...","url":"..."},
                   {"type":"acas","cite":"ACAS Code para 5","text":"...","url":"..."} ]
}
```
If the bundle is empty/weak for the question → mark `insufficient_grounding = true` and skip generative guessing.

## 4. Stage 3 — Reasoning (tiered)

### Tiers
- **Workhorse** (controlled, cheap): default. Handles classification + bulk reasoning.
- **Escalation** (stronger model): only when `confidence < threshold` AND grounding is solid. Receives **de-identified** context only (see §7).

### Job
Apply the retrieved authority to the user's facts and decide, per legal test, whether the fact pattern meets it. The model's role is the *judgment* layer, strictly bounded by the retrieved bundle.

### Output — the STRUCTURED ASSESSMENT object (canonical schema)
```json
{
  "claim_type": "unfair_dismissal",
  "jurisdiction": "EW",
  "has_viable_claim": "yes | no | uncertain",
  "strength": "low | medium | high | uncertain",
  "reasoning_summary": "plain-English, <= 150 words, no jargon",
  "value_range": {"low": 0, "high": 0, "currency": "GBP", "basis": "from rules + facts"},
  "key_weaknesses": ["what an opponent would attack", "..."],
  "deadline": {"limitation_date": "YYYY-MM-DD", "source": "rules", "authority": "ERA 1996 s.111(2)"},
  "recommended_next_step": "free_diagnosis_only | prepare_documents | seek_solicitor",
  "citations": [{"cite":"...","url":"..."}],
  "grounding_score": 0.0,
  "confidence_score": 0.0,
  "insufficient_grounding": false
}
```
> The assessment is data, not prose — so it can be validated, scored, and rendered consistently. Prose shown to the user is generated FROM this object.

## 5. Stage 4 — Scoring

- **Grounding score**: fraction of material claims in the assessment that map to a retrieved citation. Every legal assertion must trace to `citations`. Unsupported assertion → lower score.
- **Confidence score**: model-reported + heuristic (retrieval similarity, agreement across sources, fact completeness).
- Thresholds (tune empirically): below the grounding threshold OR below the confidence threshold → governance routes to uncertainty/handoff rather than display.

## 6. Stage 5 — Governance gate (the honesty layer in code)
Checks, in order:
1. **Grounding**: every legal claim cited? If not → strip/flag.
2. **Confidence**: above threshold? If not → "we can't say confidently" + route to human.
3. **Determinism**: deadlines/caps came from `rules`, not generation? (assert)
4. **Boundary**: output contains no reserved-activity action, no "we will file/represent", no outcome guarantee, no implication of being a solicitor.
5. **Honesty**: `key_weaknesses` populated when claim is non-trivial; weak/no-claim stated plainly.
Only a passing assessment proceeds to display/generation.

## 7. De-identification boundary (GUARDRAIL)
Before ANY call to a third-party/escalation model:
- Strip names, employer, addresses, dates-of-birth, contact details, case-identifying specifics.
- Send the abstracted legal question + retrieved authority, not raw personal facts.
- Re-attach identity locally after the model returns.
- Log boundary payloads in test to PROVE no personal data leaves (Phase 2 acceptance criterion).

## 8. Stage 6 — Generation (paid path)
- Template-anchored: legal structure comes from validated templates; the model fills/adapts from the assessment + facts.
- Documents: `particulars_of_claim`, `schedule_of_loss` (Phase 3); witness-statement structure, chronology, evidence checklist (Phase 4).
- Output marked as a user-owned self-help draft, not legal advice.

## 9. Failure & fallback behaviour (explicit)
| Situation | Behaviour |
|---|---|
| Out-of-scope matter | "Not supported" — no guess |
| Empty/weak retrieval | `insufficient_grounding` → honest uncertainty + route to human |
| Low confidence | "We can't say confidently" → recommend solicitor |
| Conflicting authorities | Surface the conflict + recommend human review; never pick silently |
| Third-party model needed | De-identify first; never send raw facts |
| Deadline/cap asked | Always from `rules`; model never recalls from memory |

## 10. What the brain must NEVER do
- Answer a legal question from model memory without retrieval.
- Generate or "recall" a deadline, cap, or threshold.
- Send raw personal/case data to a third-party model.
- State or imply certainty/outcome it cannot ground.
- Proceed when grounding/confidence is insufficient instead of flagging.
