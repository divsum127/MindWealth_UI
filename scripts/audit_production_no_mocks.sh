#!/usr/bin/env bash
# Wrapper — implementation in audit_production_no_mocks.py (avoids shell/rg env issues).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/.venv/bin/python" "$ROOT/scripts/audit_production_no_mocks.py"
