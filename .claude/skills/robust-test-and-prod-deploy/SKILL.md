---
name: robust-test-and-prod-deploy
description: >-
  Prod release loop: merge chatbot-dev -> chatbot-prod (branch-drift check,
  isolated worktree, zero-tolerance on conflicts), pull onto the prod clone
  (stash/resolve cron-dirty data files by timestamp, never commit from prod),
  restart mindwealth-api.service, run smoke tests against prod, and log
  dev_to_prod_migration_todos + job status. Use when the user asks to merge
  dev to prod, release to prod, deploy chatbot-prod, or run
  robust-test-and-prod-deploy / prod release.
disable-model-invocation: true
---

# Robust test and prod deploy

Run this skill when `chatbot-dev` work is verified (ideally already through [robust-test-and-dev-deploy](../robust-test-and-dev-deploy/SKILL.md)) and the user wants it **on prod**. This is the highest-blast-radius skill in the repo — it writes to the shared `chatbot-prod` branch and restarts a live, publicly reachable service. **Loop at every step until green. Never silently paper over a conflict or a failed check — stop and ask.**

**Confirm before acting** unless the user's request already explicitly authorized a full prod release (e.g. "merge dev to prod", "deploy to prod now"). A vague "check on the merge status" or "what's pending for prod" is **not** authorization to push or restart — answer read-only and ask.

**Never** edit source files under `/home/ubuntu/uiv2/prod/` — prod clone is deploy/pull-only. See CLAUDE.md → "Production clone — do not edit".

**GitHub identity (mandatory):** all commits and pushes use **`divsum127`** only — same rules as [robust-test-and-dev-deploy](../robust-test-and-dev-deploy/SKILL.md) (never plain `git commit`/`git push`, never `ahiliitb/*`, never touch git config).

**Related skills:**
- Dev-side verification before this: [robust-test-and-dev-deploy](../robust-test-and-dev-deploy/SKILL.md)
- Path/branch/port architecture, manual pull/restart commands: [prod-pull-and-details](../prod-pull-and-details/SKILL.md)
- Detailed playbook + templates: [reference.md](reference.md)

---

## Architecture recap

```text
DEV (edit + commit)                    PROD (pull only — never commit)
uiv2/git/MindWealth_UI                 uiv2/prod/MindWealth_UI
branch: chatbot-dev                    branch: chatbot-prod
API :8507                              API :8506 (public, 0.0.0.0)
```

Public prod API: `http://51.20.53.218:8506/api/v1` (requires `X-API-Key`).

---

## Master checklist

Copy and track:

```
Robust test + prod deploy:
- [ ] 0. Confirm scope with user (unless already explicit) — merge only, or merge + deploy?
- [ ] 1. Pre-flight drift check (local chatbot-prod vs origin, dev vs prod diff, concurrent sessions)
- [ ] 2. Commit + push any outstanding chatbot-dev work first
- [ ] 3. Merge chatbot-dev -> chatbot-prod in an isolated worktree — zero conflicts required
- [ ] 4. Push chatbot-prod, sync local branch ref, remove worktree
- [ ] 5. Prod clone: stash dirty runtime data -> pull -> resolve stash-pop conflicts by timestamp
- [ ] 6. pip install if requirements.txt changed; restart mindwealth-api.service
- [ ] 7. Smoke tests (local + public authenticated health check)
- [ ] 8. Update dev_to_prod_migration_todos.md (mark closed range, list what's still open)
- [ ] 9. Update job status + details docs
```

---

## Step 0 — Confirm scope

Ask (if not already answered by the user's request):
- Merge to `chatbot-prod` and push to GitHub only, or also pull + restart the prod clone (full release)?
- Any known reason to hold (open Rohit-sir question, unverified `[PROD-ACTION]` runtime step from a migration-doc entry)?

If the user already said "merge to prod" / "deploy to prod" / "release this", scope is merge **and** deploy — proceed without re-asking.

---

## Step 1 — Pre-flight drift check

**Do this before touching anything.** Two failure modes only show up here, not in the migration doc:

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
bash .claude/skills/robust-test-and-prod-deploy/scripts/check-prod-drift.sh
```

This is read-only — fetches, then reports:
1. **Local `chatbot-prod` vs `origin/chatbot-prod`** — if local is ahead, someone pulled commits onto the prod clone or committed locally without pushing. Treat **local `chatbot-prod`** as the true merge base, not `origin`, or you will silently revert already-deployed commits the moment you push.
2. **`chatbot-dev` vs `chatbot-prod`** commit count and file count — the size of what you're about to merge.
3. **Prod clone (`/home/ubuntu/uiv2/prod/MindWealth_UI`) working-tree status** — cron-driven data files (`monitored_trades.json`, SSI CSVs, `aaii_sentiment.xls`) are dirty essentially always; expected. Anything else dirty (source files) is not expected — stop and ask the user before proceeding if you see it.
4. **`requirements.txt`** diff between prod HEAD and the incoming dev tip — tells you whether Step 6 needs `pip install`.

Also check for a **concurrent session**: `pgrep -af 'claude|cursor'` and a fresh `git status` on the shared working tree immediately before merging. If another session has in-flight edits, do the merge in an isolated worktree (Step 3) and never touch that session's files.

---

## Step 2 — Land outstanding dev work first

If `git status` in the dev clone (`/home/ubuntu/uiv2/git/MindWealth_UI`, `chatbot-dev`) is dirty, commit and push it before merging — the merge diff should be computed against a clean, fully-pushed `chatbot-dev`.

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
git branch --show-current   # must be chatbot-dev
git status
```

Use `robust-test-and-dev-deploy`'s `git-commit-dev.sh` / `git-push-dev.sh` (same scripts, this skill does not duplicate them):

```bash
SKILL_SCRIPTS=/home/ubuntu/uiv2/git/MindWealth_UI/.claude/skills/robust-test-and-dev-deploy/scripts
bash "$SKILL_SCRIPTS/git-commit-dev.sh" /home/ubuntu/uiv2/git/MindWealth_UI -m "<summary>"
bash "$SKILL_SCRIPTS/git-push-dev.sh" /home/ubuntu/uiv2/git/MindWealth_UI chatbot-dev
```

**If a concurrent session's edits are mixed into `git status`:** stage and commit only your own scoped files by name. Never `git add -A` here.

---

## Step 3 — Merge in an isolated worktree

Never run `git merge` directly in the shared `chatbot-dev` checkout — it has no `chatbot-prod` branch checked out anyway, and a worktree keeps this fully isolated from any other session using the same clone.

```bash
WT=/tmp/claude-*/scratchpad/prodmerge   # use this session's actual scratchpad path
git worktree add "$WT" chatbot-prod     # or: git worktree add "$WT" <local-chatbot-prod-sha> if origin is stale (Step 1 finding #1)

git -C "$WT" merge --no-ff origin/chatbot-dev -m "merge chatbot-dev: <one-line summary of what's shipping>

<optional body: notable changes>

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**Zero tolerance on conflicts.** If the merge reports any `CONFLICT`, stop — do not resolve source-code conflicts automatically. Report the conflicting files to the user and ask how to proceed (this has not happened yet in practice; every merge so far has been clean because `chatbot-dev` is the sole upstream of `chatbot-prod`, but do not assume it always will be).

Verify before pushing:

```bash
git -C "$WT" merge-base --is-ancestor origin/chatbot-dev HEAD && echo "OK: chatbot-dev fully merged"
git -C "$WT" status --short   # must be empty
```

---

## Step 4 — Push and clean up

```bash
SKILL_SCRIPTS=/home/ubuntu/uiv2/git/MindWealth_UI/.claude/skills/robust-test-and-dev-deploy/scripts
bash "$SKILL_SCRIPTS/git-push-dev.sh" "$WT" chatbot-prod

cd /home/ubuntu/uiv2/git/MindWealth_UI
git fetch origin chatbot-prod
git branch -f chatbot-prod origin/chatbot-prod   # only if not still checked out in the worktree
git worktree remove "$WT"
```

If the branch-ref update fails because the worktree still holds it, remove the worktree first, then `git branch -f`.

---

## Step 5 — Prod clone: pull, preserving live cron data

Prod's own cron pipeline (`install_aws_cron_dual.sh`) writes `monitored_trades.json` and several `macro_intelligence/data/ssi/*` CSVs independently of dev — expect the prod clone's working tree to be dirty with exactly these files, and expect them to be **newer** than whatever dev last committed.

```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI
git status --short   # confirm only known cron-output files are dirty; stop if anything else is dirty

git stash push -u -m "prod-cron-data-pre-merge-pull $(date -u +%Y%m%dT%H%M%SZ)" -- <dirty-files-from-git-status>
git status --short   # must now be clean

git fetch origin
git pull origin chatbot-prod   # must fast-forward cleanly onto a clean tree
```

**Restore prod's cron data, resolving conflicts by timestamp — never by convention:**

```bash
git stash pop
```

If clean, done. If conflicted (the merge likely carried an older dev-side snapshot of the same files), for **each** conflicted file:

1. Compare an embedded timestamp/date on both sides — e.g. `monitored_trades.json`'s `"last_updated"` field, or the last row's date in an SSI CSV. `git diff <file>` shows both sides directly.
2. The side with the later timestamp wins — normally the stash (prod-local) side, since prod's cron runs independently and more frequently updates its own clone. Rebuild the file directly rather than trying `checkout --ours/--theirs` (stash-pop conflicts don't populate merge stages the way a real merge does):
   ```bash
   git show "stash@{0}:<path>" > "<path>"
   git add "<path>"
   ```
3. After every conflicted file is resolved and staged, confirm no conflict markers remain, then **unstage** — prod must never carry a commit:
   ```bash
   grep -rl '<<<<<<<\|>>>>>>>' <resolved-files> && echo "STILL CONFLICTED — do not proceed" || echo "clean"
   git reset
   git stash drop
   git status --short   # ordinary "M" modified-but-unstaged data files — expected end state
   ```

If a "prod-local newer" assumption looks wrong for a given file (dev's side is clearly the fresher/authoritative one), stop and ask the user rather than guessing.

---

## Step 6 — Dependencies and restart

```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI
git diff <old-prod-head>..<new-prod-head> --stat -- requirements.txt   # from Step 1's drift check, or re-run now
# non-empty -> install
.venv/bin/pip install -r requirements.txt

sudo systemctl restart mindwealth-api.service
sleep 3
systemctl is-active mindwealth-api.service
journalctl -u mindwealth-api.service -n 20 --no-pager   # confirm clean stop/start, no traceback
```

If a systemd unit file changed in the merge (`scripts/mindwealth-api.service`), copy it first:

```bash
sudo cp scripts/mindwealth-api.service /etc/systemd/system/mindwealth-api.service
sudo systemctl daemon-reload
```

---

## Step 7 — Smoke tests

```bash
bash /home/ubuntu/uiv2/git/MindWealth_UI/.claude/skills/prod-pull-and-details/scripts/smoke-test-apis.sh
```

**Pass criteria:** all `PASS`, prod `conviction_store` still isolated at `/home/ubuntu/uiv2/prod/MindWealth_UI/conviction_store` and writable, `mindwealth-api.service` active.

Then the two checks the shared script can't do from localhost:

```bash
API_KEY="$(grep -E '^API_KEY=' /home/ubuntu/uiv2/prod/MindWealth_UI/.env | cut -d= -f2-)"
curl -s -H "X-API-Key: $API_KEY" http://51.20.53.218:8506/api/v1/health | python3 -m json.tool
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8512/   # Nuxt UI, if it fronts this API
```

Any `FAIL` — stop, do not proceed to Step 8/9 as SUCCESSFUL. Check `journalctl -u mindwealth-api.service -n 80 --no-pager`, fix, restart, re-run smoke tests.

---

## Step 8 — Update dev_to_prod_migration_todos.md

Add a **closure entry at the top** of the file (right after the Status legend), not a scattered edit through every historical section:

```markdown
## YYYY-MM-DD — MERGE CLOSURE: chatbot-dev -> chatbot-prod, N commits / N files `[DONE]` YYYY-MM-DD

**This closes the git-merge portion of every dated entry below whose commits land in `<old-prod-sha>..<new-prod-sha>`** — i.e. everything from <oldest date> through <newest date>.

**What actually happened:** <numbered summary — drift found, commits merged, conflicts resolved, restart, verification>

**What this does NOT close:**
- `[PROD-ACTION]` runtime/config steps inside individual historical entries are UNVERIFIED unless separately checked
- Core-repo (`/home/ubuntu/MindWealth`) entries are out of scope — different deploy path (nightly cron reads working tree directly)
- `MindwealthUI_Vue` is a separate repo, not touched by this deploy
- Full per-entry re-tagging to `[DONE]` was not performed — only "commits are on chatbot-prod" is proven here
```

Do **not** retroactively mark every historical `[PENDING]` entry `[DONE]` — that overclaims verification of steps (secrets, systemd, bootstrap scripts) this skill did not individually check. Say plainly what was and wasn't verified.

---

## Step 9 — Mandatory job logging

Same three files as every task in this repo (CLAUDE.md "Mandatory Logging Protocol"):

1. `docs/mindwealth_ui_job_status.md` — DONE entry: date, summary of the merge/deploy, SHAs, smoke-test result
2. `docs/mindwealth_ui_repo_job_status_details.md` — assumptions (e.g. "prod's timestamp is authoritative for cron data"), edge cases left open, key decisions (worktree isolation, timestamp-based conflict resolution), caveats for the next developer
3. Commit these three doc files **in the dev clone**, on `chatbot-dev`, using `git-commit-dev.sh` / `git-push-dev.sh` — this is dev-repo bookkeeping about the release, not a prod-clone edit.

---

## When to ask the user (blockers)

| Blocker | Ask |
|---------|-----|
| Local `chatbot-prod` ahead of `origin/chatbot-prod` | Confirm those commits are legitimate before treating local as the merge base |
| Merge reports any conflict | Do not auto-resolve source-code conflicts — show the files, ask |
| Prod clone dirty with something other than known cron-output files | Investigate before stashing — may be another operator's in-progress work |
| Stash-pop conflict where "prod-local is newer" isn't obviously true | Ask rather than guess which side to keep |
| `requirements.txt` changed with unfamiliar packages | Confirm before installing on the live host |
| Smoke tests fail after restart | Do not report SUCCESSFUL — fix or roll back, then re-verify |
| User asks to skip smoke tests or push straight to prod without merging first | Push back — explain the risk, proceed only if they insist |

---

## Final report template

```markdown
## Robust test + prod deploy — <scope>

**Status:** SUCCESSFUL | UNSUCCESSFUL

### Pre-flight
- Local chatbot-prod vs origin: <in sync | N commits ahead, used as base>
- Merge size: N commits / N files
- Prod clone dirty files before pull: <list, expected cron-output only>
- requirements.txt changed: yes/no

### Merge
- Worktree merge: clean / N conflicts (resolved how)
- Pushed: chatbot-prod @ `<sha>` -> divsum127/MindWealth_UI

### Prod deploy
- Stash/pull/pop: clean / N conflicts resolved by timestamp (files: ...)
- pip install: run/skipped
- mindwealth-api.service: restarted, active

### Smoke tests
- smoke-test-apis.sh: PASS/FAIL
- Public authenticated health check: OK/FAIL
- Nuxt :8512: <status>

### Docs
- dev_to_prod_migration_todos.md: closure entry added
- Job status + details: logged

### Not covered by this deploy
- <core-repo entries, MindwealthUI_Vue, unverified PROD-ACTION steps, etc.>

### Blockers for user
- <none or list>
```
