# UI/UX Review

Generated: 2026-07-08
Branch: `cc/convergence`
Measured against: live surface at `localhost:8000`

## Assessment Rendering — Does the Deadline Dominate?

**Finding (P1 — conversion impact: HIGH):** No. The deadline card renders 4th in the assessment result, after: (1) viability card, (2) tribunal checklist, (3) save section. On mobile (360px), a user must scroll past ~3 screens of content before seeing their deadline. The deadline is the product's core promise — "understand your deadline" — but the page buries it.

**Rendering order** (`assessment.html:241-251`):
1. `renderViabilityCard` — strength badge + reasoning summary
2. `renderTribunalChecklist` — checklist of legal elements
3. `renderSaveSection` — save-to-account CTA
4. `renderDeadlineCard` — **the deadline** (navy/red card, 2.8rem days count)
5. `renderWeaknessSection` — key weaknesses
6. `renderEmployerSection` — employer arguments
7. `renderValueRange` — compensation estimate
8. `renderNextStep` — recommended action
9. `renderDocumentSection` — paid docs CTA
10. `renderHandoffSection` — solicitor referral
11. `renderCitations` — legal citations

**Styling observation:** When visible, the deadline card IS dominant — navy gradient, 2.8rem days counter, urgent variant turns red. The styling is correct; the position is wrong.

**Fix (in-scope, copy/layout):** Move `renderDeadlineCard` to position 1 or 2. Deadline first, then viability. The user's most urgent question is "how long do I have?" not "how strong is my case?"

### P1 — 120-second blank loading state

**Problem:** After intake submission, the assessment page shows "Loading your assessment..." spinner for ~120 seconds (full Ollama inference time). No progress indication, no partial results, no timeout message. Users will assume it's broken and leave.

**Risk:** Catastrophic for conversion. 120s of spinner is unacceptable for a consumer product.

**Minimal fix (Phase C spec):** Progressive render — paint the deterministic lane (deadline, viability skeleton, citations) in <1s from `use_model=false` response (measured: 200ms), then stream the reasoning summary via `/reasoning/stream` SSE. See AI_ARCHITECT_REVIEW.md for the spec.

### P2 — Weakness section readability

**Problem:** `key_weaknesses` renders as a plain `<ul>` with no visual weight. On the live assessment, weaknesses like "Early Conciliation: claimant must notify ACAS" are critical action items but visually identical to informational text. They don't stand out from the surrounding content.

**Fix (in-scope, styling):** Add a warning-yellow left border or background to the weaknesses list. Use `role="alert"` on deadline-critical weaknesses (EC requirement).

### P2 — Intake wizard has no estimated time

**Problem:** The intake form (`intake.html`) has a progress bar and step labels but no "this takes about 5 minutes" indicator on the form itself. The landing page says "5 minutes" but by the time the user reaches intake, that context is gone.

**Fix (in-scope, copy):** Add time estimate to the intake page header, matching the landing page promise.

### P2 — Error states are honest but generic

**Problem:** The assessment error state ("Your session may have expired") and the insufficient-grounding state both route to "complete the intake form again." For expired sessions, this is correct. For insufficient grounding, the user already completed intake — the issue is their facts, not their session.

**Fix (in-scope, copy):** Differentiate the two error paths. Insufficient grounding should say "We need more detail about [specific missing fact]" not "complete the intake form again."

### P3 — Trust signals placement

**Observed:** Trust bar ("11 topics in controlled beta / Grounded citations / Local AI / Not a law firm") sits below the hero fold on landing. Legal notice ("Not a law firm. Not legal advice.") is persistent at top of every page. Footer repeats the disclaimer. Trust presentation is honest and consistent.

### P3 — Mobile ergonomics

**Observed:** Responsive CSS handles 360px cleanly — deadline card stacks vertically, wizard nav goes full-width, grid columns collapse. Skip links present. Mobile menu button has aria-label. No horizontal overflow (verified in responsive matrix). Accessibility bar (A+, Easy read, High contrast) is present on landing.
