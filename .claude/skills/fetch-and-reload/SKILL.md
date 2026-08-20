---
name: fetch-and-reload
description: >-
  Fetch latest MindWealth UI (Nuxt) changes from origin, build with Node 20, and
  restart the frontend service on EC2. Production (:8512, www.mindwealth.co) and dev
  (:8514) have separate checkouts — pick the right one. Use when the user asks to
  fetch/pull remote changes, redeploy, reload, or restart the frontend server, or
  invokes /fetch-and-reload.
---

# Fetch and Reload — MindWealth UI

Pull latest code, rebuild the Nitro bundle, restart the systemd unit.

## Pick the target first

Prod and dev are **separate checkouts** with separate `.output` directories (since 2026-08-18).
Never build one and restart the other.

| | Dev | Production |
|---|---|---|
| Tree | `/home/ubuntu/MindwealthUI_Vue` | `/home/ubuntu/MindwealthUI_Vue_prod` |
| Branch | `ui-dev` | `presentation-prod` (pinned) |
| Service | `mindwealth-ui-dev.service` | `mindwealth-ui.service` |
| Port | `8514` | `8512` |
| Backend | `127.0.0.1:8507` (dev API) | `127.0.0.1:8506` (prod API) |
| Public URL | `http://51.20.53.218:8514` | `https://www.mindwealth.co` |
| Script | `scripts/fetch-and-reload-dev.sh` | `scripts/fetch-and-reload.sh` |
| Node | v20 via nvm (`nvm use 20`) — both |

**Default to dev.** A production run restarts the public site: confirm with the user before
running it, and treat it as a deploy, not a refresh.

**Always invoke the prod script from the dev tree**
(`/home/ubuntu/MindwealthUI_Vue/scripts/fetch-and-reload.sh`). It operates on the prod tree by
absolute path. The tracked copy *inside* the prod clone is stale until the `scripts/` fixes are
merged to `presentation-prod` — that copy still pulls `origin/main` into the dev tree and restarts
prod, which is the bug this split was made to remove.

## Why the split exists

Both units previously ran from `/home/ubuntu/MindwealthUI_Vue` with a relative
`ExecStart=node .output/server/index.mjs`, so they shared one build. A dev `npm run build`
overwrote the bundle prod would load at its next start — including an unattended
`Restart=on-failure`. `ExecStart` is now an absolute path in both units so a `WorkingDirectory`
edit cannot silently repoint a service again.

## Workflow (execute — do not only describe)

### 1. Preflight

```bash
cd /home/ubuntu/MindwealthUI_Vue        # dev; use _prod for a production deploy
git fetch origin
git status -sb
curl -s http://127.0.0.1:8507/api/v1/health | head -c 120; echo
```

For prod, the backend health check is `http://127.0.0.1:8506/api/v1/health`.

### 2. Run the deploy script

**Dev:**

```bash
bash /home/ubuntu/MindwealthUI_Vue/scripts/fetch-and-reload-dev.sh
```

**Production — confirm with the user first:**

```bash
bash /home/ubuntu/MindwealthUI_Vue/scripts/fetch-and-reload.sh
```

The prod script refuses to run if the prod clone has local changes (it is pull-only), uses
`git merge --ff-only` so divergence fails loudly instead of being merged or reset in prod, installs
with `npm ci` for a lockfile-exact build, and prompts before restarting. Non-interactive callers
must pass `DEPLOY_YES=1`; without it the script builds, stages `.output`, and exits before the restart.

### 3. Manual equivalent

```bash
cd /home/ubuntu/MindwealthUI_Vue_prod
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 20
git fetch origin presentation-prod && git merge --ff-only origin/presentation-prod
npm ci
npm run build
sudo systemctl restart mindwealth-ui
```

Nuxt requires **Node 20+**. System `/usr/bin/node` (v18) is too old — always use nvm.

### 4. Verify

```bash
sudo systemctl status mindwealth-ui --no-pager
curl -s -o /dev/null -w "root HTTP %{http_code}\n" http://127.0.0.1:8512/
curl -s -o /dev/null -w "meta HTTP %{http_code}\n" http://127.0.0.1:8512/api/meta
curl -s -o /dev/null -w "public HTTP %{http_code}\n" https://www.mindwealth.co/
git log --oneline -3
```

`/` must be **200**. `/api/meta` returns **401** unauthenticated and that is healthy — it means the
BFF is up and the auth gate is rejecting the probe. Do not check it with `curl -sf`: `-f` treats 401
as an error and, under `set -e`, aborts an otherwise-successful deploy. Both scripts previously had
this bug.

After a prod deploy also load one hashed asset (`/_nuxt/*.js`) and confirm 200 — a rebuild without a
restart leaves the running process referencing hashes the rebuild deleted.

### 5. Report to user

- Commits pulled (or "already up to date"), and the deployed short SHA
- Which environment was deployed
- Service status (`active` / failed)
- HTTP check results
- Live URL

### 6. Task log

After completion, append entry to `/home/ubuntu/.cursor/global_repo_todos.md` (today's date, next
sequence number, SUCCESSFUL or UNSUCCESSFUL).

## Secrets

`NUXT_API_KEY` lives in root-owned `0600` drop-ins at
`/etc/systemd/system/<unit>.service.d/secrets.conf`, not in the repo unit templates. Reinstalling a
template therefore cannot drop the key. Verify with `systemctl show mindwealth-ui -p Environment`.
Never paste the key into chat, docs, or git.

## Stopping a Nitro process

Never `pkill -f ".output/server/index.mjs"` — it matches **both** systemd units, and because a clean
SIGTERM is not a failure, `Restart=on-failure` will not bring them back. This caused a 14m50s outage
on `www.mindwealth.co` on 2026-08-17. Stop test servers by PID or by port, and run
`systemctl list-units | grep -i nuxt` before any pattern kill.

## When build is skipped

Run `npm ci` (prod) or `npm install` (dev) only if `package-lock.json` changed in the pull. Always run
`npm run build` before restart when any source file changed.

Env-only changes (systemd `NUXT_*` vars): edit `scripts/mindwealth-ui.service`, copy to
`/etc/systemd/system/`, `daemon-reload`, `restart` — no build needed.

## Failure handling

| Symptom | Action |
|---------|--------|
| `npm run build` fails | Read error; fix or report; do not restart |
| Script refuses: prod clone has local changes | Someone used the prod clone as a workspace. Inspect `git status`; do not discard without asking |
| Script refuses: not a fast-forward | `presentation-prod` diverged from origin. Resolve on the branch, not in the prod clone |
| Service fails after restart | `journalctl -u mindwealth-ui -n 50 --no-pager` |
| `EADDRINUSE` on 8512 | `ss -tlnp \| grep 8512` |
| UI 200 but empty data | Check API: `curl http://127.0.0.1:8506/api/v1/health` |

## Related docs

- `started.md` — full systemd deploy reference
- `.claude/skills/mindwealth-hosting/SKILL.md` — domain, nginx, SSL
- `docs/dev_to_prod_migration_todos.md` (in `MindWealth_UI`) — 2026-08-18 entry on the prod/dev split
