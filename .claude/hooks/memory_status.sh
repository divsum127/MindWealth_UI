#!/usr/bin/env bash
# SessionStart hook — one line of memory-layer status.
#
# Deliberately read-only and non-fatal. It never runs a sync: a session should
# start instantly, and a sync that fetches mail has no business firing on every
# new chat. It only reports what the last sync recorded, so the number can be
# stale — that staleness is itself the signal to run /sync-memory.
#
# Always exits 0. A broken status line must never block a session from starting.

set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-/home/ubuntu/uiv2/git/MindWealth_UI}"
STATE="$ROOT/docs/memory/.sync_state.json"
QUEUE="$ROOT/docs/memory/PROD_QUEUE.md"

[ -f "$STATE" ] || exit 0

last_sync=$(python3 -c "
import json,sys
try:
    print(json.load(open('$STATE')).get('last_sync','')[:10])
except Exception:
    pass
" 2>/dev/null) || exit 0

[ -n "$last_sync" ] || exit 0

age_days=$(python3 -c "
from datetime import date
try:
    y,m,d = '$last_sync'.split('-')
    print((date.today() - date(int(y),int(m),int(d))).days)
except Exception:
    print(0)
" 2>/dev/null) || age_days=0

summary=""
if [ -f "$QUEUE" ]; then
    summary=$(grep -m1 '^\*\*[0-9]* pending\*\*' "$QUEUE" | sed 's/\*\*//g; s/ · /, /g')
fi

printf 'Memory layer: last synced %s (%sd ago).' "$last_sync" "$age_days"
[ -n "$summary" ] && printf ' Prod queue: %s.' "$summary"
printf ' Map: docs/memory/MAP.md'
if [ "$age_days" -ge 3 ] 2>/dev/null; then
    printf ' — stale, run /sync-memory'
fi
printf '\n'

exit 0
