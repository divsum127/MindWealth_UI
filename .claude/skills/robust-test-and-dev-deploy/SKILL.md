---
name: robust-test-and-dev-deploy
description: >-
  Post-implementation verification loop: audit mocks/stale data, update API
  endpoints and docs, run pytest and endpoint smoke tests, deploy to dev
  (MindWealth_UI chatbot-dev :8507, MindwealthUI_Vue ui-dev :8514), commit and
  push to dev branches only, verify isolation from prod, and update
  dev_to_prod_migration_todos. Use after feature work, bug fixes, or
  conviction/macro/API/UI changes when the user asks for robust testing, dev
  deploy, or end-to-end verification before prod.
disable-model-invocation: true
---

# Robust test and dev deploy

Run this skill **after** implementing a feature or fix. **Loop at every step until green.** Ask the user when blocked (missing secrets, prod runtime writes, GitHub auth, ambiguous business rules).

**Never** edit `/home/ubuntu/uiv2/prod/` — prod clone is deploy/read-only only.

**GitHub identity (mandatory):** All commits and pushes use the **`divsum127`** GitHub account only.

| Rule | Requirement |
|------|-------------|
| Commit author | `divsum127 <117962699+divsum127@users.noreply.github.com>` via `scripts/git-commit-dev.sh` |
| Push auth | `divsum127` PAT (`~/.cursor/github_pat`) via `scripts/git-push-dev.sh` |
| Push targets | Allowlisted repos only (see table below) |
| **Never** | Plain `git commit` / `git push` (may use Cursor default or wrong remote) |
| **Never** | Push to `ahiliitb/*` (`upstream` remote) |
| **Never** | `git config user.*` — do not change global or local git config |

**GitHub PAT:** `~/.cursor/github_pat` (mode `600`, **never commit**). Rotate if exposed in chat/logs.

**Canonical remotes:**

| Repo | Remote | Branch | Notes |
|------|--------|--------|-------|
| MindWealth_UI | `divsum127/MindWealth_UI` | `chatbot-dev` | |
| `docs/mindwealth-api-docs` submodule | `divsum127/mindwealth-api-docs` | `main` | |
| MindwealthUI_Vue | `D-ParthChauhan/MindwealthUI_Vue` | `ui-dev` | Parth's repo; **divsum127 has collaborator push access** — commits still authored as divsum127 |

**Related skills:**
- Deploy/restart/smoke: [prod-pull-and-details](../prod-pull-and-details/SKILL.md)
- New/changed endpoints: [api-creation-2](../api-creation-2/SKILL.md)
- Detailed checklists: [reference.md](reference.md)

---

## Dev repositories and branches (commit + push here only)

All implementation, commits, and pushes go to **dev clones on dev branches**. Do **not** commit or push from the prod clone.

| Repo | Dev path | **Dev branch** | Dev service / port |
|------|----------|----------------|-------------------|
| **MindWealth_UI** (API, SSI, chatbot, conviction backend) | `/home/ubuntu/uiv2/git/MindWealth_UI` | **`chatbot-dev`** | `mindwealth-api-dev.service` → `:8507` |
| **MindwealthUI_Vue** (Nuxt UI — **separate git repo**) | `/home/ubuntu/MindwealthUI_Vue` | **`ui-dev`** | `mindwealth-ui-dev` → `:8514` (dev build) |

**Prod counterparts (do not commit here):**

| Repo | Prod path | Prod branch | Prod port |
|------|-----------|-------------|-----------|
| MindWealth_UI | `/home/ubuntu/uiv2/prod/MindWealth_UI` | `chatbot-prod` | `:8506` |
| MindwealthUI_Vue | prod host deploy | merge from `ui-dev` at cutover | `:8512` |

### Git rules (mandatory before closing the skill)

1. **Verify branch** before every commit:
   ```bash
   cd /home/ubuntu/uiv2/git/MindWealth_UI && git branch --show-current   # must be chatbot-dev
   cd /home/ubuntu/MindwealthUI_Vue && git branch --show-current         # must be ui-dev
   ```
2. **Commit** only files for the current task (do not sweep unrelated dirty files). **Always** use `git-commit-dev.sh` so author is `divsum127` — never plain `git commit` (Cursor/default identity).
3. **Push** via **`divsum127` PAT** to **allowlisted remotes** after deploy + smoke pass. **Always** use `git-push-dev.sh` — never plain `git push origin`.

   ```bash
   SKILL_SCRIPTS=/home/ubuntu/uiv2/git/MindWealth_UI/.claude/skills/robust-test-and-dev-deploy/scripts

   # Commit (divsum127 author)
   bash "$SKILL_SCRIPTS/git-commit-dev.sh" /home/ubuntu/uiv2/git/MindWealth_UI -m "feat/fix: <summary>"

   # Push MindWealth_UI → chatbot-dev (divsum127/MindWealth_UI)
   bash "$SKILL_SCRIPTS/git-push-dev.sh" /home/ubuntu/uiv2/git/MindWealth_UI chatbot-dev

   # API docs submodule (if changed): commit inside submodule first, then parent pointer
   bash "$SKILL_SCRIPTS/git-commit-dev.sh" /home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth-api-docs -m "docs: <summary>"
   bash "$SKILL_SCRIPTS/git-push-dev.sh" /home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth-api-docs main

   # MindwealthUI_Vue → ui-dev (D-ParthChauhan/MindwealthUI_Vue; divsum127 collaborator access)
   bash "$SKILL_SCRIPTS/git-commit-dev.sh" /home/ubuntu/MindwealthUI_Vue -m "feat/fix(ui): <summary>"
   bash "$SKILL_SCRIPTS/git-push-dev.sh" /home/ubuntu/MindwealthUI_Vue ui-dev
   ```

   Override PAT path: `GITHUB_PAT_FILE=/path/to/pat`. Override slug: `GITHUB_PUSH_SLUG=owner/repo` (must be on allowlist).

4. If UI changed, commit **both** repos (API + Nuxt are separate remotes).
5. **API docs submodule:** if `docs/mindwealth-api-docs/` changed, commit + push submodule on `main` **as divsum127**, then commit submodule pointer in parent on `chatbot-dev`.
6. **Never** `git push` to `chatbot-prod`, prod clone paths, `ahiliitb/*`, or prod UI branches unless the user explicitly requests a prod release.

**Do not commit:** `trade_store/`, `conviction_store/`, `.env`, `secrets.toml`, `runic.db`, runtime CSVs, or other generated/runtime data.

---

## Master checklist

Copy and track:

```
Robust test + dev deploy:
- [ ] 0. Branch check — MindWealth_UI on chatbot-dev; MindwealthUI_Vue on ui-dev (if UI touched)
- [ ] 1. Codebase health — no breaks, no unintended mocks/stale data
- [ ] 2. API endpoints updated (if needed)
- [ ] 3. API docs updated (if needed)
- [ ] 4. All endpoints re-tested
- [ ] 5. Deploy to dev (restart API + Nuxt dev services)
- [ ] 6. Post-deploy verification on dev
- [ ] 7. Commit + push to dev branches (chatbot-dev / ui-dev)
- [ ] 8. dev_to_prod_migration_todos.md updated
- [ ] 9. Job status + global_repo_todos logged
```

---

## Step 1 — Verify codebase health

At any of the steps below loop until everything is fixed, ask me in case of any blockers.

### 1a. Run tests (tiered)

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI

# 1) Tests for touched area first
.venv/bin/python -m pytest tests/test_<relevant>.py -q

# 2) Related API tests if API touched
.venv/bin/python -m pytest tests/test_api_*.py -q

# 3) Full suite before deploy
.venv/bin/python -m pytest tests/ -q
```

Fix failures before continuing. Re-run failed tests after each fix.

### 1b. No unintended mocks or stale data

**Production/runtime code must not use mock implementations** unless the user explicitly specified them. Document any user-approved mocks in the final summary (file + symbol + reason).

Audit changed files:

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
rg -n "mock|Mock|TODO.*mock|FIXME|placeholder|hardcoded|fake_" \
  --glob '!tests/**' --glob '!**/*mock*' src/ api/ scripts/ chatbot/
```

| Finding | Action |
|---------|--------|
| `unittest.mock` in non-test code | Replace with real implementation or ask user |
| Hardcoded sample rows / static JSON served as live data | Wire to real store/DB/CSV |
| `PROXY` / stale cache paths when real source exists | Run backfill or refresh script |
| Comment says "temporary" / "for now" | Resolve or flag user |

**Stale-data hotspots** (verify freshness after logic changes):

| Area | Real source | Refresh |
|------|-------------|---------|
| Conviction records | `conviction_store/*.json` | `scripts/update_conviction_fundamentals.py` |
| PE history cache | `conviction_store/pe_history_cache/` | purge `*_sec.json` if PE logic changed, then recalc |
| Macro SSI | `macro_intelligence/data/ssi/runic.db`, `positioning.json` | `scripts/run_ssi_daily.py` etc. |
| CNN Fear & Greed | `macro_intelligence/data/ssi/cnn_fear_greed.csv` | daily cron / backfill scripts |
| Trade signals | `trade_store/` (via `src/config_paths.py`) | MindWealth `emailscript.sh` / `update_trade_data.sh` |

### 1c. Import and lint sanity

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
export PYTHONPATH="$(pwd)"
.venv/bin/python -c "from api.main import app; print('API import OK', app.title)"
```

Fix import errors before proceeding.

---

## Step 2 — Update API endpoints (if needed)

Skip if change is internal-only (no HTTP surface change).

When request/response shape, routes, or behavior changed:

1. Update `api/routers/`, `api/services/`, `api/schemas/` per [api-creation-2](../api-creation-2/SKILL.md).
2. Register router in `api/main.py` if new.
3. Bump `API_VERSION` in `api/main.py` for meaningful releases.
4. Add/update tests in `tests/test_api_<service>.py` or `tests/test_api_integration.py`.
5. Use `src/config_paths.py` for paths — no hardcoded clone-specific absolutes.

**Auth:** routes use `optional_api_key`; when `API_KEY` is set, send `X-API-Key` in manual curls.

---

## Step 3 — Update API docs (if needed)

**Canonical docs path:** `docs/mindwealth-api-docs/` (not `docs/api/`).

When endpoints changed or added:

1. Endpoint page: `docs/mindwealth-api-docs/services/<service>/endpoints/<verb>-<slug>.md`
2. Service README + `services/README.md`
3. `docs/mindwealth-api-docs/changelog.md`
4. Regenerate OpenAPI snapshot:

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
export PYTHONPATH="$(pwd)"
.venv/bin/python scripts/export_openapi.py
```

Commit docs submodule on its `main` branch when endpoint contracts change; always update files locally as part of this workflow. Parent `MindWealth_UI` commit on **`chatbot-dev`** must include the updated submodule pointer.

---

## Step 4 — Test all endpoints again

### 4a. pytest API suite

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
.venv/bin/python -m pytest tests/test_api_*.py -q
```

### 4b. Live dev API (after Step 5 restart, or against running :8507)

```bash
DEV_URL=http://127.0.0.1:8507
API_KEY=$(grep -E '^API_KEY=' .env | cut -d= -f2-)

# Health
curl -sf -H "X-API-Key: $API_KEY" "$DEV_URL/api/v1/health" | python3 -m json.tool

# Spot-check changed endpoints (replace paths)
curl -sf -H "X-API-Key: $API_KEY" "$DEV_URL/api/v1/<changed-path>" | python3 -m json.tool | head
```

Hit every endpoint touched in this change. Confirm response fields match docs and schemas.

---

## Step 5 — Deploy to dev

### 5a. MindWealth_UI API (`chatbot-dev`)

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
git branch --show-current   # MUST print: chatbot-dev

# If requirements.txt changed:
.venv/bin/pip install -r requirements.txt

sudo systemctl restart mindwealth-api-dev.service
systemctl is-active mindwealth-api-dev.service
```

### 5b. MindwealthUI_Vue Nuxt (`ui-dev`) — when UI files changed

```bash
cd /home/ubuntu/MindwealthUI_Vue
git branch --show-current   # MUST print: ui-dev

npm run build
sudo systemctl restart mindwealth-ui-dev
systemctl is-active mindwealth-ui-dev
```

If services not installed: `bash scripts/start_api_dev.sh` or see [prod-pull-and-details](../prod-pull-and-details/SKILL.md).

**Never** restart prod (`mindwealth-api.service`) or pull prod clone as part of dev-only deploy.

---

## Step 6 — Verify after dev deploy

```bash
bash /home/ubuntu/uiv2/git/MindWealth_UI/.claude/skills/prod-pull-and-details/scripts/smoke-test-apis.sh
```

**Pass criteria (dev :8507):**

| Check | Expected |
|-------|----------|
| `status` | `ok` |
| `conviction_store` | `/home/ubuntu/uiv2/git/MindWealth_UI/conviction_store` |
| `conviction_store_writable` | `true` |
| `mindwealth-api-dev.service` | `active` |

Re-run Step 4b curls against live :8507. Re-run targeted pytest if deploy surfaced issues.

**Prod isolation:** prod :8506 `conviction_store` must still point at `/home/ubuntu/uiv2/prod/MindWealth_UI/conviction_store` until an explicit prod release.

**Nuxt UI** (`/home/ubuntu/MindwealthUI_Vue` on **`ui-dev`**, dev `:8514`): restart `mindwealth-ui-dev` after `npm run build` when Vue files changed. Not restarted by API-only deploy.

**Logs on failure:**

```bash
journalctl -u mindwealth-api-dev.service -n 80 --no-pager
journalctl -u mindwealth-ui-dev.service -n 80 --no-pager
```

---

## Step 7 — Commit and push to dev branches

After smoke tests pass, commit scoped changes and push to origin **dev branches only**.

### MindWealth_UI → `chatbot-dev`

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
SKILL_SCRIPTS=.claude/skills/robust-test-and-dev-deploy/scripts
git branch --show-current   # chatbot-dev
git status                  # no runtime secrets/data staged
git add <scoped-files>
bash "$SKILL_SCRIPTS/git-commit-dev.sh" "$(pwd)" -m "feat/fix: <summary>"
# verify: git log -1 --format='%an <%ae>'  →  divsum127 <117962699+divsum127@users.noreply.github.com>
bash "$SKILL_SCRIPTS/git-push-dev.sh" "$(pwd)" chatbot-dev
```

### MindwealthUI_Vue → `ui-dev` (if UI changed)

```bash
cd /home/ubuntu/MindwealthUI_Vue
SKILL_SCRIPTS=/home/ubuntu/uiv2/git/MindWealth_UI/.claude/skills/robust-test-and-dev-deploy/scripts
git branch --show-current   # ui-dev
git add <scoped-files>
bash "$SKILL_SCRIPTS/git-commit-dev.sh" "$(pwd)" -m "feat/fix(ui): <summary>"
bash "$SKILL_SCRIPTS/git-push-dev.sh" "$(pwd)" ui-dev
```

Report commit SHAs, author (`divsum127`), and push result. If push fails, check `~/.cursor/github_pat` and allowlist — **never** fall back to plain `git push` or `ahiliitb/upstream`.

---

## Step 8 — Update dev_to_prod_migration_todos.md

Path: `docs/dev_to_prod_migration_todos.md`

Add or update an entry for this change. Include:

- Date + short title
- Status tag: `[PENDING]` / `[DEV-ONLY]` / `[PROD-ACTION]` / `[DONE]`
- **Git files** to merge (`chatbot-dev` → `chatbot-prod`)
- **Dev-only config** to revert at prod cutover (e.g. Nuxt `NUXT_API_BASE_URL` on `:8507`)
- **Runtime artifacts** not in git (`.env` keys, `conviction_store`, `runic.db`, backfill one-time scripts)
- **systemd / host** steps
- **Smoke tests** with `[PENDING]` or `[DONE]` + date
- **Edge cases** and retroactive-effect warnings (cache invalidation, historical data shifts, billing/API-key blockers)

Use existing entries in that file as the template.

---

## Step 9 — Mandatory job logging

After verification (success or failure):

1. `docs/mindwealth_ui_job_status.md` — move TODO → DONE or add DONE entry (status, date, summary, files)
2. `docs/mindwealth_ui_repo_job_status_details.md` — assumptions, deferred items, edge cases, decisions
3. `/home/ubuntu/.cursor/global_repo_todos.md` — same task summary

Step 7 covers prod migration notes; Step 9 covers job tracking. Both required when the change has prod impact.

---

## When to ask the user (blockers)

| Blocker | Ask |
|---------|-----|
| Missing `API_KEY`, `ANTHROPIC_API_KEY`, `FMP_API_KEY`, etc. | User to provision or confirm dev-only skip |
| Need to write prod `conviction_store` / run prod backfill | Human/ops action — agent cannot write prod runtime |
| pytest passes locally but live data empty | Whether to run recalc/backfill scripts |
| GitHub push fails on dev branch | Check `~/.cursor/github_pat`; use `git-push-dev.sh`; repo must be on allowlist |
| Commit shows wrong author (Cursor/Mindwealth/ahiliitb) | Re-commit with `git-commit-dev.sh`; never plain `git commit` |
| Explicit mock requested earlier in thread | Confirm still intentional |

---

## Final report template

```markdown
## Robust test + dev deploy — <task>

**Status:** SUCCESSFUL | UNSUCCESSFUL

### Tests
- Targeted: `pytest tests/test_....py` — N passed
- API: `pytest tests/test_api_*.py` — N passed
- Full: `pytest tests/` — N passed

### Mock audit
- Unintended mocks found: none | list with fixes
- User-approved mocks: none | <file>:<symbol> — <reason>

### API
- Endpoints changed: yes/no — list
- Docs updated: yes/no — paths
- OpenAPI exported: yes/no

### Dev deploy
- Service: mindwealth-api-dev — active
- smoke-test-apis.sh: PASS/FAIL
- Spot checks: <endpoint> — OK

### Git
- MindWealth_UI: `chatbot-dev` @ `<sha>` — author `divsum127`, pushed to `divsum127/MindWealth_UI`: yes/no
- MindwealthUI_Vue: `ui-dev` @ `<sha>` — author `divsum127`, pushed to `D-ParthChauhan/MindwealthUI_Vue`: yes/no (or N/A)

### Migration todos
- Updated: docs/dev_to_prod_migration_todos.md — <section title>
- Prod actions noted: <summary>

### Blockers for user
- <none or list>
```
