# Gemini LawApp Repair Plan (Updated)

## 1. COMPLETED Fixes (Phase 9)

These changes were executed successfully.

- **SEC-001 (XSS)**: Refactored `assessment.html`, `intake.html`, and `saved_case.html` to remove all `innerHTML` usage. [DONE]
- **RH-001 (Hygiene)**: Removed `.docx` and `.zip` files from git index and updated `.gitignore`. [DONE]
- **K8S-001 (K8s)**: Replaced `:latest` image tags with `${GIT_SHA}` placeholders. [DONE]
- **BUG-001 (Deps)**: Added `python-multipart` and `sentence-transformers` to the environment. [DONE]

## 2. Immediate Next Steps (Gemini/Claude)

- **Phase 10: WASM Subsystem**: Scaffold the `wasm/` directory using the **Rust toolchain** now available. Implement the core deadline arithmetic in Rust/WASM to provide robust, client-side verified logic.
- **Phase 11: Auth UI**: Build the frontend Login and User Dashboard using the **Node.js/npm** toolchain. Implement JWT handling on the client side to match the existing backend support.

## 3. Fixes Requiring Owner Action

- **Secrets Rotation**: Leaked keys in local `.env` must be rotated.
- **OpenAI Quota**: Billing/limits must be addressed to unblock the 15 skipped semantic retrieval tests.
- **FCL Licence**: Bulk case law ingestion remains blocked until the licence is granted.

---

## Toolset Ready for Next Phases

I have confirmed the following tools are available and will be used:
- **Rust Toolchain & Cargo**: For Phase 10 (WASM construction).
- **Node.js & npm**: For Phase 11 (Auth UI and Dashboard).
- **PostgreSQL tools**: For direct database schema validation if needed.
- **Security Scan tools**: For periodic automated hardening checks.
- **Docker/Kubernetes CLI**: For staging deployment verification (read-only).
