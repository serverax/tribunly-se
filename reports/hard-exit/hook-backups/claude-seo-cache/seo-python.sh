#!/usr/bin/env bash
# Resolver shim: find a working Python 3 and exec the hook with it.
# Host-agnostic — works in MINGW64/Git Bash, WSL, macOS, Linux.
# - Skips the Microsoft Store stub (it exits 49 on `-c`, so the probe fails).
# - Converts POSIX path args to native Windows form via cygpath when present
#   (Git Bash), so Windows python.org interpreters can open them.
# Invocation:  bash seo-python.sh <script.py> [args...]
set -e
export PYTHONUTF8=1

if command -v cygpath >/dev/null 2>&1; then
  conv=()
  for a in "$@"; do
    case "$a" in
      /*) conv+=("$(cygpath -w "$a")") ;;
      *)  conv+=("$a") ;;
    esac
  done
  set -- "${conv[@]}"
fi

probe() { "$@" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,6) else 1)' >/dev/null 2>&1; }

for cmd in "python3.13" "python3.12" "python3.11" "python3.10" "python3" "python" "py -3"; do
  # shellcheck disable=SC2086
  if probe $cmd; then
    # shellcheck disable=SC2086
    exec $cmd "$@"
  fi
done

echo "seo-python: no working Python 3 interpreter found (tried python3.x, python3, python, py -3)." >&2
exit 1
