#!/usr/bin/env bash
# AI Analyst panel smoke test.
#
# Asserts the contract the Nuxt panel depends on. Run against dev (:8507) before
# any merge to chatbot-prod, and against prod (:8506) after deploy.
#
#   scripts/smoke_analyst.sh [BASE_URL] [API_KEY]
set -uo pipefail

BASE="${1:-http://127.0.0.1:8507}"
KEY="${2:-${MINDWEALTH_API_KEY:-}}"
PREFIX="$BASE/api/v1"
PASS=0
FAIL=0

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

hdr=(-H "Accept: application/json")
[ -n "$KEY" ] && hdr+=(-H "X-API-Key: $KEY")

fetch() {  # fetch <name> <path>
  curl -s -m 120 "${hdr[@]}" "$PREFIX$2" -o "$TMP/$1.json"
}

# Payloads run to hundreds of KB, which is past the environment-size limit —
# they are passed to python by path, never by env var.
assert() {  # assert <name> <file> <python-expr over `d`>
  local out
  out=$(python3 -c "
import json,sys,re
d = json.load(open('$TMP/$2.json'))
print(bool($3))
" 2>&1) || out="ERR: $out"
  if [ "$out" = "True" ]; then
    echo "  PASS  $1"; PASS=$((PASS + 1))
  else
    echo "  FAIL  $1  ($out)"; FAIL=$((FAIL + 1))
  fi
}

echo "AI Analyst smoke test -> $BASE"

fetch alerts "/analytics/analyst/alerts?include_system=false"
fetch brief "/analytics/analyst/brief"
fetch context "/analytics/analyst/context?include_system=false"
fetch page "/portfolio/alerts?book_id=model"

echo "== /analytics/analyst/alerts =="
assert "responds with panel_alerts" alerts \
  "'panel_alerts' in d"

# The headline defect: MTM percentages rendered as forward win rates.
assert "no degradation alert carries a negative fwd_wr" alerts \
  "not any(a['type']=='degradation' and (a.get('signal') or {}).get('fwd_wr',0)<0 for a in d['panel_alerts'])"

assert "position risk never fills the signal payload" alerts \
  "all(a.get('signal') is None for a in d['panel_alerts'] if a['type']=='position_risk')"

assert "position risk always fills the position payload" alerts \
  "all(a.get('position') for a in d['panel_alerts'] if a['type']=='position_risk')"

assert "every drift alert has a real 4-point trend" alerts \
  "all(len(a.get('fwd_trend') or [])==4 for a in d['panel_alerts'] if a['type']=='degradation')"

assert "every alert carries a channel" alerts \
  "all(a.get('channel') in ('signals','macro','system') for a in d['panel_alerts'])"

assert "alert ids are unique" alerts \
  "len({a['id'] for a in d['panel_alerts']})==len(d['panel_alerts'])"

assert "next scan times are populated" alerts \
  "bool(d['meta'].get('next_signal_check')) and bool(d['meta'].get('next_macro_scan'))"

assert "signals badge separates drift from positions" alerts \
  "d['meta']['tabs']['signals'].get('drift_count') is not None and d['meta']['tabs']['signals'].get('position_count') is not None"

echo "== /analytics/analyst/brief =="
assert "snippet does not truncate mid-number" brief \
  "re.search(r'\d\.\$', d['snippet']) is None"

echo "== /analytics/analyst/context =="
assert "bundles alerts, regime and sentiment" context \
  "'regime' in d and 'sentiment' in d and 'panel_alerts' in d"

echo "== /portfolio/alerts (agent slide-in, 15 Jul spec D4) =="
assert "every page alert names a target_page" page \
  "all(a.get('target_page') for a in d.get('alerts',[]))"

echo
echo "passed: $PASS   failed: $FAIL"
[ "$FAIL" -eq 0 ]
