#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/yangyiqun/codex_work/AutoResearchClaw"
OUTPUT_ROOT="${AUTORESEARCHCLAW_OUTPUT_ROOT:-/Users/yangyiqun/Library/CloudStorage/坚果云-yqyangyangyq@163.com/project/Autoresearchclaw/codex}"
MAX_PARALLEL="${AUTORESEARCHCLAW_MAX_PARALLEL:-4}"
HITL_MODE="${AUTORESEARCHCLAW_HITL_MODE:-co-pilot}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 topics.txt [additional researchclaw run args...]" >&2
  echo "Each non-empty, non-comment line in topics.txt is one topic." >&2
  exit 2
fi

TOPICS_FILE="$1"
shift

if [[ ! -f "$TOPICS_FILE" ]]; then
  echo "Topics file not found: $TOPICS_FILE" >&2
  exit 2
fi

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

mkdir -p "$OUTPUT_ROOT"

timestamp="$(date +%Y%m%d-%H%M%S)"
idx=0

while IFS= read -r topic || [[ -n "$topic" ]]; do
  [[ -z "${topic// }" ]] && continue
  [[ "$topic" =~ ^[[:space:]]*# ]] && continue

  idx=$((idx + 1))
  slug="$("$PROJECT_DIR/.venv/bin/python" - "$topic" <<'PY'
import re
import sys

topic = sys.argv[1].strip()
slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", topic).strip("-")
print(slug[:48] or "topic")
PY
)"
  run_dir="$OUTPUT_ROOT/${timestamp}_${idx}_${slug}"
  mkdir -p "$run_dir"

  session_name="researchclaw-codex-${timestamp}-${idx}"
  run_config="$run_dir/config.codex.yaml"

  "$PROJECT_DIR/.venv/bin/python" - "$PROJECT_DIR/config.codex.yaml" "$run_config" "$session_name" <<'PY'
import sys
from pathlib import Path

import yaml

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
session_name = sys.argv[3]

config = yaml.safe_load(src.read_text(encoding="utf-8"))
config.setdefault("llm", {}).setdefault("acp", {})["session_name"] = session_name
dst.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
PY

  log_file="$run_dir/run.log"
  echo "[$idx] Starting: $topic"
  echo "    output: $run_dir"
  echo "    session: $session_name"
  echo "    mode: $HITL_MODE"

  (
    export RESEARCHCLAW_HITL_FILE_WAIT=1
    researchclaw run \
      --config "$run_config" \
      --output "$run_dir" \
      --topic "$topic" \
      --mode "$HITL_MODE" \
      "$@"
  ) >"$log_file" 2>&1 &

  while [[ "$(jobs -rp | wc -l | tr -d ' ')" -ge "$MAX_PARALLEL" ]]; do
    sleep 5
  done
done < "$TOPICS_FILE"

wait
echo "All ResearchClaw runs finished."
