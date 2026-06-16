# lawapp Design System

Generated from `client/public/css/styles.css`. Tokens live in `client/public/design-tokens.json`.

## Design Principles

lawapp's brand promise is **"honest, cited, no overpromising"**. The UI must match that:

- **Tool, not product**  -  this is a legal instrument, not a consumer app. No gradients, no hero illustrations, no personality flourishes.
- **Authority through restraint**  -  navy + white + one orange CTA. Every colour addition requires justification.
- **Urgency is earned**  -  red is reserved for deadlines and errors. Don't dilute it.
- **Clarity first**  -  tight line-height on headings, generous line-height on body. The user is reading legal information under stress.

---

## Colour

### Brand
| Token | Value | Use |
|---|---|---|
| `--primary` / `brand-900` | `#1a3a5c` | Nav, headings, deadline card, next-step bg |
| `brand-700` | `#1e4d7a` | Hover/focus states |
| `brand-100` | `#e8f0f8` | Brand-tinted surfaces |

### Accent
| Token | Value | Use |
|---|---|---|
| `--accent` | `#e84f25` | Primary CTA button **only**. One per page maximum. |

> **Rule:** Do not use `--accent` for anything that isn't the primary action. Secondary actions use `--primary` (filled) or `--primary` (outline).

### Status Colours
These were previously hardcoded Bootstrap 4 values scattered across badge rules. They are now named:

| Token | Surface | Text | Border | Use |
|---|---|---|---|---|
| `danger-*` | `#f8d7da` | `#721c24` | `#c0392b` | Errors, badge-no, badge-low |
| `success-*` | `#d4edda` | `#155724` | `#1e7e34` | OK, badge-yes, badge-high |
| `warning-*` | `#fff3cd` | `#664d03` | `#ffc107` | Legal notice, grounding alert, badge-uncertain |

> **Issue found:** The existing CSS has 8+ hardcoded hex values for these states. They should be migrated to CSS custom properties to enable future theming.

---

## Typography

### Font Stack
`'Segoe UI', system-ui, sans-serif`  -  system font stack, zero webfont load. Appropriate for a tool that users may access urgently (e.g. missed deadline warning). Do not add a webfont without measuring the tradeoff.

### Scale
The original CSS had **17 distinct font sizes**. This is the reduced scale:

| Token | Value | Use |
|---|---|---|
| `--text-xs` | `0.75rem` | Wizard step labels, small badges |
| `--text-sm` | `0.875rem` | Hints, citations, legal notice, form-error |
| `--text-base` | `1rem` | Body, inputs, buttons, list items |
| `--text-md` | `1.05rem` | Next-step text, card section headings |
| `--text-xl` | `1.25rem` | Nav brand, assessment h2 |
| `--text-hero` | `clamp(1.45rem, 4vw, 2.2rem)` | Hero h1 only |
| `--text-deadline` | `2.5rem` | Deadline days-remaining number only |

> **Rule:** If a new font size is needed, use the nearest token. If none fits, add a token here first.

---

## Spacing

8px base scale. All padding/margin/gap values must be a multiple of `4px`.

| Token | Value | Common use |
|---|---|---|
| `--space-1` | `0.25rem` (4px) | Fine gaps, small internal padding |
| `--space-2` | `0.5rem` (8px) | Radio gap, badge padding |
| `--space-3` | `0.75rem` (12px) | Nav padding, form-group margin |
| `--space-4` | `1rem` (16px) | Standard padding |
| `--space-5` | `1.25rem` (20px) | Form-group margin, card inner spacing |
| `--space-6` | `1.5rem` (24px) | Section padding, page padding |
| `--space-8` | `2rem` (32px) | Page padding top |
| `--space-10` | `2.5rem` (40px) | Deadline days number context |
| `--space-12` | `3rem` (48px) | Hero top padding, footer margin |

> **Issue found:** Current CSS uses arbitrary values like `0.35rem`, `0.55rem`, `0.875rem` for spacing. These should be snapped to the nearest token value.

---

## Border Radius

| Token | Value | Use |
|---|---|---|
| `--radius` | `6px` | Cards, inputs, buttons, all standard elements |
| `--radius-pill` | `20px` | Badges only |
| `--radius-full` | `50%` | Spinner, wizard step-number circles |

---

## Shadows

One shadow level only. lawapp is not a layered app  -  no elevation system needed.

| Token | Value | Use |
|---|---|---|
| `--shadow` | `0 1px 3px rgba(0,0,0,0.12)` | Cards, form sections |

---

## Breakpoints

| Name | Value | Change |
|---|---|---|
| `md` | `768px` | Stack deadline card, reduce wizard step labels, stack case headers |
| `sm` | `480px` | Hide nav links (show hamburger if added), full-width buttons, hide wizard step text labels |

---

## Component Rules

### Buttons
- **One `btn-primary` (accent) per page.** It is the single most important action.
- Secondary: `btn-secondary` (navy filled) for second-priority actions.
- Tertiary: `btn-outline` (navy border) for low-priority or destructive actions.
- Disabled: `opacity: 0.45`. Never remove disabled state.

### Badges
- `badge-yes` / `badge-high` → success palette
- `badge-no` / `badge-low` → danger palette
- `badge-uncertain` / `badge-medium` → warning palette

### Deadline Card
- Default: `--primary` (navy) background  -  deadline is safe.
- `.deadline-urgent`: `--warn` (red) background  -  ≤30 days.
- `.deadline-card .days` always uses `--text-deadline` (2.5rem). Do not reduce this.

### Legal Notice
- Always present. Always `background: warning-100`, `border-left: 4px solid warning-border`.
- Never style it to look less prominent. It is a legal requirement.

---

## What NOT to do

- No gradients anywhere.
- No box shadows beyond `--shadow`.
- No colour outside this token set without a written rationale.
- No font size outside the scale.
- No `!important` except in the responsive overrides for inline `style` grid columns (already present).
- Do not add a dark mode until the light mode is fully consistent.
