#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/yangyiqun/codex_work/AutoResearchClaw"
OUTPUT_ROOT="${AUTORESEARCHCLAW_OUTPUT_ROOT:-/Users/yangyiqun/Library/CloudStorage/坚果云-yqyangyangyq@163.com/project/Autoresearchclaw/codex}"
MAX_PARALLEL="${AUTORESEARCHCLAW_MAX_PARALLEL:-2}"
HITL_MODE="${AUTORESEARCHCLAW_HITL_MODE:-full-auto}"

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 topics.txt batch_prefix [additional researchclaw run args...]" >&2
  echo "Example: $0 topics_central_obesity_t2d.txt 20260510-004308" >&2
  exit 2
fi

TOPICS_FILE="$1"
BATCH_PREFIX="$2"
shift 2

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

resume_ts="$(date +%Y%m%d-%H%M%S)"
idx=0

while IFS= read -r topic || [[ -n "$topic" ]]; do
  [[ -z "${topic// }" ]] && continue
  [[ "$topic" =~ ^[[:space:]]*# ]] && continue

  idx=$((idx + 1))
  matches=("$OUTPUT_ROOT/${BATCH_PREFIX}_${idx}_"*)
  run_dir=""
  for candidate in "${matches[@]}"; do
    if [[ -d "$candidate" ]]; then
      run_dir="$candidate"
      break
    fi
  done

  if [[ -z "$run_dir" ]]; then
    echo "Run directory not found for index $idx: $OUTPUT_ROOT/${BATCH_PREFIX}_${idx}_*" >&2
    exit 1
  fi

  run_config="$run_dir/config.codex.yaml"
  if [[ ! -f "$run_config" ]]; then
    echo "Run config not found: $run_config" >&2
    exit 1
  fi

  session_name="researchclaw-codex-${BATCH_PREFIX}-${idx}-resume-${resume_ts}"
  "$PROJECT_DIR/.venv/bin/python" - "$run_config" "$session_name" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
session_name = sys.argv[2]
config = yaml.safe_load(path.read_text(encoding="utf-8"))
config.setdefault("llm", {}).setdefault("acp", {})["session_name"] = session_name
path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
PY

  log_file="$run_dir/resume-${resume_ts}.log"
  echo "[$idx] Resuming: $topic"
  echo "    output: $run_dir"
  echo "    session: $session_name"
  echo "    mode: $HITL_MODE"
  echo "    log: $log_file"

  (
    export RESEARCHCLAW_HITL_FILE_WAIT=1
    researchclaw run \
      --config "$run_config" \
      --output "$run_dir" \
      --topic "$topic" \
      --mode "$HITL_MODE" \
      --resume \
      "$@"
  ) >"$log_file" 2>&1 &

  while [[ "$(jobs -rp | wc -l | tr -d ' ')" -ge "$MAX_PARALLEL" ]]; do
    sleep 5
  done
done < "$TOPICS_FILE"

wait
echo "All resumed ResearchClaw runs finished."
