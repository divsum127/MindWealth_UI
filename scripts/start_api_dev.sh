#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export API_HOST=127.0.0.1
export API_PORT=8507
export UVICORN_RELOAD=1
exec "${SCRIPT_DIR}/start_api.sh"
