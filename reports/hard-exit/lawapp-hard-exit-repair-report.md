# LawApp  -  Hard-Exit Blocker Repair Report

**Branch:** `recovery/lawapp-autonomous-stabilisation`
**Started:** 2026-06-06
**Mode:** Autonomous repair (owner pre-approved continuation; stop only for owner-only credential/destructive actions)
**Current verdict:** 🔴 **NOT READY  -  LAWAPP HARD BLOCKERS REMAIN**

Blockers: G1 (brain 503 / DB pw) · G2 (leaked PATs in history) · G3 (CI red: WASM + pip-audit) · G10 (legal-data provenance).
Evidence is command-based. Secrets are never printed raw (redacted).

---

## Phase 1  -  Repo / safety state ✅

```
branch  : recovery/lawapp-autonomous-stabilisation
remotes : origin git@github.com:serverax/lawapp.git (SSH  -  no embedded credentials)
HEAD    : bcb5240 fix(deploy): guard lawapp-ai-secrets apply (never overwrite empty CI secrets)
```
Working tree: task-001 scaffolding + UI redesign + this report (no app-logic changes pending).

---

## G2  -  Leaked PATs in git history  -  🟡 AUTONOMOUS PARTS DONE, OWNER ACTION REMAINS

| Item | Status | Evidence |
|---|---|---|
| Remotes carry no embedded credentials | ✅ PASS | `git remote -v` → SSH `git@github.com` |
| Working tree free of real PATs | ✅ PASS | precise scan `ghp_{36}` / `github_pat_{40+}` → `NONE_IN_HEAD` |
| Fake test fixture neutralised | ✅ PASS | `tests/security/test_auth_routes.py:168` marked `# pragma: allowlist secret (fake fixture)` |
| Secret-scan script exists + fails on tokens | ✅ PASS | `scripts/security/scan-secrets-history.sh` |
| Scanner positive test (clean tree) | ✅ PASS | exit 0, "no leaked secrets" |
| Scanner negative test (real-shaped `ghp_` token) | ✅ PASS | staged probe → exit 1, redacted `ghp_[REDACTED]`, cleaned up |
| Real PATs in history | ⚠️ PRESENT | blobs: `a0968b0:package.json`, `a0968b0:tasks/multiagentlawapp.md`, `e165295:package.json` (redaction commit `6c5882e`) |
| Rotate/revoke PAT in GitHub | ⛔ OWNER ONLY | see action below |
| History rewrite + force-push | ⛔ OWNER ONLY (destructive) | see action below |

**Commands run**
```
git remote -v
git grep -lI -E 'ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}'            # HEAD: NONE
git log --all --oneline -G 'ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}' # 6c5882e a0968b0 e165295
bash scripts/security/scan-secrets-history.sh        # tree PASS, history WARN
SCAN_HISTORY=0 bash scripts/security/scan-secrets-history.sh   # CI gate PASS
# negative test: staged ghp_<36> probe -> FAIL exit 1 -> cleaned up
```

**Files changed:** `scripts/security/scan-secrets-history.sh` (new), `tests/security/test_auth_routes.py` (pragma only).

**OWNER ACTION REQUIRED (G2 cannot be PASS until done):**
1. **Rotate/revoke** the exposed GitHub PAT(s) at GitHub → Settings → Developer settings → Personal access tokens. (Owner-only; account action.)
2. **Rewrite history** to purge blobs in `a0968b0`/`e165295` (`git filter-repo --path package.json --path tasks/multiagentlawapp.md --invert-paths` or BFG), then **force-push**. (Owner-approved destructive step  -  not performed autonomously.)
- Exact target blobs: `package.json`, `tasks/multiagentlawapp.md` in commits `a0968b0`, `e165295`.

**G2 verdict:** working-tree + scanner gate = PASS; **history remediation = OWNER ACTION REQUIRED** → G2 not fully closed.

---

## G3  -  CI red (WASM + pip-audit)  -  ✅ FIXED & PROVEN

### WASM
| Item | Status | Evidence |
|---|---|---|
| Rust source present | ✅ | `client/wasm/src/lib.rs`, `notice.rs`, `Cargo.toml` |
| Toolchain present | ✅ | `cargo`, `rustc`, `wasm-pack` in WSL |
| Build works + reproducible | ✅ | `wasm-pack build --target web` → `Finished release profile`; sha256 BEFORE==AFTER `23dd91cec725…` |
| Root cause of CI failure | ✅ | `client/public/wasm/.gitignore` was `*` → binary untracked → CI `test -f` failed |
| Fix: track artifacts | ✅ | `.gitignore` rewritten (allowlist); `git ls-files` now lists `lawapp_wasm_bg.wasm` + js/d.ts/package.json |
| CI check simulation | ✅ | `test -f client/public/wasm/lawapp_wasm_bg.wasm` → PRESENT |

### pip-audit
| Item | Status | Evidence |
|---|---|---|
| Real CI failure identified | ✅ | faithful `pip install -e .` env → 6 CVEs in **pip 24.0 + wheel 0.45.1** (base-image build tools, NOT app deps); `diskcache` ABSENT in CI env |
| Fix proven | ✅ | `pip install --upgrade pip setuptools wheel` then audit → **"No known vulnerabilities found"** RC=0 (pip 26.1.2) |
| CI step patched | ✅ | `.github/workflows/lawapp-ci.yml` SCA step upgrades toolchain before audit (still fail-closed) |
| Bonus: dead vuln dep removed | ✅ | `dspy-ai>=2.4` removed from `Dockerfile.ingestion` (pulled vulnerable `diskcache` via dspy; `dspy_available()` hard-returns False  -  local-Ollama mandate; no tests reference dspy) |

### Secret-scan gate wired
- `.github/workflows/lawapp-ci.yml` now runs `SCAN_HISTORY=0 bash scripts/security/scan-secrets-history.sh` (working-tree, fail-closed) before trivy.

### Regression check
- `pytest tests/security/test_auth_routes.py tests/test_local_ollama_only_policy.py` → **26 passed, 1 skipped** (after fixture pragma edit).

**Commands run**
```
wasm-pack build --target web --out-dir ../public/wasm           # reproducible sha
git add client/public/wasm/{.gitignore,lawapp_wasm_bg.wasm,...} # now tracked
docker run python:3.11-slim 'pip install -e . && pip-audit'      # 6 toolchain CVEs
docker run python:3.11-slim 'pip install -U pip setuptools wheel && pip install -e . && pip-audit'  # No known vulnerabilities, RC=0
docker compose --profile ingestion run --rm ingestion pytest ... # 26 passed,1 skipped
```

**Files changed:** `client/public/wasm/.gitignore` + tracked WASM artifacts, `.github/workflows/lawapp-ci.yml` (pip-audit toolchain upgrade + secret-scan step), `Dockerfile.ingestion` (dspy-ai removed).

**G3 verdict:** ✅ both WASM and pip-audit root causes fixed and proven in CI-equivalent environments; secret-scan gate added. (Final confirmation = a green CI run after push.)

---

## G1  -  brain 503  -  🟡 ROOT-CAUSED + SOURCE-HARDENED; cluster fix is OWNER/CI (redeploy)

**Re-diagnosis supersedes the earlier "password mismatch" theory.** Command-proven this phase:

| Evidence | Result |
|---|---|
| brain pods | CrashLoopBackOff; `/health` → `{"status":"error","db":"disconnected"}` HTTP 503 |
| brain liveness probe | was `/health:8000` (DB-gated) → 503 kills container → crashloop |
| brain DB config | `POSTGRES_HOST=lawapp-postgres.lawapp-api.svc...`, DB/USER/PORT correct; **no `DATABASE_URL` override** |
| brain secret | `lawapp-ai-secrets` (sha 38bb32)  -  **same secret rules-engine uses** |
| **rules-engine** (same ns, same `lawapp-ai-secrets`, same host) | `/ready` (real DB check) = **HTTP 200** → DB auth+network from lawapp-ai WORKS |
| NetworkPolicies in lawapp-ai | **none** (not blocking) |
| **current HEAD source** backend (`docker compose`) | `/health` = `{"db":"connected"}` **HTTP 200** |
| deployed brain image | `ghcr.io/serverax/lawapp/backend@sha256:4c88929d…`, pullPolicy=Always; rollout restart re-pulled same digest → **still 503** |

**Conclusion (by elimination):** credentials, DB network, DNS, and config are all correct (rules-engine proves it; current source connects locally). The **deployed monolith image `4c88929d` is stale/defective for DB connectivity**. The fix is to **rebuild + redeploy the monolith backend image from HEAD**  -  a production deployment.

**Source-side fixes made (committable, non-destructive):**
- Added `GET /livez` to `backend/api/main.py`  -  dependency-free liveness (proven route registers).
- Repointed brain **liveness** probe `/health → /livez` in `infra/k8s/lawapp-brain-deployment.yaml` + `lawapp-ai-brain.yaml` (readiness stays `/health`). This stops DB-outage crash-loops; pod goes NotReady instead.

**OWNER / CI ACTION REQUIRED to close G1 (production deployment  -  not done autonomously):**
1. Rebuild + push the monolith image from HEAD, e.g. trigger the deploy pipeline:
   `gh workflow run lawapp-deploy-talos.yml --ref recovery/lawapp-autonomous-stabilisation`
   (or after merge to the deploy branch), then verify rollout.
2. Confirm: `kubectl -n lawapp-ai rollout status deploy/lawapp-brain`, brain `/health` → `db:connected` 200, brain `/livez` 200, pod 1/1 Ready, 8/8 in-cluster smoke.

**G1 verdict:** root-caused with command proof + source hardened; brain still 503 in cluster pending an owner/CI redeploy of the monolith image. **NOT closed.**

---

## G10  -  legal-data provenance chain  -  🟡 RUNTIME CHAIN PROVEN; embedding stage + fresh fetch incomplete

Proven on the local DB (db service, identical schema/code to cluster):

| Stage | Status | Evidence |
|---|---|---|
| Legal source fetched + hashed | ✅ | `legislation` 186/186 rows have `source_url` + `content_hash`; sample = real `legislation.gov.uk/ukpga/1996/18/section/104/data.xml` (ERA 1996 s104), hash `b4a72458…`, jurisdiction EW, `last_verified_at` set |
| Parsed legal rows | ✅ | legislation=186, acas_guidance=37, rules=21 |
| corpus_chunks exist w/ provenance | ✅ | 8 rows; schema carries `source_url, source_row_id, authority_ref, chunk_hash, effective_from/to` |
| Embeddings populated | ❌ | `corpus_chunks.with_embedding = 0`  -  vector search over corpus_chunks is INACTIVE |
| Retrieval returns grounded data | ✅ | `retrieve("unfair dismissal…","unfair_dismissal","EW",2025-01-01)` → **authorities=6, insufficient_grounding=False** (via rules/lexical + legislation path) |
| CitationGuard real UUID passes | ✅ | `valid_corpus_uuids([real])` → real `17bc0dc1…` **accepted=True** |
| CitationGuard fake UUID fails | ✅ | fake `00000000-…` **rejected=True** (cannot cite a source that does not exist) |
| `raw_source_records` table | ⚠️ absent | provenance is held in `legislation.{source_url,content_hash}` instead of a dedicated raw table |

**Commands**
```
psql ... 'select count(*) filter(where source_url is not null) from legislation'   # 186/186
psql ... 'select count(*) filter(where embedding is not null) from corpus_chunks'  # 0
docker compose --profile ingestion run ingestion python scripts/ops/g10_guard.py
# -> real accepted=True, fake rejected=True; retrieve authorities=6 insufficient_grounding=False
```

**G10 verdict:** the runtime chain (legal row → corpus_chunk → retrieval → CitationGuard fail-closed) is **proven**, with real source provenance (URL+hash). **Incomplete:** (a) `corpus_chunks` embeddings = 0 → vector semantic search not active; (b) backlog 007a–007d fresh-fetch + dedicated `raw_source_records` not yet executed; (c) corpus_chunks coverage (8) is small vs legislation (186). **NOT fully closed**  -  autonomous remaining work (embedder run + 007a–d).

---

## Updated blocker status (this session)

| Blocker | Status | Remaining |
|---|---|---|
| G1 brain 503 | 🟡 root-caused + source-hardened | OWNER/CI: rebuild+redeploy monolith image from HEAD |
| G2 leaked PATs | 🟡 working-tree clean + scanner gate proven | OWNER: rotate PAT + history rewrite/force-push |
| G3 CI red (WASM+pip-audit) | ✅ fixed & proven in CI-equiv env | confirm on next CI run |
| G10 legal-data chain | 🟡 runtime chain proven | embedder run + 007a–d fresh fetch |

**OVERALL: 🔴 NOT READY  -  LAWAPP HARD BLOCKERS REMAIN** (G1 + G2 owner-gated; G10 embedding/fetch incomplete).

---

## Remaining owner-only actions (consolidated)
- G2: rotate PAT(s) in GitHub; history rewrite + force-push.
- (others TBD as phases execute)
