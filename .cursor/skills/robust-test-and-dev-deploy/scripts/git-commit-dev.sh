#!/usr/bin/env bash
# Commit with divsum127 identity only — never use Cursor/default git user.
# Does NOT modify repo or global git config (env vars only).
set -euo pipefail

export GIT_AUTHOR_NAME="divsum127"
export GIT_AUTHOR_EMAIL="117962699+divsum127@users.noreply.github.com"
export GIT_COMMITTER_NAME="${GIT_AUTHOR_NAME}"
export GIT_COMMITTER_EMAIL="${GIT_AUTHOR_EMAIL}"

REPO_PATH="${1:-}"
if [[ -z "$REPO_PATH" ]]; then
  echo "Usage: git-commit-dev.sh <repo_path> <git-commit-args...>" >&2
  echo "Example: git-commit-dev.sh /home/ubuntu/uiv2/git/MindWealth_UI -m \"fix: foo\"" >&2
  exit 1
fi
shift

cd "$REPO_PATH"
git commit "$@"

echo "Author: $(git log -1 --format='%an <%ae>')"
