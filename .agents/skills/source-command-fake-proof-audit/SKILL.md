---
name: "source-command-fake-proof-audit"
description: "Hunt for fakes  -  stubs, placeholder logic, static success, mock auth/payment, fabricated citations, uncited legal rows."
---

# source-command-fake-proof-audit

Use this skill when the user asks to run the migrated source command `fake-proof-audit`.

## Command Template

# /fake-proof-audit

Scan for anything that fakes readiness.

## Steps
1. Grep for placeholder/stub/static-success patterns in `backend/`, `services/`, `client/`.
2. Check routes for static JSON success not calling real logic.
3. Check auth (no prod mock / X-User-ID trust), payment (no bypass/raw-token unlock).
4. Check legal data: no fake/placeholder/uncited rows; CitationGuard rejects fabricated UUIDs.
5. Check frontend: no mock API as product proof, no dead buttons.
6. Write findings to `reports/hard-exit/fake-stub-scan.txt`.

## Output
Findings list (file:line) + severity. Any fake in the product path = REJECT.
