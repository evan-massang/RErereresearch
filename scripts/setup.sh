#!/usr/bin/env bash
# Install everything the pipeline needs. Safe to re-run: skips what is present.
#
#   scripts/setup.sh                 # system packages + Python packages + empty data/ layout + DB
#   scripts/setup.sh --check         # only report what is missing (exit 1 if anything is)
#   RR_WHISPER_MODEL=small scripts/setup.sh   # also pre-download a Whisper model (needs huggingface.co)
#   RR_SKIP_APT=1 scripts/setup.sh   # skip apt (e.g. no root)
#
# Works on Debian/Ubuntu (Claude Code cloud containers). Elsewhere, install
# ffmpeg/jq/ripgrep with your package manager and set RR_SKIP_APT=1.
set -euo pipefail

cd "$(dirname "$0")/.."
REPO="$(pwd)"
PY="${PYTHON:-python3}"
APT_PKGS=(ffmpeg git curl jq ripgrep python3-pip)
CHECK_ONLY=0
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=1

log() { printf '[setup] %s\n' "$*" >&2; }

# ---- system packages --------------------------------------------------------
missing_apt=()
for p in "${APT_PKGS[@]}"; do
  dpkg -s "$p" >/dev/null 2>&1 || missing_apt+=("$p")
done

# ---- python packages --------------------------------------------------------
missing_py=$("$PY" - <<'EOF'
import importlib.util
mods = {"yt_dlp": "yt-dlp", "faster_whisper": "faster-whisper", "trafilatura": "trafilatura",
        "bs4": "beautifulsoup4", "lxml": "lxml", "httpx": "httpx", "pandas": "pandas",
        "pyarrow": "pyarrow", "duckdb": "duckdb", "pytest": "pytest"}
print(" ".join(pkg for mod, pkg in mods.items() if importlib.util.find_spec(mod) is None))
EOF
)

if [[ $CHECK_ONLY == 1 ]]; then
  log "missing apt: ${missing_apt[*]:-none}"
  log "missing python: ${missing_py:-none}"
  [[ ${#missing_apt[@]} -eq 0 && -z "$missing_py" ]]
  exit $?
fi

if [[ ${#missing_apt[@]} -gt 0 && -z "${RR_SKIP_APT:-}" ]]; then
  SUDO=""; [[ $(id -u) -ne 0 ]] && SUDO="sudo"
  log "apt installing: ${missing_apt[*]}"
  $SUDO apt-get update -qq
  DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq "${missing_apt[@]}" >/dev/null
else
  log "apt packages: ok"
fi

if [[ -n "$missing_py" ]]; then
  log "pip installing requirements (missing: $missing_py)"
  if ! "$PY" -m pip install -q -r requirements.txt 2>/tmp/rr-pip.err; then
    if grep -q externally-managed /tmp/rr-pip.err; then
      "$PY" -m pip install -q --break-system-packages -r requirements.txt
    else
      cat /tmp/rr-pip.err >&2; exit 1
    fi
  fi
else
  log "python packages: ok"
fi

# ---- archive + database -----------------------------------------------------
ROOT="${RR_ROOT:-$REPO}"
"$PY" -m pipeline init >/dev/null
log "project root ready at $ROOT"

# Restore committed Parquet snapshot into a fresh container's empty DB.
if ls "$ROOT"/data/parquet/*.parquet >/dev/null 2>&1; then
  rows=$("$PY" -m pipeline query "SELECT count(*) AS n FROM sources" | "$PY" -c 'import json,sys;print(json.load(sys.stdin)[0]["n"])')
  if [[ "$rows" == "0" ]]; then
    "$PY" -m pipeline import-parquet >/dev/null && log "restored database from $ROOT/data/parquet"
  fi
fi

# ---- optional: pre-download a Whisper model ---------------------------------
if [[ -n "${RR_WHISPER_MODEL:-}" ]]; then
  log "pre-downloading whisper model ${RR_WHISPER_MODEL} (needs huggingface.co)"
  "$PY" -c "from faster_whisper import WhisperModel; WhisperModel('${RR_WHISPER_MODEL}', device='cpu', compute_type='int8')" \
    || log "WARNING: whisper model download failed (network policy?) — ASR will retry on first use"
fi

log "done"
