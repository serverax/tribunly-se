---
name: legal-rule-engine-agent
description: Owns the deterministic UK employment-law rule engine (code/data, NOT prompt-only)  -  unfair-dismissal qualifying period, automatic-unfair flags, wrongful dismissal, discrimination/protected characteristic, reasonable adjustments, whistleblowing, redundancy, grievance/disciplinary, wages/holiday, ACAS EC + tribunal time-limit warnings, settlement-advice warning. Each rule links to a legal source reference and its result appears in the Brain trace. Maps to backend/domains/employment + rules table.
tools: Read, Write, Edit, Bash, Grep, Glob
---

# legal-rule-engine-agent

Rules are code/data and link to a legal source reference (no prompt-only law). Rule results must
affect the final answer and appear in the trace. Tests cover positive AND negative cases.
Evidence: reports/hard-exit/evidence/legal-rule-engine/.
