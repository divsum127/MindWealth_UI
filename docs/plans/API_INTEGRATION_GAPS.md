# API Integration Gaps

Base URL in use: `http://51.20.53.218:8506` (prefix `/api/v1`).

This document tracks MindWealth API coverage for the Nuxt Alpha Terminal frontend.

**Last updated:** v1.2.0 — added signals, monitored-trades, virtual-trading, analytics, and macro routers; fixed claude shortlist overlay and score-sheet MTM columns.

---

## 1. Implemented backend services (v1.2.0)

| Service | Prefix | Status |
|---------|--------|--------|
| Health | `/api/v1/health` | Implemented |
| Conviction Engine | `/api/v1/conviction` | Implemented |
| Chatbot | `/api/v1/chatbot` | Implemented (async jobs) |
| Signals / Reports | `/api/v1/signals` | **Implemented** |
| Monitored Trades | `/api/v1/monitored-trades` | **Implemented** |
| Virtual Trading | `/api/v1/virtual-trading` | **Implemented** |
| Analytics | `/api/v1/analytics` | **Implemented** |
| Macro / Runic | `/api/v1/macro` | **Implemented** |

### New endpoints (v1.2.0)

**Signals** — [`docs/api/services/signals/`](services/signals/)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/signals/reports` | Catalog of trade-store reports |
| GET | `/signals/reports/{name}/latest` | Latest CSV as JSON records |
| GET | `/signals/reports/{name}/{date}` | Dated report |
| GET | `/signals/shortlist` | Claude markdown + CSV (txt fallback when CSV empty) |

**Monitored trades**

| Method | Path |
|--------|------|
| GET | `/monitored-trades` |
| POST | `/monitored-trades` |
| DELETE | `/monitored-trades/{trade_id}` |

**Virtual trading / portfolio**

| Method | Path |
|--------|------|
| GET | `/virtual-trading/long` |
| GET | `/virtual-trading/short` |
| GET | `/virtual-trading/portfolio` |

**Analytics**

| Method | Path | Frontend gap addressed |
|--------|------|------------------------|
| GET | `/analytics/sigma` | Dashboard sigma KPI |
| GET | `/analytics/sentiment` | PULSEGAUGE signal rows |
| GET | `/analytics/sentiment/layers` | SSI positioning + layer inputs |
| GET | `/analytics/performance` | Combined performance report |
| GET | `/analytics/portfolio-ytd` | Overwatch `forced_portfolio_ytd` |

**Macro / Runic**

| Method | Path |
|--------|------|
| GET | `/macro/runic/nightly` |
| GET | `/macro/runic/variables/current` |
| GET | `/macro/combo/active` |
| GET | `/macro/sentiment/positioning` |

### Bug fixes (v1.2.0)

| Issue | Fix |
|-------|-----|
| `claude_signals_report.csv` overlay fails (empty 1-byte CSV) | Empty CSV handled; overlay returns `shortlist` with `.txt` markdown; `GET /signals/shortlist` |
| Conviction score-sheet missing MTM | Score sheet includes MTM / today price / holding period columns when present |
| `dry_run` pipeline hung on yfinance | Fixed in v1.1.1 (`fundamentals.py`) |

---

## 2. Frontend wiring still pending (Nuxt Nitro)

These backend endpoints exist but **Nuxt `/api/*` proxies** may still use mocks until updated:

| UI area | Backend endpoint to wire |
|---------|--------------------------|
| Portfolio | `GET /virtual-trading/portfolio`, `/long`, `/short` |
| Monitored trades | `GET/POST/DELETE /monitored-trades` |
| Runic macro | `GET /macro/runic/nightly`, `/combo/active`, `/runic/variables/current` |
| Sentiment layers | `GET /analytics/sentiment/layers` |
| Dashboard sigma | `GET /analytics/sigma` |
| Shortlist report | `GET /signals/shortlist` |
| Overwatch YTD | `GET /analytics/portfolio-ytd` |
| Conviction MTM cards | `GET /conviction/overlays/{date}/score-sheet` (now includes MTM) |

---

## 3. Conviction / chatbot endpoints optional for UI

Admin and debug routes remain available but are not required for Alpha Terminal v1:

- Conviction: recalculate, daily patch, overrides, evaluate, pipeline
- Chatbot: session rename/delete, finalize, convenience presets, flag, memory stats

---

## 4. Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NUXT_API_BASE_URL` | `http://51.20.53.218:8506` | MindWealth API host (no `/api/v1` suffix) |
| `NUXT_API_KEY` | empty | Optional `X-API-Key` header |
| `API_KEY` | empty | Server-side auth when set |

---

## 5. Documentation

Full API docs: [`docs/api/README.md`](README.md)
