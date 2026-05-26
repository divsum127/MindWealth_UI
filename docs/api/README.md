# MindWealth API Documentation

REST API for MindWealth trading analysis services. The Streamlit UI (`app.py`) remains the primary interface; this API exposes the same domain logic for automation and future clients.

## Base URL

```
http://localhost:8000/api/v1
```

Configure port via `API_PORT` (default `8000`).

## Interactive documentation

| Tool | URL |
|------|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| OpenAPI JSON (live) | http://localhost:8000/openapi.json |
| OpenAPI snapshot (repo) | [openapi/mindwealth-v1.json](openapi/mindwealth-v1.json) |

## Authentication

Optional. When `API_KEY` is set in the environment, every request must include:

```
X-API-Key: <your-api-key>
```

## Service index

| Service | Status | Prefix | Documentation |
|---------|--------|--------|---------------|
| Health | Implemented | `/api/v1/health` | [services/health/](services/health/) |
| Conviction Engine | Implemented | `/api/v1/conviction` | [services/conviction/](services/conviction/) |
| Chatbot | Implemented | `/api/v1/chatbot` | [services/chatbot/](services/chatbot/) |
| Signals / Reports | Planned | `/api/v1/signals` | [services/signals/](services/signals/) |
| Monitored Trades | Planned | `/api/v1/monitored-trades` | [services/monitored-trades/](services/monitored-trades/) |
| Virtual Trading | Planned | `/api/v1/virtual-trading` | [services/virtual-trading/](services/virtual-trading/) |
| Analytics | Planned | `/api/v1/analytics` | [services/analytics/](services/analytics/) |

## Getting started

See [getting-started.md](getting-started.md).

## Conventions

See [conventions.md](conventions.md) for errors, pagination, dates, and ticker formats.

## Data dependencies

| Path | Purpose |
|------|---------|
| `conviction_store/` | Per-ticker JSON fundamentals |
| `conviction_store/daily/` | Archived daily overlays |
| `trade_store/US/` | Signal CSV reports |

Paths resolve via `src/config_paths.py` (overridable with env vars).

## Changelog

See [changelog.md](changelog.md).
