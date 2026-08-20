# Robust test and prod deploy — reference

## Path / branch / port quick reference

| Item | Dev | Prod |
|------|-----|------|
| Repo root | `/home/ubuntu/uiv2/git/MindWealth_UI` | `/home/ubuntu/uiv2/prod/MindWealth_UI` |
| Branch | `chatbot-dev` | `chatbot-prod` |
| API port | `:8507` (127.0.0.1) | `:8506` (0.0.0.0, public) |
| systemd | `mindwealth-api-dev.service` | `mindwealth-api.service` |
| Public URL | — | `http://51.20.53.218:8506/api/v1` |
| Nuxt UI | `MindwealthUI_Vue` `ui-dev` `:8514` | separate repo, `:8512` — **not covered by this skill** |

## Why the pre-flight drift check exists (2026-08-20 incident)

A routine "merge dev to prod" nearly reverted live code because `origin/chatbot-prod` was **5 commits behind** the actual state of both the local `chatbot-prod` branch and the running prod clone — someone had pulled those commits onto the prod host directly without ever pushing them to GitHub. A merge computed the naive way (`git checkout chatbot-prod && git pull && git merge origin/chatbot-dev && git push`) would have based the merge on the stale `origin` ref, and the push would have overwritten GitHub's copy with something missing those 5 commits — the prod clone would then look fine (it already had them locally) until the *next* pull silently dropped them.

**Rule of thumb:** always diff local `chatbot-prod` against `origin/chatbot-prod` first. If they differ, local is very likely the more current one (it reflects whatever was actually deployed), but confirm with the user if the divergence is large or unexplained.

## Why worktree isolation exists

Merging in the shared dev checkout is risky when another agent session or human might have uncommitted edits in that same working tree at the same time — `git merge`/`git checkout` there can stomp on in-progress work with no warning. `git worktree add <tmp-path> chatbot-prod` gives a second, fully independent working directory backed by the same `.git` object store — the merge happens there, gets pushed, and the worktree is torn down. The shared checkout is never touched by this skill except to fetch/read branch refs and to commit *your own* scoped documentation files.

```bash
git worktree list             # see what's active
git worktree remove <path>    # clean up when done (fails safely if dirty)
git worktree remove <path> --force   # only if you are certain nothing valuable is inside
```

## Why timestamp-based conflict resolution, not blanket "ours"/"theirs"

The prod clone's cron-managed files (`monitored_trades.json`, several `macro_intelligence/data/ssi/*.csv`, `aaii_sentiment.xls`) are **not authored code** — they're independent daily snapshots written by prod's own cron, separate from dev's cron. A merge from dev almost always carries an *older* copy of the same series, because dev's last commit of that file predates whatever prod's cron has written since. Automatically preferring one side by convention (always "ours", always "theirs") is wrong in general — the correct rule is "whichever side is chronologically newer wins," verified per file:

```bash
# Look for an embedded timestamp/date field on both sides of the conflict
git diff macro_intelligence/data/ssi/nh_nl_ratio.csv     # last row's date, both sides
git diff monitored_trades.json | grep last_updated        # both "last_updated" values
```

If a file has no obvious embedded date (e.g. a binary `.xls`), fall back to filesystem mtime as a weaker signal, or ask the user.

## `git stash pop` conflict resolution — mechanics

Unlike a real 3-way `git merge`, a conflicted `git stash pop` does **not** populate stage 2/3 the way `git checkout --ours`/`--theirs` expects, so those flags silently no-op. Rebuild the file directly from the stash blob instead:

```bash
git show "stash@{0}:<path>" > "<path>"   # overwrite working copy with the stash's version
git add "<path>"                          # clears the conflict marker state
```

After all conflicts are resolved and staged:

```bash
grep -rl '<<<<<<<\|>>>>>>>' <every-resolved-file>   # must return nothing
git reset                                            # unstage — prod never carries staged/committed changes
git stash drop                                       # only after you're sure the resolution is correct
```

If you drop the stash before confirming the resolution, the prod-local version is gone for good — always run the conflict-marker grep check before dropping.

## dev_to_prod_migration_todos.md closure entry — template

```markdown
## YYYY-MM-DD — MERGE CLOSURE: chatbot-dev -> chatbot-prod, N commits / N files `[DONE]` YYYY-MM-DD

**This closes the git-merge portion of every dated entry below whose commits land in `<old-sha>..<new-sha>`** (in practice: <date range>).

**What actually happened, in order:**
1. <drift finding, if any>
2. <outstanding dev work committed/pushed, SHAs>
3. <merge result — worktree, conflict count, push SHA>
4. <prod pull, stash conflicts resolved how>
5. <restart, install>
6. <verification result>

**What this does NOT close:**
- `[PROD-ACTION]` runtime/config steps inside individual historical entries — UNVERIFIED unless separately checked tonight
- Core-repo (`/home/ubuntu/MindWealth`) entries — out of scope, different deploy path
- `MindwealthUI_Vue` — separate repo, not touched
- Full per-entry re-tagging to `[DONE]` — not performed; only "commits are on chatbot-prod" is proven

Full details: `docs/mindwealth_ui_job_status.md` (<date>, "<entry title>") and `docs/mindwealth_ui_repo_job_status_details.md` (same).
```

## Do not

- Merge directly in the shared `chatbot-dev` checkout — always use an isolated worktree
- Base a merge on `origin/chatbot-prod` without first diffing it against local `chatbot-prod`
- Auto-resolve a genuine source-code merge conflict — stop and ask
- Assume "stash side wins" for a data-file conflict without checking a timestamp
- `git commit` anything in `/home/ubuntu/uiv2/prod/MindWealth_UI`, ever, including "just to resolve the conflict"
- Drop a stash before grepping for leftover `<<<<<<<`/`>>>>>>>` markers
- Retroactively mark every historical migration-doc entry `[DONE]` without individually verifying its `[PROD-ACTION]` steps
- Restart `mindwealth-api.service` without running smoke tests immediately after
- Push to `chatbot-prod` without the user's explicit go-ahead for a prod release
