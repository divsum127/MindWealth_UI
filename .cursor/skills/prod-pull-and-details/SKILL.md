---
name: prod-pull-and-details
description: >-
  MindWealth_UI dev/prod deploy workflow: git clone vs prod clone paths,
  chatbot-dev/chatbot-prod branches, push and pull steps, systemd restarts,
  and smoke tests after every dev push or prod pull. Use when deploying code,
  pulling chatbot-prod, restarting APIs, verifying prod isolation, or when
  the user mentions prod-pull, chatbot-prod, chatbot-dev, 8506, or 8507.
disable-model-invocation: true
---

# Prod pull and deploy details

## Architecture

```text
DEV (edit + commit)                    PROD (pull only)
uiv2/git/MindWealth_UI                 uiv2/prod/MindWealth_UI
branch: chatbot-dev                    branch: chatbot-prod
API :8507 (127.0.0.1, --reload)        API :8506 (0.0.0.0, public)
systemd: mindwealth-api-dev            systemd: mindwealth-api
enabled at boot: NO                    enabled at boot: YES

Remote: origin = divsum127/MindWealth_UI (canonical)
        upstream = ahiliitb/MindWealth_UI (legacy upstream)
```

**Rule:** Code flows `chatbot-dev` → merge → `chatbot-prod` → prod clone pull. **Never commit from prod clone.**

**Cursor rule:** `/home/ubuntu/uiv2/prod/MindWealth_UI` is **read-only** for the agent. Never edit prod source files; warn the user and redirect to git clone. See `.cursor/rules/mindwealth-ui-repository-rules.mdc` (Production clone — do not edit).

---

## Path reference

| Item | Dev (git clone) | Prod clone |
|------|-----------------|------------|
| Repo root | `/home/ubuntu/uiv2/git/MindWealth_UI` | `/home/ubuntu/uiv2/prod/MindWealth_UI` |
| Python venv | `.venv/` in repo root | `.venv/` in repo root |
| Secrets | `.env`, `.streamlit/secrets.toml` | same files (server-local, not in git) |
| Runtime data | `trade_store/`, `conviction_store/`, `chatbot/data/`, `chatbot/history/`, `chatbot/jobs/`, `macro_intelligence/logs/`, `macro_intelligence/output/`, `ssi.db` | same (gitignored, per-clone) |
| Macro DB | `macro_intelligence/data/ssi/runic.db` | same path under prod root |
| Shared engine | `/home/ubuntu/MindWealth` (C++ strategies, email) | same |
| Nuxt UI | `/home/ubuntu/MindwealthUI_Vue` on **:8512** | proxies to prod API **:8506** |

### Key scripts

| Script | Branch | Purpose |
|--------|--------|---------|
| `scripts/start_api_dev.sh` | `chatbot-dev` | Manual dev API on :8507 with reload |
| `scripts/start_api.sh` | both | Shared uvicorn launcher (`API_HOST`, `API_PORT`, `UVICORN_RELOAD`) |
| `scripts/setup-mindwealth-api-dev-systemd.sh` | `chatbot-dev` | Install `mindwealth-api-dev.service` |
| `scripts/mindwealth-api-dev.service` | `chatbot-dev` | systemd unit for dev API |
| `scripts/mindwealth-api.service` | `chatbot-prod` | systemd unit for prod API (prod paths) |
| `scripts/prod-pull-and-restart.sh` | `chatbot-prod` | Fetch, pull, pip install, restart prod API |
| `scripts/install_aws_cron_dual.sh` | `chatbot-dev` | Macro crons for **both** git + prod clones |

### systemd units (installed on host)

| Service | Unit file source | Port | Bind |
|---------|------------------|------|------|
| Prod API | `uiv2/prod/.../scripts/mindwealth-api.service` → `/etc/systemd/system/` | 8506 | `0.0.0.0` |
| Dev API | `uiv2/git/.../scripts/mindwealth-api-dev.service` → `/etc/systemd/system/` | 8507 | `127.0.0.1` |

Public prod API: `http://51.20.53.218:8506/api/v1`

---

## Git identity (commits must show divsum127)

Both clones have **repo-local** config (overrides global `Mindwealth`):

```bash
git config user.name "divsum127"
git config user.email "117962699+divsum127@users.noreply.github.com"
```

Cursor may add `Co-authored-by: Cursor <cursoragent@cursor.com>`. Strip before push if you want only divsum127 on GitHub:

```bash
MSG=$(git log -1 --format=%B | sed '/^Co-authored-by: Cursor/d')
git commit --amend -m "$MSG"
```

---

## Workflow A — Dev push (after coding in git clone)

**Where:** `/home/ubuntu/uiv2/git/MindWealth_UI` on `chatbot-dev`

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
git status                    # confirm chatbot-dev, no runtime data staged
git add <tracked-files-only>  # never add trade_store/, conviction_store/, etc.
git commit -m "feat: ..."
git push origin chatbot-dev
```

**If `requirements.txt` changed:**

```bash
.venv/bin/pip install -r requirements.txt
sudo systemctl restart mindwealth-api-dev.service
```

**If only Python code changed** and dev service runs with `--reload`, restart is often optional. Restart anyway after push if unsure.

### Smoke tests after dev push

Run the skill script (preferred):

```bash
bash /home/ubuntu/uiv2/git/MindWealth_UI/.cursor/skills/prod-pull-and-details/scripts/smoke-test-apis.sh
```

Or manually:

```bash
# 1. Dev API health — must point at GIT conviction_store
curl -s http://127.0.0.1:8507/api/v1/health | python3 -m json.tool
# expect: status ok, conviction_store ends with uiv2/git/MindWealth_UI/conviction_store

# 2. Prod API unchanged — still prod paths
curl -s http://127.0.0.1:8506/api/v1/health | python3 -m json.tool
# expect: conviction_store ends with uiv2/prod/MindWealth_UI/conviction_store

# 3. systemd
systemctl is-active mindwealth-api-dev.service mindwealth-api.service

# 4. Quick data endpoint
curl -s http://127.0.0.1:8507/api/v1/signals/counts | python3 -m json.tool | head
```

**Isolation check:** Editing a file in git clone must **not** change prod health `conviction_store` path or prod `version` until prod pull.

---

## Workflow B — Release to prod (merge + pull)

### B1. Merge dev → prod on GitHub (or locally in git clone)

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
git fetch origin
git checkout chatbot-prod
git pull origin chatbot-prod
git merge origin/chatbot-dev   # or merge via GitHub PR
git push origin chatbot-prod
git checkout chatbot-dev
```

### B2. Deploy prod clone (pull only)

**Preferred — use deploy script:**

```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI
bash scripts/prod-pull-and-restart.sh
```

**Manual equivalent:**

```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI
git fetch origin
git checkout chatbot-prod
git pull origin chatbot-prod
.venv/bin/pip install -r requirements.txt          # if requirements changed
sudo cp scripts/mindwealth-api.service /etc/systemd/system/mindwealth-api.service
sudo systemctl daemon-reload
sudo systemctl restart mindwealth-api.service
curl -s http://127.0.0.1:8506/api/v1/health | python3 -m json.tool
```

**Never** `git commit` or `git push` from prod clone.

### Smoke tests after prod pull

```bash
bash /home/ubuntu/uiv2/git/MindWealth_UI/.cursor/skills/prod-pull-and-details/scripts/smoke-test-apis.sh
```

Additional prod checks:

```bash
# Health — prod store path + writable
curl -s http://127.0.0.1:8506/api/v1/health | python3 -m json.tool

# Public reachability (from host)
curl -s http://51.20.53.218:8506/api/v1/health | python3 -m json.tool

# Signals pipeline
curl -s http://127.0.0.1:8506/api/v1/signals/counts | python3 -m json.tool

# Nuxt UI still up (optional)
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8512/
```

**Pass criteria:**

| Check | Expected |
|-------|----------|
| `status` | `ok` |
| `conviction_store` (8506) | `/home/ubuntu/uiv2/prod/MindWealth_UI/conviction_store` |
| `conviction_store` (8507) | `/home/ubuntu/uiv2/git/MindWealth_UI/conviction_store` |
| `conviction_store_writable` | `true` |
| `mindwealth-api.service` | `active` |

---

## Restart commands

| Action | Command |
|--------|---------|
| Restart prod API | `sudo systemctl restart mindwealth-api.service` |
| Restart dev API | `sudo systemctl restart mindwealth-api-dev.service` |
| Start dev API (if stopped) | `sudo systemctl start mindwealth-api-dev.service` |
| Prod logs | `journalctl -u mindwealth-api.service -n 50 --no-pager` |
| Dev logs | `journalctl -u mindwealth-api-dev.service -n 50 --no-pager` |
| Reload after `.env` / `secrets.toml` change | restart the affected API service (keys load at import time) |

---

## Cron (dual pipeline)

Installed via `scripts/install_aws_cron_dual.sh`. Runs macro jobs in **both** clones:

- `run_ssi_daily.py` — weekdays 08:00 ET
- `run_macro_friday_pull.py` — Fri 17:30 ET
- `run_macro_nightly.py` — weekdays 18:00 ET
- `run_emission_vectors_daily.py` — weekdays 18:15 ET

Nightly email + trade data: `/home/ubuntu/MindWealth/emailscript.sh` (22:00) updates trade data in git **and** prod via `update_trade_data.sh`.

Verify: `crontab -l`

---

## Do not

- Commit from `/home/ubuntu/uiv2/prod/MindWealth_UI`
- Track or commit `trade_store/`, `conviction_store/`, `chatbot/data/`, `.env`, `secrets.toml`
- Run prod API from git clone paths (8506 must use prod clone)
- `git pull` on prod without being on `chatbot-prod`
- Skip smoke tests after deploy

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Prod shows git `conviction_store` | systemd still points at git clone | `sudo cp prod/.../mindwealth-api.service /etc/systemd/system/` + restart |
| API 401 on chat after secret change | uvicorn not restarted | `sudo systemctl restart mindwealth-api.service` |
| `git pull` overwrites data | runtime dirs tracked in git | ensure `.gitignore` + `git rm --cached` on data dirs |
| Dev API not reachable | service not started | `sudo systemctl start mindwealth-api-dev.service` |
| Push auth fails | need GitHub credentials | `git push origin <branch>` with PAT or SSH |

---

## Agent checklist

After any dev push or prod pull, the agent must:

```
Deploy verification:
- [ ] Correct branch and clone (dev=git/chatbot-dev, prod=prod/chatbot-prod)
- [ ] No runtime data committed
- [ ] pip install if requirements.txt changed
- [ ] Restart affected API service(s)
- [ ] Run smoke-test-apis.sh (or equivalent manual checks)
- [ ] Confirm conviction_store paths prove isolation
- [ ] Update global_repo_todos.md when task complete
```
