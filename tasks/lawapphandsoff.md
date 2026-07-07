> SUPERSEDED - see docs/handoff/LAWAPP_CURRENT_STATE.md. Do not act on this document.

# LAWAPP PROJECT HANDOFF

## Vision

LawApp is not another legal chatbot.

Most legal AI products answer questions.

LawApp solves a legal problem from start to finish.

The user arrives worried, confused, and unsure if they have a claim.

LawApp should:

1. Diagnose the case.
2. Explain strengths and weaknesses honestly.
3. Calculate deadlines.
4. Generate tribunal-ready documents.
5. Track the claim.
6. Escalate to a solicitor when needed.

The core market position is:

**"The UK's most honest employment law AI assistant."**

Never promise success.

Never exaggerate.

Never behave like a solicitor.

---

# Target User

Typical users:

* Dismissed employees
* Redundancy victims
* Unfair dismissal claimants
* Whistleblowers
* Employees facing discrimination
* Employees owed wages
* People who cannot afford a solicitor

---

# What Makes LawApp Different

Current market:

* Generic legal chatbots
* Law firm websites
* Expensive solicitors
* Generic AI assistants

Gap:

Nobody combines:

* Diagnosis
* Deadline tracking
* Tribunal documents
* Honest assessment
* Human escalation

inside one workflow.

LawApp must become:

**"TurboTax for Employment Law."**

---

# User Journey

## Step 1 – Landing Page

User visits:

```text
lawapp.co.uk
```

First screen:

Headline:

"Find out if you have an employment claim in minutes."

Subtext:

* Free diagnosis
* Deadline tracker
* Tribunal documents
* Human solicitor handoff

Buttons:

```text
Start Free Assessment
```

```text
Check My Deadline
```

```text
See Example Cases
```

Visuals:

* Animated timeline
* Tribunal workflow
* Progress indicators

Not corporate.

Not law-firm style.

Modern.

Trustworthy.

Fast.

---

# Step 2 – Free Assessment

Wizard style.

One question at a time.

Examples:

```text
Were you dismissed?
```

```text
When were you dismissed?
```

```text
How long did you work there?
```

```text
Why were you dismissed?
```

Progress indicator:

```text
Question 4 of 15
```

User should never feel overwhelmed.

---

# Step 3 – AI Analysis

LawApp runs:

Classification

↓

Rules Engine

↓

RAG

↓

Graph RAG

↓

Reasoning

↓

Governance

↓

Assessment

User receives:

### Claim Strength

High

Medium

Low

Uncertain

### Deadline

Limitation date

### Estimated Value

Compensation estimate

### Weaknesses

Most important section.

LawApp must be brutally honest.

Example:

```text
Your claim appears weak because you only worked for your employer for 11 months.
```

---

# Step 4 – Dashboard

After registration.

User sees:

## My Cases

Cards:

* Case status
* Deadline
* Strength
* Last activity

Example:

```text
Unfair Dismissal
High Strength
Deadline: 15 July 2026
```

---

# Step 5 – Deadline Center

Dedicated screen.

Shows:

Timeline

Today

↓

ACAS

↓

ET1 Deadline

↓

Hearing

Countdown:

```text
45 days remaining
```

Red warning:

```text
Deadline approaching
```

---

# Step 6 – Documents

Paid area.

User can generate:

### Phase 1

* Particulars of Claim
* Schedule of Loss

### Phase 2

* ET1 Support Notes
* Witness Statement
* Chronology
* Evidence Bundle

Preview:

PDF viewer

Download

Word

PDF

---

# Step 7 – Case Timeline

Every event tracked.

Example:

```text
Dismissed
```

↓

```text
ACAS Started
```

↓

```text
Certificate Received
```

↓

```text
ET1 Drafted
```

↓

```text
Solicitor Escalation
```

---

# Step 8 – Beyond Self Help

Complex cases trigger:

```text
You should speak with a solicitor.
```

User can:

* Request callback
* Upload documents
* Send assessment

LawApp prepares the lead package.

---

# Future AI Modules

LawApp architecture must support:

### Employment

Current

### Housing

Future

### Benefits

Future

### Immigration

Future

### Debt

Future

Same platform.

Different rules.

Different RAG.

Different templates.

Same engine.

---

# Technical Architecture

Frontend

```text
Next.js
Tailwind
Motion UI
```

Backend

```text
FastAPI
Python
```

Database

```text
PostgreSQL
pgvector
```

AI

```text
Classification
RAG
Graph RAG
Reasoning Engine
Governance Layer
```

Storage

```text
Documents
Evidence
Generated Files
```

Deployment

```text
Docker
Kubernetes
CloudStack
```

---

# AI Pipeline

User Facts

↓

Classification

↓

Rules Lookup

↓

RAG Retrieval

↓

Graph RAG

↓

Reasoning

↓

Scoring

↓

Governance

↓

Assessment

↓

Document Generation

↓

User

The AI never skips retrieval.

The AI never invents legal facts.

---

# UI Style

Not a law firm.

Not government.

Not corporate.

Use:

* Smooth animations
* Progress bars
* Timelines
* Case cards
* Visual deadline alerts
* Mobile-first design

Feel:

```text
Modern SaaS
+
Legal Trust
+
Simple Language
```

Examples:

* Linear
* Stripe
* Notion
* Modern fintech apps

Avoid:

* Old legal websites
* Long forms
* Dense text
* Corporate blue pages

---

# Success Criteria

A new user can:

1. Land on website.
2. Complete assessment.
3. Understand strengths and weaknesses.
4. See deadline.
5. Pay.
6. Download documents.
7. Return later.
8. Escalate to solicitor if required.

Without speaking to support.

That is the LawApp experience.
