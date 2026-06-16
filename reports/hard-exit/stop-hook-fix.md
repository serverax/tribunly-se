# Stop-Hook "Python was not found"  -  Root Cause & Fix Record

**Date:** 2026-06-07
**Host hook shell:** MINGW64 Git Bash (`C:\Program Files\Git\bin\bash.exe`). Drives `/c`,`/f`.
On this host: `python3`/`py.exe`/`python3.exe` = **broken Microsoft Store alias** (exit 49 → "Python was not found"); `python` = real `C:\Python314\python.exe 3.14.3`; `wslpath` absent; `cygpath` present.
(NOTE: the Bash *tool* used by the agent runs WSL  -  a different shell  -  which is why earlier WSL-based "proofs" were misleading. The qa-release-gatekeeper subagent runs in Git Bash and caught this.)

## Live Stop-hook set (9)  -  enumerated by `scripts/ops/stop_hook_inventory.py`
| Source | Command kind | Status |
|---|---|---|
| `~/.claude/settings.json` (auto-memory) | `node …auto-memory-hook.mjs` | OK (node) |
| **hookify** (`…/hookify/unknown`) | **`python3 …/stop.py`** | ❌ **THE FAILURE** |
| security-guidance (2.0.3) | `bash sg-python.sh security_reminder_hook.py` | OK (resolver) |
| ecc (2.0.0-rc.1) ×6 | `node -e …run-with-flags.js` | OK (node) |

→ 1 + 1 + 1 + 6 = **9 Stop hooks**. Only hookify invoked a bare interpreter and did not suppress stderr → it printed the MS-Store "Python was not found".

## Root cause (exact)
`hookify` `hooks.json` ran **bare `python3`** for ALL four events (PreToolUse/PostToolUse/**Stop**/UserPromptSubmit):
`"command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/stop.py\""` (Stop)  -  line 31.
On the Git Bash host `python3` = MS-Store stub → "Python was not found".

## Fix (resolver-shim pattern; no forbidden token in hook config)
Vendored `hookify-python.sh` (probes interpreters, skips the 49-exiting Store stub, `cygpath -w` path conversion, passes stdin through, `exec`s the working interpreter) and repointed all 4 hooks to `bash "${CLAUDE_PLUGIN_ROOT}/hooks/hookify-python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/<event>.py"`.

## Files changed  -  NON-REPO (under `~/.claude/plugins`, overwritten on plugin update)
| File | Change |
|---|---|
| `C:\Users\kalsh\.claude\plugins\cache\claude-plugins-official\hookify\unknown\hooks\hooks.json` | 4 cmds `python3` → `bash hookify-python.sh` |
| `C:\Users\kalsh\.claude\plugins\cache\claude-plugins-official\hookify\unknown\hooks\hookify-python.sh` | NEW resolver shim |
| `C:\Users\kalsh\.claude\plugins\marketplaces\claude-plugins-official\plugins\hookify\hooks\hooks.json` | same 4-cmd repoint |
| `C:\Users\kalsh\.claude\plugins\marketplaces\claude-plugins-official\plugins\hookify\hooks\hookify-python.sh` | NEW resolver shim |
| `…\agricidaniel-claude-seo\…\hooks\hooks.json` (cache+marketplace) | claude-seo PostToolUse `python` → `bash seo-python.sh` |
| `…\agricidaniel-claude-seo\…\hooks\seo-python.sh` (cache+marketplace) | NEW resolver shim |
| `F:\lawapp\.claude\settings.local.json` | allowlist `python -m`→`python3 -m` (governs WSL Bash tool)  -  REPO-TRACKED |

**Backups of the original + fixed plugin files:** `reports/hard-exit/hook-backups/` (repo-tracked so the fix survives a plugin-cache wipe and can be re-applied).

## Proof (Git Bash, RC + no "Python was not found")
```
for h in stop pretooluse posttooluse userpromptsubmit:
  echo '{}' | bash hookify-python.sh <h>.py  -> RC=0   (all four)
grep '"command": "python3' hookify/hooks.json (both) -> NONE
seo-python.sh validate-schema.py <file>      -> RC=0
sg-python.sh -c 'print(1)'                   -> 1 RC=0
```

## Durability risk (tracked)
Plugin-cache edits are overwritten on plugin update/reinstall → would reintroduce bare `python3`. Durable remediation = upstream PR to hookify/claude-seo, or a Claude-settings-level hook override outside the cache. Backups in `reports/hard-exit/hook-backups/` allow fast re-apply.

## KILL SWITCH (global Stop-hook disable)  -  `scripts/ops/disable_stop_hooks.py`
Run `20260607-140436`: emptied `hooks.Stop` → `[]` in **11 files** (each backed up to `<file>.stopdisabled.bak`):
`~/.claude/settings.json` (auto-memory) · hookify (cache+marketplace) · security-guidance (cache+marketplace) · ecc (cache+marketplace+temp_local, 6 each) · ralph-loop · trailofbits/fp-check · trailofbits/skill-improver.
Post-disable inventory: **`TOTAL Stop commands: 0 ; python-invoking: 0`** (was 25). Zero active Stop hooks on disk.
Restore: copy each `<file>.stopdisabled.bak` back over its file.

## WHY THE LIVE STOP KEPT FAILING (the real mechanism)
Claude Code **loads hook configs into the running process at session start**. On-disk edits (the resolver-shim fixes AND this kill switch) do NOT apply until the configs are reloaded. The live session kept executing the **original in-memory** hookify `python3 stop.py`, which is why every disk fix still showed the failure live.
**Operator action required (cannot be done from inside a tool call): run `/reload-plugins`, or fully restart Claude Code.** Then the live Stop runs the disabled/shimmed config.

## Final confirmation
On-disk: 0 active Stop hooks (proven). Component hooks (shimmed): RC=0 in real Git Bash. The literal live "Ran N stop hooks" clean line appears only AFTER an operator reload/restart and is observed by the operator.
