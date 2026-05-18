#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/yangyiqun/codex_work/AutoResearchClaw"
OUTPUT_DIR="${AUTORESEARCHCLAW_OUTPUT_DIR:-/Users/yangyiqun/Library/CloudStorage/坚果云-yqyangyangyq@163.com/project/Autoresearchclaw/codex}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"research topic\" [additional researchclaw run args...]" >&2
  exit 2
fi

TOPIC="$1"
shift

cd "$PROJECT_DIR"
source "$PROJECT_DIR/.venv/bin/activate"

if [[ -f "$PROJECT_DIR/.env.local" ]]; then
  set -a
  source "$PROJECT_DIR/.env.local"
  set +a
fi

CERT_FILE="$("$PROJECT_DIR/.venv/bin/python" -m certifi)"
export SSL_CERT_FILE="$CERT_FILE"
export REQUESTS_CA_BUNDLE="$CERT_FILE"
export GIT_SSL_CAINFO="$CERT_FILE"

EXTRA_ARGS=()
if [[ "${AUTORESEARCHCLAW_STRICT_QUALITY:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--no-graceful-degradation)
fi

researchclaw run \
  --config "$PROJECT_DIR/config.codex.yaml" \
  --output "$OUTPUT_DIR" \
  --topic "$TOPIC" \
  --mode co-pilot \
  "${EXTRA_ARGS[@]}" \
  "$@"
