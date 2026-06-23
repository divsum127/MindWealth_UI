---
name: api-creation-2
description: >-
  Create MindWealth REST API endpoints for functions in MindWealth core
  (/home/ubuntu/MindWealth) and MindWealth_UI, wire them to the unified FastAPI
  backend on port 8606, write tests, and update the mindwealth-api-docs repo.
  Use when the user asks to add API endpoints, expose a function via REST,
  create a new router/service, or update API documentation.
disable-model-invocation: true
---

# MindWealth API Creation

## Architecture (do not deviate)

| Item | Value |
|------|-------|
| API app | `MindWealth_UI/api/main.py` (single FastAPI process) |
| Port | **8606** (`API_PORT` env, systemd `mindwealth-api.service`) |
| Base URL | `http://localhost:8606/api/v1` (prod: `http://51.20.53.218:8606/api/v1`) |
| Core repo | `/home/ubuntu/MindWealth` |
| UI repo | `/home/ubuntu/uiv2/git/MindWealth_UI` |
| API docs repo (separate git) | `/home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth-api-docs` |
| Docs remote | `https://github.com/divsum127/mindwealth-api-docs.git` |

**Never** start a second API server. All endpoints from both repos register on this one app.

Layer pattern:

```
api/routers/<service>.py   → HTTP routes only
api/services/<service>.py  → business logic, imports MindWealth or UI modules
api/schemas/<service>.py   → Pydantic request/response models (when non-trivial)
```

---

## Workflow checklist

Copy and track progress:

```
API endpoint task:
- [ ] 1. Identify source function + data dependencies
- [ ] 2. Choose service prefix and operationId
- [ ] 3. Implement service layer
- [ ] 4. Implement router + register in api/main.py
- [ ] 5. Add tests (tests/test_api_*.py)
- [ ] 6. Verify locally on :8606
- [ ] 7. Update mindwealth-api-docs (endpoint page, service README, changelog)
- [ ] 8. Export OpenAPI snapshot to docs repo
- [ ] 9. Commit MindWealth_UI code changes (if user asked)
- [ ] 10. Commit mindwealth-api-docs repo (required for every new endpoint)
- [ ] 11. Restart mindwealth-api.service
- [ ] 12. Update global_repo_todos.md
```

---

## Step 1 — Classify the source function

### MindWealth core (`/home/ubuntu/MindWealth`)

Import via `MINDWEALTH_ROOT` — never duplicate logic in the UI repo.

```python
import sys
from functools import lru_cache
from src.config_paths import MINDWEALTH_ROOT

@lru_cache(maxsize=1)
def _import_mindwealth():
    root = str(MINDWEALTH_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return root

# then: from helper_functions.claude_lateness_metrics import enrich_signal_dict
# or:   from virtual_trading import ...
# or:   import cpp_functions  # requires compiled extension in API venv
```

**MindWealth path env vars** (from `src/config_paths.py`):

| Variable | Default |
|----------|---------|
| `MINDWEALTH_ROOT` | `/home/ubuntu/MindWealth` |
| `MINDWEALTH_TRADE_STORE` | `{MINDWEALTH_ROOT}/trade_store/US` |

### MindWealth_UI (`/home/ubuntu/uiv2/git/MindWealth_UI`)

Import directly: `src/`, `macro_intelligence/`, `chatbot/`, `conviction_store/`, etc.

### Prefix guidance

| Source | Suggested prefix | Examples |
|--------|------------------|----------|
| MindWealth signal/trading logic | `/api/v1/signals` or `/api/v1/core` | lateness, virtual trading, breadth |
| MindWealth_UI conviction | `/api/v1/conviction` | existing |
| MindWealth_UI macro/SSI | `/api/v1/macro` | existing |
| MindWealth_UI analytics | `/api/v1/analytics` | existing |

Extend an existing router when the function fits that domain. Create a new router only when no service fits.

---

## Step 2 — Implement router + service

### Router template

```python
"""<Service> REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import optional_api_key
from api.services import <service>_service as svc

router = APIRouter(
    prefix="/<service>",
    tags=["<service>"],
    dependencies=[Depends(optional_api_key)],
)


@router.get("/<path>", operation_id="<unique_camel_case_id>", summary="Short label")
def get_something(
    ticker: str,
    report_date: str | None = Query(default=None, description="YYYY-MM-DD"),
) -> dict[str, Any]:
    try:
        return svc.get_something(ticker=ticker, report_date=report_date)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
```

### Register in `api/main.py`

```python
from api.routers import <service>
app.include_router(<service>.router, prefix=API_PREFIX)
```

Bump `API_VERSION` in `api/main.py` when shipping a meaningful release (minor for new endpoints).

---

## Step 3 — Things to keep in mind

### Auth

- All routes use `dependencies=[Depends(optional_api_key)]`.
- When `API_KEY` env is set, clients must send `X-API-Key`.

### HTTP status codes (follow `docs/mindwealth-api-docs/conventions.md`)

| Situation | Code |
|-----------|------|
| Success | 200 |
| Created | 201 |
| Async job queued | 202 |
| No content (DELETE) | 204 |
| Bad input / unresolved date | 400 |
| Missing API key | 401 |
| Missing ticker/report/file | 404 |
| Pydantic validation | 422 |
| yfinance / upstream failure | 502 |

### Error handling

- Catch domain errors in router or service; return `HTTPException` with clear `detail`.
- Never return raw tracebacks to clients.
- `FileNotFoundError` → 404; `ValueError` → 400; unexpected upstream → 502.

### Data paths

- Resolve paths via `src/config_paths.py`, not hardcoded absolute paths.
- MindWealth reads trade-store CSVs from `TRADE_STORE_US_DIR` (UI repo) or `MINDWEALTH_TRADE_STORE` (core).

### Response shape

- DataFrame endpoints: `{ "records": [...], "row_count": N }` via `api.utils.dataframe_to_records`.
- Convert pandas NaN to `null`.
- Dates: `YYYY-MM-DD`.
- Tickers: uppercase; `/` → `_` in path params.

### Long-running work

| Duration | Pattern |
|----------|---------|
| < 1s read-only | Sync GET in router |
| 10–30s per ticker | Sync POST with timeout warning in docs |
| Minutes / full pipeline | Async job (`api/jobs/`) returning **202** + poll URL, or CLI-only |

Follow chatbot pattern (`api/jobs/runner.py`) for anything that can exceed reverse-proxy timeouts.

### C++ dependencies (`cpp_functions`)

- Verify extension imports in the API venv before shipping.
- If import fails at runtime, document the build step or wrap with clear 502.

### operationId

- Must be unique across the entire app.
- Must match the `operation_id` in the router decorator.
- Must match the `operationId` in docs and OpenAPI snapshot.

### Tests

Add cases to `tests/test_api_<service>.py` or `tests/test_api_integration.py`:

```python
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)
r = client.get("/api/v1/<service>/<path>")
assert r.status_code == 200
```

Run: `cd /home/ubuntu/uiv2/git/MindWealth_UI && python -m pytest tests/test_api_*.py -v`

### Port 8606 alignment

Ensure these agree on **8606**:

- `scripts/mindwealth-api.service` → `API_PORT=8606` and uvicorn `--port 8606`
- `scripts/start_api.sh` → `API_PORT` default (or export before run)
- Docs base URLs in `docs/mindwealth-api-docs/`

---

## Step 4 — Update API documentation

**Docs repo path:** `/home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth-api-docs`

This is a **separate git repository**. Commit docs there in addition to MindWealth_UI code.

### Files to update per new endpoint

1. **Endpoint page** — `services/<service>/endpoints/<verb>-<slug>.md`
   - Use [endpoint-doc-template.md](endpoint-doc-template.md)
2. **Service README** — `services/<service>/README.md` (add row to endpoint table)
3. **Service catalog** — `services/README.md` (update endpoint count if needed)
4. **Changelog** — `changelog.md` (new version section with endpoint table)
5. **Main README** — `README.md` (update version + service index if new service)
6. **OpenAPI snapshot** — `openapi/mindwealth-v1.json`

### Export OpenAPI snapshot

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
export PYTHONPATH="$(pwd)"
python scripts/export_openapi.py
cp docs/api/openapi/mindwealth-v1.json docs/mindwealth-api-docs/openapi/mindwealth-v1.json
```

Use **8606** in curl examples:

```bash
curl -s http://localhost:8606/api/v1/<path> | jq
# prod: http://51.20.53.218:8606/api/v1/<path>
```

### Commit docs repo

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth-api-docs

git status
git add services/<service>/endpoints/<new-endpoint>.md
git add services/<service>/README.md
git add services/README.md changelog.md README.md openapi/mindwealth-v1.json

git commit -m "$(cat <<'EOF'
docs: add GET /api/v1/<service>/<path> (vX.Y.Z)

Document <brief purpose>. Regenerate OpenAPI snapshot.
EOF
)"

git push origin main
```

Only push when the user requests it. Always commit locally as part of the endpoint workflow.

---

## Step 5 — Deploy

```bash
# Restart API (after code changes in MindWealth_UI)
sudo systemctl restart mindwealth-api.service
sudo systemctl status mindwealth-api.service

# Smoke test
curl -s http://localhost:8606/api/v1/health | jq
curl -s http://localhost:8606/api/v1/<new-path> | jq
```

Live Swagger: `http://localhost:8606/docs`

---

## Anti-patterns

| Do not | Do instead |
|--------|------------|
| New uvicorn app in MindWealth core | Register router on `api/main.py` |
| Copy MindWealth function into UI repo | Import via `MINDWEALTH_ROOT` |
| Skip docs repo commit | Always commit `mindwealth-api-docs` |
| Hardcode `/home/ubuntu/...` in services | Use `src/config_paths.py` |
| Blocking HTTP for multi-minute jobs | Async job pattern or CLI |
| Duplicate `operationId` | Grep `operation_id=` across `api/routers/` |

---

## Reference files

| Purpose | Path |
|---------|------|
| App entry | `api/main.py` |
| Auth dependency | `api/dependencies.py` |
| Conventions | `docs/mindwealth-api-docs/conventions.md` |
| Example router | `api/routers/signals.py` |
| Example service | `api/services/reports_service.py` |
| MindWealth import pattern | `src/utils/signal_quality.py` |
| Macro service (complex) | `api/services/macro_service.py` |
| Endpoint doc template | `.cursor/skills/api-creation-2/endpoint-doc-template.md` |
| systemd unit | `scripts/mindwealth-api.service` |
