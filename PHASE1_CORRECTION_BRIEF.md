# Phase 1 Correction Brief — for the coding agent

**Context:** Phase 1 reported "PASS pending FCL grant" with 17/17 tests passing. The legal-correctness audit found that the tests validate code against the seed, not the seed against the law. Several `rules` values are likely stale or incomplete. Do NOT treat Phase 1 as passed for the rules-dependent paths until every item below is closed.

**Hard rule for this work:** every figure below must be confirmed against `legislation.gov.uk` (and, for the prospective changes, the Employment Rights Act 2025 text and the relevant commencement regulations) before it is committed. The values given here are the expected current answers so you can detect stale data; they are NOT a substitute for fetching the source. Record the source URL, version/date, and the value as it appears, for every row.

---

## 1. Methodology fix (do this first)

The accuracy tests must validate the seed against an independent source of truth, not against itself. For each `rules` row:
- Store the `legislation.gov.uk` (or ERA 2025 / SI) URL actually fetched, the version date, and the verbatim value from the source.
- Add a verification test that asserts the stored value equals the value at the cited source, not a hardcoded fixture written alongside the seed.
- A test that only confirms "the code returns what the seed says" does not count as passing for legal correctness.

---

## 2. Values to re-verify and correct

### 2.1 Compensatory award cap (likely STALE)
- Expected current value, in force from 6 April 2026: **£123,543** (Employment Rights (Increase of Limits) Order 2026).
- Previous value (6 April 2025): £118,223. If the table returns £118,223 as "current", it is one uprating cycle out of date and acceptance criterion 2 fails.
- Action: confirm the table returns £123,543 for today's date, effective-dated from 6 April 2026, with the correct SI as authority.

### 2.2 Week's pay cap (check alongside)
- Expected current value from 6 April 2026: **£751** (up from £719 on 6 April 2025).
- Action: confirm current value and effective date.

### 2.3 Qualifying period (check the prospective change is present)
- Current: **2 years**.
- Changes to **6 months from 1 January 2027** (Employment Rights Act 2025, s.25), applying where the effective date of termination is on or after 1 January 2027.
- Action: the table must hold both values, effective-dated, and the eligibility logic must select by EDT. This is the rule that decides whether a user has a claim at all; it cannot be a single static value.

### 2.4 Verify the cited authorities
- `Haque para 17` (used as `authority_ref`) and `Haque para 26` (EC stop-the-clock regression): confirm the case exists, that those paragraphs say what is claimed, and explain why a case anchors a deterministic rule rather than the statute. The limitation period is statutory (ERA 1996 s.111(2)); the Early Conciliation extension is statutory (confirm s.207B ERA 1996). Deterministic rules should cite the statute as primary authority, with a case only as interpretation.
- `SI 2025/348` and `SI 2026/310`: confirm these are the correct SI series numbers for the 2025 and 2026 Increase of Limits Orders. Plausible but unverified; trivial to confirm on legislation.gov.uk.

---

## 3. Prospective branches that must exist (effective-dated, date-selected)

The engine's structured-rules retrieval, deadline logic, and value-range logic must select the correct rule by the relevant date, never hardcode the current regime. Three changes are coming:

1. **Tribunal time limit: 3 months less one day → 6 months.** Coming into force **no earlier than October 2026** for most claims, including unfair dismissal. The date is not yet fixed ("no earlier than"), so:
   - Encode the 6-month rule as `is_prospective` with `effective_from` left to be set on confirmed commencement.
   - The live deadline engine must read the limit from `rules` by date, not hardcode "3 months less one day". When commencement is confirmed, only the `rules` row changes.
   - Current behaviour (3 months less one day) is correct for now and must remain until the confirmed date.

2. **Qualifying period: 2 years → 6 months, from 1 January 2027** (see 2.3).

3. **Compensatory cap removed entirely from 1 January 2027** for ordinary unfair dismissal (ERA 2025 removes ERA 1996 s.124). The `value_range` logic needs an uncapped branch from that date: capped through 31 December 2026, uncapped from 1 January 2027. Note for the assessment layer: removal of the cap does not mean large awards; awards remain based on actual loss, and the historical median is low. Do not let "uncapped" inflate the value range.

---

## 4. Smaller item

- ACAS Code ingestion is **2 chunks** from the March 2015 Code. The 2015 edition is still current, so the version is right, but two chunks almost certainly under-ingests a Code whose paragraphs drive the up-to-25% award adjustment the diagnosis relies on. Re-check coverage; ingest the full Code structure, not a fragment.

---

## 5. Phase 2 gate (the decision)

- Phase 2 may proceed now on classification and the orchestration skeleton, which do not depend on these values.
- **Hold** the structured-rules retrieval, deadline, and value-range paths until sections 2 and 3 above are closed and independently source-verified. These paths are not stubbed in the engine, so they will carry any wrong value straight into the assessment shown to a user.
- Semantic retrieval, embeddings, and FCL bulk remain correctly blocked as reported; no change there.

---

## 6. What was correct (leave alone)

The FCL bulk gate as a hard `RuntimeError`, content-hash change detection, the effective-dated `rules` structure, the de-identification gate on embeddings, and submitting the FCL application on day one are all correct. The problem is specific to the values and the missing prospective branches, not the architecture.

---

*All legal figures and dates in this brief were verified against current public sources as at the date of writing. The agent must still confirm each against legislation.gov.uk / the ERA 2025 text before committing, per the project's grounding guardrail.*
