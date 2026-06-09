# lawapp MVP — End-to-End Proof Report

- **Timestamp:** 2026-06-05  **Branch:** main  **Commit:** a0968b0
- **Command:** `bash scripts/prove_mvp_user_journey.sh` (+ 7 component proofs, + full regression)
- **Status:** MVP journey **PASS**; only Find Case Law bulk remains **OWNER-BLOCKED**.

## Files changed (this phase)
- `backend/api/main.py` — `/documents/generate` now **fail-closed grounding gate**:
  refuses (HTTP 422) when the assessment is `insufficient_grounding`, `not_supported`,
  or `jurisdiction_supported=false`.
- (Prior phase, underpinning the journey) `backend/core/retrieve.py` +
  `backend/core/pipeline.py` — jurisdiction_code filtering, NI fail-closed,
  `legal_retrieval_audit` + `deadline_calculation_audit` writes.

## Migrations changed
None new this phase. Journey runs on the spine migrations 028–035 (already applied).

## Routes used / changed
| route | role | change |
|---|---|---|
| `POST /assess` | cited diagnosis + deadline | (prior) jurisdiction-filtered + audited |
| `POST /api/payment/create-session` | test-payment path | unchanged (test_simulator) |
| `POST /documents/generate` | Particulars/Schedule | **+grounding gate (422)** |
| `GET /api/documents/{id}/download` | download | unchanged |
| `POST /handoff/leads` | free referral capture | unchanged (consent-gated) |

## Frontend pages (verified, all served 200)
intake.html (wired to `/assess`), assessment.html (renders citation/deadline/weakness),
dashboard.html, case_detail.html, saved_case.html, constructive_dismissal.html,
login/register, success/cancel. **Boundary notice present on all 10 pages.**

## Exact commands + PASS output
```
prove_mvp_user_journey.sh ............... MVP USER JOURNEY PROOF: PASS
prove_frontend_backend_wiring.sh ....... FRONTEND/BACKEND WIRING PROOF: PASS
prove_document_generation.sh ........... DOCUMENT GENERATION PROOF: PASS
prove_deadline_tracker.sh .............. DEADLINE TRACKER PROOF: PASS
prove_handoff_workflow.sh .............. HANDOFF WORKFLOW PROOF: PASS
prove_legal_boundary_notices.sh ........ LEGAL BOUNDARY NOTICES PROOF: PASS
prove_no_fake_claims_or_uncited_law.sh . NO FAKE CLAIMS / UNCITED LAW PROOF: PASS
```
(Plus the 14 legal-spine proofs from the prior phase — all PASS.)

## Journey evidence (hostile end-to-end)
1. **Land/intake** — `/pages/intake.html`, `/pages/assessment.html` served (200).
2. **/assess** — status=ok, **8 citations**, deadline **2024-07-31** (source=`rules`),
   **6 key_weaknesses** shown.
3. **Test payment** — `/api/payment/create-session` returns
   `{mode, session_id, payment_token, checkout_url, price_gbp, document_type}`.
4. **Document generation (paid)** — schedule_of_loss (13,176 chars) +
   particulars_of_claim (12,728 chars); `disclaimer_included=true`,
   `safety_check.passed=true`, no reserved-activity wording.
5. **Fail-closed** — ungrounded assessment → **HTTP 422** (no document).
6. **Handoff** — consented lead → **201** (free); no consent → **422**; bad trigger → 422.
7. **Audit** — `legal_retrieval_audit` 29→30, `deadline_calculation_audit` 18→19.

## DB audit row counts (before → after a single journey run)
- legal_retrieval_audit: 29 → 30
- deadline_calculation_audit: 18 → 19

## Sample assessment JSON (GB, abbreviated)
```json
{
  "status": "ok",
  "jurisdiction": "EW",
  "has_viable_claim": "no",
  "strength": "low",
  "grounding_score": 1.0,
  "insufficient_grounding": false,
  "deadline_info": {"limitation_date": "2024-07-31", "source": "rules",
                     "authority": "ERA 1996 s.111(2)"},
  "key_weaknesses": ["Qualifying period not met: ~8 months service, 2 years required ...", "..."],
  "citations": [
    {"cite": "ERA 1996 s.108(1); SI 2012/989 ...", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/108"},
    {"cite": "ACAS Code of Practice on Disciplinary and Grievance Procedures", "url": "https://www.acas.org.uk/..."},
    {"cite": "ERA 1996 s.124; SI 2024/213", "url": "https://www.legislation.gov.uk/uksi/2024/213"}
  ]
}
```

## Sample generated document proof
- `POST /documents/generate {document_type: schedule_of_loss, payment_token: test_*}`
  → `payment_required=false`, `disclaimer_included=true`,
  `safety_check.passed=true`, content length **13,176** chars, marked self-help draft.
- Unpaid request → `payment_required=true` + truncated preview (shorter than full).
- Ungrounded assessment → **HTTP 422** (no document produced).

## Deadline tracker evidence (rules-backed)
- No EC: EDT 2024-05-01 → **2024-07-31** (source=rules).
- EC stop-the-clock: deadline shifts off the base date.
- EC floor bites: Day B 2024-07-29 → **2024-08-29** (1 month after Day B).
- missing EDT → `missing_edt`; invalid date → `invalid_date` (fail-closed).
- `tests/test_deadline.py` passes.

## Known blockers (external owner/licence only)
- **Find Case Law bulk ingestion** — BLOCKED BY OWNER (computational-analysis licence
  pending). case_law empty, fail-closed, blocker recorded. Everything else green.
- **Live solicitor integration** — out of scope per the order; the handoff trigger +
  capture workflow is implemented and proven (free to the user).

## Honest note on full pytest
`scripts/prove_full_regression.sh` runs all 21 proofs + the full `pytest -q` suite;
its captured output is the authoritative regression record (see run log). Any
pre-existing unrelated failures are reported there, not hidden.
