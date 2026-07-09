# Dev → Prod migration todos

Living checklist for moving **`chatbot-dev`** work from the git clone to **`chatbot-prod`** / production.

**Dev clone:** `/home/ubuntu/uiv2/git/MindWealth_UI` (branch `chatbot-dev`, API `:8507`)  
**Prod clone:** `/home/ubuntu/uiv2/prod/MindWealth_UI` (branch `chatbot-prod`, API `:8506`)  
**Nuxt UI:** `/home/ubuntu/MindwealthUI_Vue` (`:8512`) — **separate repo**, not deployed via `prod-pull-and-restart.sh`

Update this file **after every meaningful dev change** with what to merge, revert, copy, or configure for prod.

Reference deploy skill: `.cursor/skills/prod-pull-and-details/SKILL.md`

---

## Status legend

| Tag | Meaning |
|-----|---------|
| `[PENDING]` | Not yet on prod |
| `[DEV-ONLY]` | Intentional dev shortcut — **revert** before/at prod cutover |
| `[PROD-ACTION]` | Manual step on server after git merge (secrets, systemd, bootstrap) |
| `[DONE]` | Completed on prod (date in notes) |

---

## Temporary dev-only config (revert for production)

These are **not** in git on the server; they live in **`/etc/systemd/system/`** and must be corrected when prod auth ships.

| Item | Current (dev testing) | Prod target | Status |
|------|----------------------|-------------|--------|
| Nuxt `NUXT_API_BASE_URL` | `http://127.0.0.1:8507` (dev API) | `http://127.0.0.1:8506` (prod API) | `[DEV-ONLY]` `[PENDING]` |
| Nuxt systemd `After` / `Wants` | `mindwealth-api-dev.service` | `mindwealth-api.service` | `[DEV-ONLY]` `[PENDING]` |
| Nuxt `NUXT_PUBLIC_ADMIN_MODE` | `true` | `false` (optional; admin comes from JWT role) | `[DEV-ONLY]` `[PENDING]` |
| Prod API `:8506` | Still **pre-auth** code (no `X-API-Key` / JWT routes) | Auth-enabled code after merge + pull | `[PENDING]` |
| Dev API `:8507` | Auth **enabled**, `0.0.0.0`, `.env` with keys | Keep as dev; no change | OK |

**Revert commands (after prod API has auth code):**

```bash
# Edit /etc/systemd/system/mindwealth-ui.service
#   NUXT_API_BASE_URL=http://127.0.0.1:8506
#   After=network.target mindwealth-api.service
#   Wants=mindwealth-api.service
#   NUXT_PUBLIC_ADMIN_MODE=false   # optional

sudo systemctl daemon-reload
sudo systemctl restart mindwealth-api mindwealth-ui
```

---

## 2026-06-30 — Auth & security hardening (invite-only login)

### 1. Git merge (MindWealth_UI)

`[PENDING]` Commit on `chatbot-dev` → push → merge to `chatbot-prod` → prod clone pull.

**New files (track in git):**

| Path |
|------|
| `api/routers/auth.py` |
| `api/schemas/auth.py` |
| `api/services/auth_service.py` |
| `api/routers/activity.py` |
| `api/schemas/activity.py` |
| `api/services/activity_log_service.py` |
| `src/auth/streamlit_gate.py` |
| `config/users.json.example` |
| `scripts/bootstrap_admin.py` |
| `scripts/invite_user.py` |
| `tests/test_api_auth.py` |
| `tests/test_activity_log.py` |

**Modified files (merge carefully):**

| Path | Notes |
|------|--------|
| `api/dependencies.py` | `require_api_key`, `get_current_user`, `require_admin`, `require_chatbot_user` |
| `api/main.py` | `auth` + `activity` routers; CORS `:8512`; `DOCS_ENABLED` |
| `api/routers/chatbot.py` | JWT required; session ownership; activity chat log hook |
| `api/services/chatbot_service.py` | Owner-scoped sessions/jobs |
| `chatbot/session_manager.py` | `owner_email` on sessions |
| `app.py` | `ensure_streamlit_login()` gate |
| `requirements.txt` | `bcrypt`, `python-jose[cryptography]`, `email-validator` |
| `scripts/mindwealth-api.service` | `EnvironmentFile=-.../.env`; prod paths in **installed** unit |
| `scripts/mindwealth-api-dev.service` | `EnvironmentFile`; `0.0.0.0:8507` |
| `.gitignore` | `config/users.json`, `activity_logs/` |
| `.env.example` | Auth env var comments |
| `tests/test_api_chatbot.py`, `tests/test_api_conviction.py`, `tests/test_api_integration.py` | API key / auth test fixes |

### 2. Runtime files — copy/create on prod (NOT in git)

`[PROD-ACTION]` Do in **prod clone** only after merge; never commit secrets.

| File / dir | Action |
|------------|--------|
| `config/users.json` | **Create** via `scripts/bootstrap_admin.py` on prod (do not copy from dev) |
| `.env` | **Add** vars below to `/home/ubuntu/uiv2/prod/MindWealth_UI/.env` (generate **new** prod secrets or copy policy-approved keys) |
| `activity_logs/` | Auto-created when logging enabled; ensure directory writable |
| `config/.bootstrap_admin_password` | Dev-only helper; **do not** copy to prod |

**Required `.env` keys (prod API):**

```bash
API_KEY=<strong-random>              # same value as NUXT_API_KEY on :8512
JWT_SECRET=<strong-random>
USERS_FILE=config/users.json
INVITE_BASE_URL=http://51.20.53.218:8512
DOCS_ENABLED=false
CHATBOT_REQUIRE_USER=true
JWT_ACCESS_MINUTES=480               # 8h session; match Nuxt cookie
ACTIVITY_LOGS_DIR=activity_logs      # optional override
```

**Streamlit** (`mindwealth-streamlit.service` or env): add `API_KEY`, `MW_AUTH_API_BASE=http://127.0.0.1:8506` after prod auth deploy.

### 3. systemd — prod API

`[PROD-ACTION]` Installed unit: `/etc/systemd/system/mindwealth-api.service`

- `WorkingDirectory=/home/ubuntu/uiv2/prod/MindWealth_UI`
- `EnvironmentFile=-/home/ubuntu/uiv2/prod/MindWealth_UI/.env`
- `ExecStart` → `0.0.0.0:8506` (already public; now requires `X-API-Key`)

Template in git: `scripts/mindwealth-api.service` (paths in template still point at git clone — **installed prod unit** uses prod paths).

```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI
bash scripts/prod-pull-and-restart.sh
# or: git pull origin chatbot-prod && .venv/bin/pip install -r requirements.txt && sudo systemctl restart mindwealth-api
```

### 4. Bootstrap prod admin

`[PROD-ACTION]` After pull + `.env`:

```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI
USERS_FILE=config/users.json JWT_SECRET=... .venv/bin/python scripts/bootstrap_admin.py \
  --email admin@mindwealth.co --name "Admin"
```

### 5. Nuxt frontend (`/home/ubuntu/MindwealthUI_Vue`)

`[PENDING]` Separate from MindWealth_UI git — deploy by pull/build/restart on server.

**Auth-related files to have in Nuxt tree:**

| Path | Purpose |
|------|---------|
| `server/routes/api/v1/[...].ts` | Proxy to FastAPI; JWT cookie on login |
| `composables/useAuth.ts` | Login, session, `useRequestFetch` |
| `middleware/auth.global.ts` | Route protection |
| `plugins/auth-session.ts` | Hydrate session on load |
| `plugins/activity-log.client.ts` | Page/click tracking when enabled |
| `composables/useActivityLog.ts` | Activity batching |
| `pages/login.vue`, `pages/accept-invite.vue`, `pages/admin/users.vue` | Auth UI |
| `components/UserMenu.vue` | Profile + sign out |
| `utils/api-error.ts`, `utils/copy-text.ts` | UX helpers |
| `nuxt.config.ts` | `authSessionMaxAge`, `apiKey`, `apiBaseUrl` |

**Nuxt prod systemd** (`/etc/systemd/system/mindwealth-ui.service`):

```ini
Environment="NUXT_API_BASE_URL=http://127.0.0.1:8506"
Environment="NUXT_API_KEY=<same as prod API_KEY>"
Environment="NUXT_AUTH_SESSION_MAX_AGE=28800"
Environment="NUXT_PUBLIC_ADMIN_MODE=false"
```

```bash
cd /home/ubuntu/MindwealthUI_Vue
npm run build
sudo systemctl restart mindwealth-ui
```

### 6. Post-deploy smoke tests

`[PENDING]`

```bash
# Prod API — key required
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8506/api/v1/health          # expect 401
curl -s -H "X-API-Key: $API_KEY" http://127.0.0.1:8506/api/v1/health                 # expect 200

# Login via Nuxt proxy
curl -s -c /tmp/c.jar -X POST http://127.0.0.1:8512/api/v1/auth/login \
  -H 'Content-Type: application/json' -d '{"email":"...","password":"..."}'
curl -s -b /tmp/c.jar http://127.0.0.1:8512/api/v1/auth/me

# Chatbot requires JWT
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $API_KEY" \
  -X POST http://127.0.0.1:8506/api/v1/chatbot/sessions -H 'Content-Type: application/json' -d '{}'  # 401
```

### 7. Security follow-ups (not blocking merge)

| Item | Status |
|------|--------|
| Rotate leaked keys in `MindWealth/constant.py` | `[PENDING]` |
| AWS SG: keep `8506`/`8507` open only with API key | OK |
| Share `API_KEY` with teammates securely for curl testing | `[PROD-ACTION]` |

---

## 2026-06-30 — Per-user activity logging

Bundled with auth deploy above.

| Area | Prod action |
|------|-------------|
| `activity_logging_enabled` on users | Admin toggles on `/admin/users`; stored in `config/users.json` |
| Log storage | `activity_logs/{email_slug}/navigation.jsonl`, `clicks.jsonl`, `chat.jsonl` |
| Nuxt plugin | `activity-log.client.ts` — only sends when `/auth/me` reports logging on |
| Chat logs | Written in `api/routers/chatbot.py` on message enqueue |

No extra prod steps beyond auth deploy + writable `activity_logs/`.

---

## 2026-06-30 — API rate limiting + Nuxt BFF defense-in-depth

Ship **with auth deploy** on prod `:8506`. Limits are identity-aware (`user:{email}` → `apikey:{hash}` → `ip:{ip}`) so Nuxt proxy traffic from `127.0.0.1` is not collapsed into one IP bucket.

### Git (MindWealth_UI — `chatbot-dev`)

`[PENDING]` Merge with auth hardening.

| Path | Notes |
|------|--------|
| `api/rate_limit.py` | Middleware + slowapi limiter, 429 + `Retry-After` |
| `api/rate_limit_config.py` | Env-backed tier defaults |
| `api/main.py` | `RateLimitMiddleware`, exception handler |
| `requirements.txt` | `slowapi` |
| `tests/test_rate_limit.py` | Burst tests |
| `tests/api_test_helpers.py` | `disable_rate_limits()` for existing suites |
| `.env.example` | `RATE_LIMIT_*` vars |

### Git (Nuxt — `/home/ubuntu/MindwealthUI_Vue`)

| Path | Notes |
|------|--------|
| `server/utils/require-auth.ts` | Cookie gate helper |
| `server/middleware/bff-auth.ts` | 401 on `/api/*` without session (excludes `/api/v1` proxy) |
| `server/middleware/bff-rate-limit.ts` | 100/min per IP on BFF; 5/min on `POST /api/chat` |

Optional Nuxt env:

```bash
NUXT_BFF_RATE_LIMIT_PER_MINUTE=100
NUXT_BFF_CHAT_RATE_LIMIT_PER_MINUTE=5
```

### Prod runtime (not in git)

`[PROD-ACTION]` Add to prod API `.env` (after auth keys):

```bash
RATE_LIMIT_ENABLED=true
# Optional overrides — defaults match plan
RATE_LIMIT_READ_USER=30/10seconds;300/minute
RATE_LIMIT_CHAT_MESSAGES=3/minute;30/hour
RATE_LIMIT_LOGIN_PER_MINUTE=10/minute
```

`[PENDING]` Set `RATE_LIMIT_ENABLED=false` in test/CI only.

### Smoke tests (dev `:8507` + Nuxt `:8512`)

```bash
# Login IP bucket — expect 429 on 6th attempt (email bucket 5/min) or 11th (IP 10/min)
for i in $(seq 1 12); do curl -s -o /dev/null -w "%{http_code}\n" \
  -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"email":"admin@mindwealth.co","password":"wrong"}' \
  http://127.0.0.1:8507/api/v1/auth/login; done

# BFF without cookie — expect 401
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8512/api/dashboard

# BFF with cookie — expect 200 (after browser login)
# curl -b "mw_access_token=..." http://127.0.0.1:8512/api/dashboard
```

### Revert / disable

```bash
# Emergency disable API limits
RATE_LIMIT_ENABLED=false
sudo systemctl restart mindwealth-api-dev   # or mindwealth-api on prod
```

v1 uses **in-memory** counters (single uvicorn worker). Document Redis upgrade if multi-worker later.

### Status: `[PENDING]` (dev implemented; prod after auth merge)

### Curated commit — Release A (auth + rate limits + test fixes)

**Verified:** `349 passed` pytest on `chatbot-dev` (2026-07-09).

Stage **only** these paths for the prod-bound release (exclude macro combo sweeps, data CSV drift, unrelated WIP):

| Area | Paths |
|------|--------|
| Auth | `api/routers/auth.py`, `api/schemas/auth.py`, `api/services/auth_service.py`, `api/dependencies.py`, `config/users.json.example`, `scripts/bootstrap_admin.py`, `scripts/invite_user.py`, `src/auth/streamlit_gate.py`, `app.py` |
| Activity | `api/routers/activity.py`, `api/schemas/activity.py`, `api/services/activity_log_service.py` |
| Rate limits | `api/rate_limit.py`, `api/rate_limit_config.py`, `config/rate_limits.yaml`, `api/main.py`, `requirements.txt`, `.env.example` |
| Chatbot ownership | `api/routers/chatbot.py`, `api/services/chatbot_service.py`, `chatbot/session_manager.py` |
| Tests | `tests/conftest.py`, `tests/api_test_helpers.py`, `tests/test_api_auth.py`, `tests/test_activity_log.py`, `tests/test_rate_limit.py`, `tests/test_api_chatbot.py`, `tests/test_api_integration.py`, `tests/test_api_conviction.py`, `tests/test_api_macro.py`, `tests/test_api_portfolio.py`, `tests/test_api_signals_surface.py`, `tests/test_combo_c_cancel.py` |
| Bug fixes (ship with release) | `src/config_paths.py` (`load_dotenv(override=False)`), `chatbot/config.py`, `chatbot/smart_data_fetcher.py` (entry_or_exit collapse), `api/services/signal_enrichment_service.py` (`function`/`interval` on enrich) |
| Docs | `docs/dev_to_prod_migration_todos.md`, `.gitignore` (activity_logs, users.json) |
| Systemd templates | `scripts/mindwealth-api.service`, `scripts/mindwealth-api-dev.service` |

**Nuxt** (separate repo `/home/ubuntu/MindwealthUI_Vue`): commit `server/utils/require-auth.ts`, `server/middleware/bff-auth.ts`, `server/middleware/bff-rate-limit.ts`, then `sudo systemctl restart mindwealth-ui`.

**Do not stage** for this release unless intentional: `macro_intelligence/data/*`, `monitored_trades.json`, `testing/combo_all_thresholds/`, macro calendar scripts unless already merged separately.

### Merge order

1. Commit Release A on `chatbot-dev` → push
2. Merge `chatbot-dev` → `chatbot-prod`
3. Prod clone: `git pull` + `prod-pull-and-restart.sh`
4. Prod `.env`: `API_KEY`, `JWT_SECRET`, `RATE_LIMIT_ENABLED=true`
5. Bootstrap `config/users.json` on prod
6. Nuxt: commit BFF middleware → restart `mindwealth-ui` → revert `NUXT_API_BASE_URL` to `:8506`
7. Smoke tests (login, BFF 401, rate-limit curl in section above)

---

## Template for future entries

Copy for each new dev feature:

```markdown
## YYYY-MM-DD — Short title

### Git (chatbot-dev → chatbot-prod)
- [ ] New files: ...
- [ ] Modified files: ...

### Dev-only / revert before prod
- [ ] ...

### Prod runtime (not in git)
- [ ] `.env` keys: ...
- [ ] `config/...` create/copy: ...
- [ ] Bootstrap/migration scripts: ...

### systemd / Nuxt
- [ ] ...

### Smoke tests
- [ ] ...

### Status: [PENDING] | [DONE] YYYY-MM-DD
```

---

## Change log (this document)

| Date | Change |
|------|--------|
| 2026-06-30 | API rate limiting (FastAPI tiers + Nuxt BFF auth/rate middleware) |
| 2026-06-30 | Initial auth + activity logging migration checklist; documented Nuxt → `:8507` dev shortcut |
