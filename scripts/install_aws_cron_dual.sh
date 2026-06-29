#!/usr/bin/env bash
# Install Runic + SSI cron for BOTH git (dev) and prod clones on AWS host.
# Merges with existing crontab — preserves emailscript.sh and unrelated jobs.
set -euo pipefail

GIT_ROOT="${GIT_ROOT:-/home/ubuntu/uiv2/git/MindWealth_UI}"
PROD_ROOT="${PROD_ROOT:-/home/ubuntu/uiv2/prod/MindWealth_UI}"
GIT_PY="${GIT_ROOT}/.venv/bin/python"
PROD_PY="${PROD_ROOT}/.venv/bin/python"
export TZ=America/New_York

MACRO_MARKERS='run_ssi_daily\.py|run_macro_friday_pull\.py|run_macro_nightly\.py|run_emission_vectors_daily\.py'
EMAIL_MARKER='emailscript\.sh'

for ROOT in "$GIT_ROOT" "$PROD_ROOT"; do
  if [[ ! -x "${ROOT}/.venv/bin/python" ]]; then
    echo "Missing venv at ${ROOT}/.venv" >&2
    exit 1
  fi
  mkdir -p "${ROOT}/macro_intelligence/logs"
done

EXISTING="$(crontab -l 2>/dev/null || true)"
PRESERVED="$(printf '%s\n' "$EXISTING" | grep -v -E "^SHELL=|^PATH=|${MACRO_MARKERS}" | sed '/^[[:space:]]*$/d' || true)"

CRON_FILE=$(mktemp)
{
  echo "SHELL=/bin/bash"
  echo "PATH=/usr/local/bin:/usr/bin:/bin"
  if [ -n "$PRESERVED" ]; then
    printf '%s\n' "$PRESERVED"
  fi
  for ROOT_PY in "${GIT_ROOT}:${GIT_PY}" "${PROD_ROOT}:${PROD_PY}"; do
    ROOT="${ROOT_PY%%:*}"
    PY="${ROOT_PY##*:}"
    echo "0 8 * * 1-5 cd ${ROOT} && ${PY} scripts/run_ssi_daily.py >> macro_intelligence/logs/ssi_daily.log 2>&1"
    echo "30 17 * * 5 cd ${ROOT} && ${PY} scripts/run_macro_friday_pull.py >> macro_intelligence/logs/friday_pull.log 2>&1"
    echo "0 18 * * 1-5 cd ${ROOT} && ${PY} scripts/run_macro_nightly.py >> macro_intelligence/logs/nightly.log 2>&1"
    echo "15 18 * * 1-5 cd ${ROOT} && ${PY} scripts/run_emission_vectors_daily.py >> macro_intelligence/logs/emission_vectors_daily.log 2>&1"
  done
} > "$CRON_FILE"

crontab "$CRON_FILE"
rm -f "$CRON_FILE"

echo "Dual macro cron installed (git + prod). Verify: crontab -l"
if ! crontab -l 2>/dev/null | grep -qE "$EMAIL_MARKER"; then
  echo "WARNING: emailscript.sh cron not found — daily MindWealth email reports will NOT run."
  echo "         Add: 0 22 * * * cd /home/ubuntu/MindWealth && /usr/bin/bash /home/ubuntu/MindWealth/emailscript.sh >> /home/ubuntu/MindWealth/emailscript_cron.log 2>&1"
  exit 1
fi
