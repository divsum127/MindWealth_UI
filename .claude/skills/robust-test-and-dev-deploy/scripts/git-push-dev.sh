#!/usr/bin/env bash
# Push dev branches using divsum127 PAT. Commits must use git-commit-dev.sh (divsum127 author).
set -euo pipefail

PAT_FILE="${GITHUB_PAT_FILE:-$HOME/.cursor/github_pat}"

# Repos divsum127 may push to (owner/repo). Add new entries only with explicit user approval.
ALLOWED_SLUGS=(
  "divsum127/MindWealth_UI"
  "divsum127/mindwealth-api-docs"
  "D-ParthChauhan/MindwealthUI_Vue"
)

if [[ ! -f "$PAT_FILE" ]]; then
  echo "FAIL: GitHub PAT not found at $PAT_FILE" >&2
  echo "Create it with: printf '%s\\n' 'ghp_...' > $PAT_FILE && chmod 600 $PAT_FILE" >&2
  exit 1
fi

GITHUB_TOKEN="$(tr -d '[:space:]' < "$PAT_FILE")"
if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "FAIL: $PAT_FILE is empty" >&2
  exit 1
fi

REPO_PATH="${1:-/home/ubuntu/uiv2/git/MindWealth_UI}"
BRANCH="${2:-chatbot-dev}"

cd "$REPO_PATH"
CURRENT="$(git branch --show-current)"
if [[ "$CURRENT" != "$BRANCH" ]]; then
  echo "FAIL: expected branch $BRANCH, on $CURRENT" >&2
  exit 1
fi

if [[ -n "${GITHUB_PUSH_SLUG:-}" ]]; then
  REPO_SLUG="$GITHUB_PUSH_SLUG"
else
  REMOTE_URL="$(git remote get-url origin)"
  REPO_SLUG="$(printf '%s' "$REMOTE_URL" \
    | sed -E 's#^https://([^@]+@)?github.com/##; s#^git@github.com:##; s#\.git$##')"
fi

# Never push to ahiliitb / upstream mirrors
if [[ "$REPO_SLUG" == ahiliitb/* ]]; then
  echo "FAIL: refuse to push to ahiliitb remote ($REPO_SLUG)" >&2
  exit 1
fi

slug_allowed=false
for allowed in "${ALLOWED_SLUGS[@]}"; do
  if [[ "$REPO_SLUG" == "$allowed" ]]; then
    slug_allowed=true
    break
  fi
done

if [[ "$slug_allowed" != true ]]; then
  echo "FAIL: refuse to push — '$REPO_SLUG' is not in the allowlist" >&2
  echo "Allowed: ${ALLOWED_SLUGS[*]}" >&2
  exit 1
fi

AUTH_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO_SLUG}.git"

echo "Pushing $BRANCH to $REPO_SLUG (auth: divsum127 PAT)..."
git push "$AUTH_URL" "HEAD:${BRANCH}"
