# MindWealth API Documentation

**Current version:** 1.2.0

REST API for MindWealth trading analysis services. The Streamlit UI (`app.py`) remains the primary interface; this API exposes the same domain logic for automation and future clients.

## Base URL

```
http://51.20.53.218:8506/api/v1
```

For local development on the host, use `http://localhost:8506/api/v1` instead.

Configure port via `API_PORT` (default `8506`). The production **systemd** service (`mindwealth-api.service`) binds to `0.0.0.0:8506`.

## Interactive documentation

| Tool | URL |
|------|-----|
| Swagger UI | http://51.20.53.218:8506/docs |
| ReDoc | http://51.20.53.218:8506/redoc |
| OpenAPI JSON (live) | http://51.20.53.218:8506/openapi.json |
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
| Signals / Reports | Implemented | `/api/v1/signals` | [services/signals/](services/signals/) |
| Monitored Trades | Implemented | `/api/v1/monitored-trades` | [services/monitored-trades/](services/monitored-trades/) |
| Virtual Trading | Implemented | `/api/v1/virtual-trading` | [services/virtual-trading/](services/virtual-trading/) |
| Analytics | Implemented | `/api/v1/analytics` | [services/analytics/](services/analytics/) |
| Macro / Runic | Implemented | `/api/v1/macro` | [services/macro/](services/macro/) |

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
| `macro_intelligence/output/` | Runic nightly JSON, SSI positioning |
| `monitored_trades.json` | User-monitored trade list |

Paths resolve via `src/config_paths.py` (overridable with env vars).

## Changelog

See [changelog.md](changelog.md).
