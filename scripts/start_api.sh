#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
HOST="${API_HOST:-0.0.0.0}"
PORT="${API_PORT:-8506}"
# Parallel chatbot background jobs (default 2)
export CHATBOT_JOB_WORKERS="${CHATBOT_JOB_WORKERS:-2}"
RELOAD_ARGS=()
if [[ "${UVICORN_RELOAD:-0}" == "1" ]]; then
  RELOAD_ARGS+=(--reload)
fi
exec uvicorn api.main:app --host "$HOST" --port "$PORT" "${RELOAD_ARGS[@]}"
