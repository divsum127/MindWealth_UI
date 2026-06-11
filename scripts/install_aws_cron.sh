#!/usr/bin/env bash
# Install Runic + SSI cron on AWS host (51.20.53.218). Run from repo root as deploy user.
#
# IMPORTANT: Merges with the existing user crontab — never wipes unrelated jobs
# (e.g. MindWealth daily email at emailscript.sh).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${REPO_ROOT}/.venv/bin/python"
export TZ=America/New_York

MACRO_MARKERS='run_ssi_daily\.py|run_macro_friday_pull\.py|run_macro_nightly\.py|run_emission_vectors_daily\.py'
EMAIL_MARKER='emailscript\.sh'

EXISTING="$(crontab -l 2>/dev/null || true)"
PRESERVED="$(printf '%s\n' "$EXISTING" | grep -v -E "^SHELL=|^PATH=|${MACRO_MARKERS}" | sed '/^[[:space:]]*$/d' || true)"

CRON_FILE=$(mktemp)
{
  echo "SHELL=/bin/bash"
  echo "PATH=/usr/local/bin:/usr/bin:/bin"
  if [ -n "$PRESERVED" ]; then
    printf '%s\n' "$PRESERVED"
  fi
  echo "0 8 * * 1-5 cd ${REPO_ROOT} && ${PY} scripts/run_ssi_daily.py >> macro_intelligence/logs/ssi_daily.log 2>&1"
  echo "30 17 * * 5 cd ${REPO_ROOT} && ${PY} scripts/run_macro_friday_pull.py >> macro_intelligence/logs/friday_pull.log 2>&1"
  echo "0 18 * * 1-5 cd ${REPO_ROOT} && ${PY} scripts/run_macro_nightly.py >> macro_intelligence/logs/nightly.log 2>&1"
  echo "15 18 * * 1-5 cd ${REPO_ROOT} && ${PY} scripts/run_emission_vectors_daily.py >> macro_intelligence/logs/emission_vectors_daily.log 2>&1"
} > "$CRON_FILE"
mkdir -p "${REPO_ROOT}/macro_intelligence/logs"
crontab "$CRON_FILE"
rm -f "$CRON_FILE"

echo "Cron installed (merged with existing entries). Verify: crontab -l"
if ! crontab -l 2>/dev/null | grep -qE "$EMAIL_MARKER"; then
  echo "WARNING: emailscript.sh cron not found — daily MindWealth email reports will NOT run."
  echo "         Add: 0 22 * * * cd /home/ubuntu/MindWealth && /usr/bin/bash /home/ubuntu/MindWealth/emailscript.sh >> /home/ubuntu/MindWealth/emailscript_cron.log 2>&1"
  exit 1
fi
