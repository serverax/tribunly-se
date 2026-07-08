# Fullstack Architect Review

Generated: 2026-07-08
Branch: `cc/convergence`
Measured against: live compose stack (15 services healthy)

## Findings

### P1 — Backend has no depends_on for tier-1/RAG services

**Problem:** Backend `depends_on` lists db, redis, ollama — but NOT rules-service, rag-service, graph-rag-service, redaction-service, or audit-service. If backend starts before these reach healthy, the first `/assess` call fails on service connections.

**Risk:** Race condition on cold start. Currently masked because backend retries internally and services boot fast. On slow hardware or constrained CI, the first request after `docker compose up` can hit an unhealthy upstream.

**Minimal fix:** Add `depends_on` with `condition: service_healthy` for the five upstream services. Cost: longer startup chain but guaranteed readiness. Alternatively, backend health should only report `ok` after pinging its upstreams (defense in depth).

### P1 — 8 orphan route modules registered on the backend router

**Problem:** `domain_routes.py`, `features_routes.py`, `feedback_routes.py`, `i18n_routes.py`, `reasoning_routes.py`, `sovereign_routes.py`, `chatbot/router.py`, `citation-guard/main.py` are registered but not backed by tested, wired services (matrix status: ORPHAN).

**Risk:** Attack surface. Each orphan route accepts HTTP requests. Unauthenticated orphan endpoints (e.g., `/api/feedback`, `/api/features/*`) could be probed. `reasoning_routes.py` exposes `/reasoning/stream` which calls the LLM — functional but unaudited for rate limiting and auth.

**Minimal fix:** For beta, fence orphan routes behind a beta-disabled flag or remove their router registrations. Preserve the code for post-beta enablement. Priority: `reasoning_routes.py` (LLM-calling) and `chatbot/router.py` (user-facing) first.

### P2 — Single-brain integrity confirmed post-repoint

**Observed:** After WO006, `grep -r "host.docker.internal:11434" backend/` returns 0 hits in Python source. All Ollama URL resolution chains (`brain.py` → `models.py` → `inference_policy.py`) read `LAWAPP_OLLAMA_BASE_URL` which compose sets to `http://ollama:11434`. `/health` confirms `base_url: http://ollama:11434`. Brain integrity: INTACT.

### P2 — Module registry IS jurisdiction-parameterized (ready for SE)

**Observed:** `backend/domains/registry.py:63` initializes from domain packs. `pack_contract.py:28-29` defines `jurisdiction: list[str]` and `country_code: str` per domain spec. `registry.py:156` has `jurisdiction_supported_for_domain(domain, jurisdiction)` that checks membership. The data layer (rules table `jurisdiction` column) and orchestration layer (domain registry) are both ready.

**Risk:** Low. Adding Scotland/SE requires: (a) a new domain pack directory with SE-specific rules, (b) SE rules in the rules table, (c) SE-specific graph nodes. The registry plumbing exists; the content does not yet.

**Gap:** The brain's `detect_jurisdiction` (brain.py:600-604) currently reads `facts.jurisdiction` but doesn't validate it against the registry's supported list before proceeding. An unsupported jurisdiction silently falls through to EW defaults rather than returning `not_supported`.

### P3 — Embedding model not in Ollama registry

**Problem:** `bge-large-en-v1.5` (the RAG embedding model) is not natively available via `ollama pull`. The compose stack starts healthy, but RAG query-time embedding fails with HTTP 404 from Ollama. Ingestion embedding also fails.

**Risk:** RAG retrieval path is broken at runtime. The brain falls back to rules-only (which works), but vector similarity search over `corpus_chunks` is unavailable until the embedding model is imported or swapped.

**Minimal fix:** Either (a) import `bge-large-en-v1.5` as a custom Ollama model from GGUF, or (b) swap to `nomic-embed-text` (Ollama-native, 768-dim) and re-embed corpus. Option (b) requires schema migration (1024→768). Recommend (a) for minimal disruption.

### P3 — Ollama has no GPU passthrough in compose

**Problem:** The `ollama` service definition has no `deploy.resources.reservations.devices` for GPU passthrough. On GPU-capable hosts, Ollama runs CPU-only inside compose, causing 50s+ inference latency per call.

**Risk:** 120s total assessment latency makes the product feel broken. CPU inference on qwen2.5:3b-instruct-q6_K produces ~3 tokens/sec.

**Minimal fix:** Add optional GPU reservation via compose deploy block (requires `docker compose` v2.22+ with GPU support). Document as opt-in for GPU hosts.
