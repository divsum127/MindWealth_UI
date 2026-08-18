#!/usr/bin/env bash
# Parallel Test 15 SBI scan (4 shards) then merge + archive.
set -euo pipefail
MW="/home/ubuntu/MindWealth"
UI="/home/ubuntu/uiv2/git/MindWealth_UI"
PY="${MW}/.venv/bin/python"
SCRIPT="${UI}/scripts/mindwealth_adapters/sbi_breadth.py"
LOGDIR="/tmp/sbi_shards"
mkdir -p "${LOGDIR}"

pkill -f "sbi_breadth.py --start" 2>/dev/null || true
sleep 2
rm -f /tmp/sbi_full_out.json /tmp/sbi_short_dates.json

run_shard() {
  local id="$1" start="$2" end="$3"
  local cache="/tmp/sbi_shard_${id}.json"
  local log="${LOGDIR}/shard_${id}.log"
  echo "[shard ${id}] ${start} -> ${end:-today}"
  cd "${MW}"
  if [[ -n "${end}" ]]; then
    "${PY}" "${SCRIPT}" --start "${start}" --end "${end}" --freq BMS --dates-cache "${cache}" \
      > "${LOGDIR}/shard_${id}_out.json" 2> "${log}"
  else
    "${PY}" "${SCRIPT}" --start "${start}" --freq BMS --dates-cache "${cache}" \
      > "${LOGDIR}/shard_${id}_out.json" 2> "${log}"
  fi
}

run_shard 1 "2015-01-01" "2017-12-31" &
run_shard 2 "2018-01-01" "2020-12-31" &
run_shard 3 "2021-01-01" "2023-12-31" &
run_shard 4 "2024-01-01" "" &
wait

"${PY}" - <<'PY'
import json
from pathlib import Path

dates: list[str] = []
for i in range(1, 5):
    p = Path(f"/tmp/sbi_shard_{i}.json")
    if not p.is_file():
        continue
    data = json.loads(p.read_text())
    dates.extend(data.get("short_dates", []))
dates = sorted(set(dates))
Path("/tmp/sbi_short_dates.json").write_text(
    json.dumps({"short_dates": dates, "last_done": None, "scan_complete": True})
)
print(f"merged {len(dates)} short dates from shards")
PY

cd "${MW}"
"${PY}" "${SCRIPT}" --start 2015-01-01 --freq BMS --dates-cache /tmp/sbi_short_dates.json \
  > /tmp/sbi_full_out.json 2> "${LOGDIR}/metrics.log"

cd "${UI}"
"${UI}/.venv/bin/python" -c "
from src.sentiment_superindex.analysis.sbi_short_validation import run_and_report
import json
print(json.dumps(run_and_report('2015-01-01'), indent=2))
"
