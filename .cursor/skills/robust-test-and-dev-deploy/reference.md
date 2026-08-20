# Robust test and dev deploy — reference

## Dev vs prod quick reference

### Dev repos (edit, commit, push here)

| Repo | Path | **Branch** | Service | Port |
|------|------|------------|---------|------|
| MindWealth_UI | `/home/ubuntu/uiv2/git/MindWealth_UI` | **`chatbot-dev`** | `mindwealth-api-dev.service` | `:8507` |
| MindwealthUI_Vue | `/home/ubuntu/MindwealthUI_Vue` | **`ui-dev`** | `mindwealth-ui-dev` | `:8514` |

### Prod (read-only for agents; pull/deploy only)

| Repo | Path | Branch | Service | Port |
|------|------|--------|---------|------|
| MindWealth_UI | `/home/ubuntu/uiv2/prod/MindWealth_UI` | `chatbot-prod` | `mindwealth-api.service` | `:8506` |
| MindwealthUI_Vue | prod host | cutover from `ui-dev` | prod Nuxt | `:8512` |

**Rule:** `git push origin chatbot-dev` and `git push origin ui-dev` after dev smoke passes. Never commit in `/home/ubuntu/uiv2/prod/`.

## API test files by domain

| File | Domain |
|------|--------|
| `tests/test_api_conviction.py` | Conviction engine |
| `tests/test_api_signals_surface.py` | Signals |
| `tests/test_api_portfolio.py` | Portfolio |
| `tests/test_api_macro.py` | Macro / SSI |
| `tests/test_api_analyst.py` | Analyst |
| `tests/test_api_chatbot.py` | Chatbot |
| `tests/test_api_auth.py` | Auth |
| `tests/test_api_meta.py` | Meta / health |
| `tests/test_api_integration.py` | Cross-service |

## Common targeted test commands

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI

# Conviction
.venv/bin/python -m pytest tests/test_conviction_engine.py tests/test_api_conviction.py -q

# Signals
.venv/bin/python -m pytest tests/test_api_signals_surface.py -q

# Portfolio
.venv/bin/python -m pytest tests/test_api_portfolio.py tests/test_portfolio_backend_engines.py -q

# Macro / SSI
.venv/bin/python -m pytest tests/test_api_macro.py tests/test_ssi_superindex.py -q
```

## Mock audit — allow vs reject

| Location | Mock usage | Verdict |
|----------|------------|---------|
| `tests/**` | `unittest.mock`, fixtures | OK |
| `api/`, `src/`, `scripts/` | mock data returned as live | Reject unless user specified |
| Nuxt `mock-data.ts` | UI dev placeholders | Flag if backend still missing equivalent |
| Comments "no mock data" | documentation | Verify still true |

## dev_to_prod_migration_todos entry template

```markdown
## YYYY-MM-DD — <short title>

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`

```bash
# [PROD-ACTION] one-time commands on prod host
cd /home/ubuntu/uiv2/prod/MindWealth_UI
.venv/bin/python scripts/<script>.py --apply
```

| Path | Notes |
|------|-------|
| `src/...` | **modified** — <what changed> |
| `tests/...` | **new** — N tests |

**Dev-only `[DEV-ONLY]`:** <what to revert for prod>

**Edge cases:**
- <cache invalidation, historical data shift, ticker-specific behavior>

**Smoke test `[PENDING]`:** <specific curl checks + expected fields>
```

## Endpoint spot-check curls (dev)

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
DEV=http://127.0.0.1:8507
KEY=$(grep -E '^API_KEY=' .env | cut -d= -f2-)
H=(-H "X-API-Key: $KEY")

curl -sf "${H[@]}" "$DEV/api/v1/health" | python3 -m json.tool
curl -sf "${H[@]}" "$DEV/api/v1/signals/counts" | python3 -m json.tool | head
curl -sf "${H[@]}" "$DEV/api/v1/conviction/tickers/AAPL" | python3 -m json.tool | head -40
```

Adjust tickers/paths to match the change under test.

## Do not

- Commit or push from `/home/ubuntu/uiv2/prod/` or to `chatbot-prod` without explicit prod release
- Commit on wrong branch (`main`, `chatbot-prod`, etc.) — always verify `chatbot-dev` / `ui-dev` first
- Commit `trade_store/`, `conviction_store/`, `.env`, `secrets.toml`, `runic.db`, runtime CSVs
- Edit or deploy from prod clone during dev verification
- Skip OpenAPI export when endpoint contracts changed
- Mark migration smoke `[DONE]` without live verification on dev
- Push UI changes only to MindWealth_UI — Nuxt lives in **MindwealthUI_Vue** on **`ui-dev`**
