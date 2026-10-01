#!/usr/bin/env bash
# SessionStart hook: provision a fresh Claude Code cloud container.
# Local sessions are left alone (run scripts/setup.sh yourself there).
set -euo pipefail

if [[ "${CLAUDE_CODE_REMOTE:-}" != "true" ]]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/..}"
scripts/setup.sh 2>&1 | tail -n 20 >&2
