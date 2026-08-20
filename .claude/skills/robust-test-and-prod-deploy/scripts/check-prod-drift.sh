#!/usr/bin/env bash
# Read-only pre-flight check before a chatbot-dev -> chatbot-prod merge.
# Never writes, pushes, or restarts anything. Safe to run any time.
set -euo pipefail

DEV_REPO="/home/ubuntu/uiv2/git/MindWealth_UI"
PROD_CLONE="/home/ubuntu/uiv2/prod/MindWealth_UI"

echo "=== fetch ==="
git -C "$DEV_REPO" fetch origin --quiet

echo
echo "=== 1. local chatbot-prod vs origin/chatbot-prod ==="
if ! git -C "$DEV_REPO" show-ref --verify --quiet refs/heads/chatbot-prod; then
  echo "local chatbot-prod branch does not exist in $DEV_REPO — nothing to compare"
else
  AHEAD_BEHIND="$(git -C "$DEV_REPO" rev-list --left-right --count chatbot-prod...origin/chatbot-prod)"
  LOCAL_AHEAD="$(echo "$AHEAD_BEHIND" | cut -f1)"
  LOCAL_BEHIND="$(echo "$AHEAD_BEHIND" | cut -f2)"
  echo "local chatbot-prod is ${LOCAL_AHEAD} ahead, ${LOCAL_BEHIND} behind origin/chatbot-prod"
  if [[ "$LOCAL_AHEAD" -gt 0 ]]; then
    echo "  >>> WARNING: local has unpushed commits. Use local chatbot-prod as the merge base, not origin."
    git -C "$DEV_REPO" log --oneline "origin/chatbot-prod..chatbot-prod"
  fi
fi

echo
echo "=== 2. chatbot-dev vs chatbot-prod (what would merge) ==="
BASE_REF="chatbot-prod"
git -C "$DEV_REPO" show-ref --verify --quiet refs/heads/chatbot-prod || BASE_REF="origin/chatbot-prod"
COMMIT_COUNT="$(git -C "$DEV_REPO" rev-list --count "${BASE_REF}..origin/chatbot-dev")"
FILE_COUNT="$(git -C "$DEV_REPO" diff --name-only "${BASE_REF}...origin/chatbot-dev" | wc -l)"
echo "base: ${BASE_REF}"
echo "${COMMIT_COUNT} commits / ${FILE_COUNT} files would merge"

echo
echo "=== 3. requirements.txt changed? ==="
REQ_DIFF="$(git -C "$DEV_REPO" diff --stat "${BASE_REF}...origin/chatbot-dev" -- requirements.txt)"
if [[ -n "$REQ_DIFF" ]]; then
  echo "YES — pip install will be needed on prod after merge:"
  echo "$REQ_DIFF"
else
  echo "no change"
fi

echo
echo "=== 4. prod clone working-tree status ==="
if [[ -d "$PROD_CLONE" ]]; then
  DIRTY="$(git -C "$PROD_CLONE" status --short)"
  if [[ -z "$DIRTY" ]]; then
    echo "clean"
  else
    echo "$DIRTY"
    echo
    echo "Expected: only cron-output data files (monitored_trades.json, macro_intelligence/data/ssi/*,"
    echo "aaii_sentiment.xls). Anything else dirty — stop and ask the user before stashing/pulling."
  fi
  echo
  echo "prod clone HEAD: $(git -C "$PROD_CLONE" log --oneline -1)"
else
  echo "SKIP — $PROD_CLONE not found on this host"
fi

echo
echo "=== 5. concurrent sessions on this host ==="
pgrep -af 'claude|cursor' 2>/dev/null | grep -v "$$" | grep -v check-prod-drift.sh || echo "none found"

echo
echo "=== done — this was read-only, nothing was changed ==="
