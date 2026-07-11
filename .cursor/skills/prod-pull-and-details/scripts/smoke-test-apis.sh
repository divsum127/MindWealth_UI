#!/usr/bin/env bash
# Smoke tests after dev push or prod pull. Exit non-zero on failure.
set -euo pipefail

PROD_URL="${PROD_URL:-http://127.0.0.1:8506}"
DEV_URL="${DEV_URL:-http://127.0.0.1:8507}"
PROD_STORE="/home/ubuntu/uiv2/prod/MindWealth_UI/conviction_store"
GIT_STORE="/home/ubuntu/uiv2/git/MindWealth_UI/conviction_store"
FAIL=0

pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*" >&2; FAIL=1; }

check_health() {
  local label="$1" url="$2" expected_store="$3"
  local body
  if ! body="$(curl -sf "${url}/api/v1/health")"; then
    fail "${label} health unreachable at ${url}/api/v1/health"
    return
  fi
  local status version store writable
  status="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status',''))" <<<"$body")"
  version="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('version',''))" <<<"$body")"
  store="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('conviction_store',''))" <<<"$body")"
  writable="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('conviction_store_writable',''))" <<<"$body")"

  [[ "$status" == "ok" ]] && pass "${label} status=ok" || fail "${label} status=${status}"
  [[ -n "$version" ]] && pass "${label} version=${version}" || fail "${label} missing version"
  [[ "$store" == "$expected_store" ]] && pass "${label} conviction_store isolated (${store})" \
    || fail "${label} conviction_store mismatch: got '${store}', want '${expected_store}'"
  [[ "$writable" == "True" || "$writable" == "true" ]] && pass "${label} conviction_store_writable" \
    || fail "${label} conviction_store not writable"
}

check_systemd() {
  local unit="$1"
  if systemctl is-active --quiet "$unit"; then
    pass "systemd ${unit} active"
  else
    fail "systemd ${unit} not active"
  fi
}

echo "=== MindWealth API smoke tests ==="
check_systemd mindwealth-api.service
check_health "prod (8506)" "$PROD_URL" "$PROD_STORE"

if curl -sf "${DEV_URL}/api/v1/health" >/dev/null 2>&1; then
  check_systemd mindwealth-api-dev.service
  check_health "dev (8507)" "$DEV_URL" "$GIT_STORE"
else
  echo "SKIP: dev API not running on ${DEV_URL} (start mindwealth-api-dev.service to test)"
fi

if curl -sf "${PROD_URL}/api/v1/signals/counts" >/dev/null 2>&1; then
  pass "prod /api/v1/signals/counts reachable"
else
  fail "prod /api/v1/signals/counts unreachable"
fi

echo "=== done ==="
exit "$FAIL"
