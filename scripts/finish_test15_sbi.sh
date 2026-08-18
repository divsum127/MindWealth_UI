#!/usr/bin/env bash
# Wait for Test 15 SBI batch, archive JSON, print result.
set -euo pipefail
ROOT="/home/ubuntu/uiv2/git/MindWealth_UI"
OUT="/tmp/sbi_full_out.json"
CACHE="/tmp/sbi_short_dates.json"

echo "[finish_test15] waiting for ${OUT} ..."
while [[ ! -s "${OUT}" ]]; do
  if [[ -f "${CACHE}" ]] && grep -q '"scan_complete": true' "${CACHE}"; then
    echo "[finish_test15] scan complete in cache but no stdout yet; sleeping"
  fi
  sleep 120
done

cd "${ROOT}"
echo "[finish_test15] archiving ..."
"${ROOT}/.venv/bin/python" -c "
from src.sentiment_superindex.analysis.sbi_short_validation import run_and_report
import json
print(json.dumps(run_and_report('2015-01-01'), indent=2))
"
