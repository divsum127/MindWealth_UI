#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
HOST="${API_HOST:-0.0.0.0}"
PORT="${API_PORT:-8000}"
# Parallel chatbot background jobs (default 2)
export CHATBOT_JOB_WORKERS="${CHATBOT_JOB_WORKERS:-2}"
exec uvicorn api.main:app --host "$HOST" --port "$PORT" --reload
