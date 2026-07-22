# API Changelog

## v1.8.2 (2026-07-22)

### Added — Portfolio page HANDOFF endpoints

- `GET /portfolio/nav` — overview snapshot (MODEL enhanced; NAV history pending Ahil A1)
- `GET /portfolio/holdings` — holdings merged with sizer allocations
- `GET /portfolio/sizing` — alias for `/portfolio/sizer`
- `GET /signals/entries`, `GET /signals/exits` — Portfolio admission/exit pipelines
- `GET /signals/reports/portfolio-risk/latest` — cross-function conflict report (HANDOFF §11)
- Services: `portfolio_book.py`, `portfolio_pipeline_service.py`
- Extended: `portfolio_service.py` (D2 base size, `conviction_summary`), `signal_enrichment_service.py` (`rr_dynamic`)

## v1.8.1 (2026-07-20)

### Overwatch panel completeness

- `GET /analytics/analyst/context` — cross-page bundle (alerts, tab badges, regime, sentiment, chat)
- Extended `GET /analytics/analyst/alerts` — channel filter, regime/sentiment/persistence/watch warnings, `include_system`
- Chat `page_context` on `POST /chatbot/sessions/{id}/messages`

## v1.8.0 (2026-07-20)

### Added — AI Analyst / Overwatch

- `GET /analytics/analyst/alerts` — unified Overwatch panel alerts (degradation + runic)
- `GET /analytics/analyst/brief` — dashboard analyst snippet
- `GET /overwatch/stream` — SSE push for auto-triggered alerts
- `GET /system/health` — admin-only pipeline/integration checks
- Services: `analyst_service`, `system_health_service`, `overwatch_event_bus`, `analyst_copy_service`, `integration_health_store`
- Degradation parquet + result cache (`overwatch_store/`) — cached reads &lt;1s
- Optional Claude alert copy: `ANALYST_USE_CLAUDE_COPY=true`
- Cron: `scripts/overwatch/run_overwatch_signals.py` pre-warms cache
- Docs: `docs/api/services/analyst/`

### Changed

- `POST /signals/check-degradation` — spec-aligned 60% watch/breach tiers + weekly trend; disk cache
- System health Tavily/Sheets use integration markers from chatbot + conviction daily

### Notes

- SSE requires single uvicorn worker (in-process event bus).
- See `docs/dev_to_prod_migration_todos.md` for prod deploy checklist.

## v1.5.0 (2026-07-03)

### Added

- **Macro scheduled events** (3 new endpoints; existing macro routes unchanged):
  - `GET /macro/events/pre-catalyst` — pre-catalyst fragility before CPI/FOMC/NFP
  - `GET /macro/events/post-regime` — post-event regime transition (48h window)
  - `GET /macro/events/calendar?days=21` — upcoming CPI, FOMC, NFP dates
- Frontend integration guide: `docs/api/frontend/macro-scheduled-events-integration.md`
- Endpoint docs under `docs/api/services/macro/endpoints/`

### Notes

- `GET /macro/regime` response shape unchanged (no new keys).
- Full nightly JSON (`GET /macro/runic/nightly`) includes `pre_catalyst` and `post_event_regime` blocks from the nightly pipeline.

## v1.2.0 (2026-06-06)

### Added

- **Signals** router: `/signals/reports`, `/reports/{name}/latest`, `/reports/{name}/{date}`, `/signals/shortlist`
- **Monitored trades** router: `GET/POST/DELETE /monitored-trades`
- **Virtual trading** router: `/virtual-trading/long`, `/short`, `/portfolio`
- **Analytics** router: `/analytics/sigma`, `/sentiment`, `/sentiment/layers`, `/performance`, `/portfolio-ytd`
- **Macro / Runic** router: `/macro/runic/nightly`, `/runic/variables/current`, `/combo/active`, `/sentiment/positioning`
- Shared report loader: `api/services/reports_service.py`
- Integration tests: `tests/test_api_integration.py`

### Fixed

- Empty `claude_signals_report.csv` (1-byte file): overlay returns `shortlist` fallback; shortlist endpoint reads `.txt` markdown
- Conviction score-sheet: includes MTM / today price / holding period columns when present in overlay data
- Empty CSV load no longer raises parse errors (`load_signal_file`)

### Documentation

- Service docs with per-endpoint pages: signals, monitored-trades, virtual-trading, analytics, macro
- OpenAPI snapshot updated (`docs/api/openapi/mindwealth-v1.json`) — 55 operations

## v1.1.2 (2026-06-05)

### Changed

- API docs base URL updated to hosted server `http://51.20.53.218:8506` (Swagger, ReDoc, OpenAPI, and endpoint examples)

## v1.1.1 (2026-05-26)

### Added

- systemd service `mindwealth-api.service` on port **8506** (`scripts/setup-mindwealth-api-systemd.sh`)
- API docs base URL updated to `http://localhost:8506` (local dev default)

## v1.1.0 (2026-05-26)

### Changed (Conviction Engine v6)

- Scoring aligned with v6 Internal spec: `valuation_tax_breakdown`, 5-vote `fd_votes`, `fd_sizing_adj`, `debt_purpose`, yield trap at market threshold uses `>=`.
- Optional Claude agent dimensions on full recalc when `CONVICTION_RUN_AGENT_DIMS=1` and `ANTHROPIC_API_KEY` is set.

### Added

- Chatbot router under `/api/v1/chatbot`
- Session CRUD, history, finalize (memory extract)
- Async jobs: `POST .../messages` (202), `GET .../jobs/{id}` with `flow_steps`
- Preset launches: `/analyze-asset`, `/signal-insights`, `/breadth-analysis`
- Discovery: config, signal-types, tickers, functions, memory stats
- Flag exchange for debugging
- Documentation: `docs/api/services/chatbot/` + `async-jobs.md`
- Tests: `tests/test_api_chatbot.py`

## v1.0.0 (2026-05-26)

### Added

- FastAPI application (`api/main.py`)
- Health endpoint `GET /api/v1/health`
- Conviction Engine routes under `/api/v1/conviction`
- Structured documentation in `docs/api/`
- OpenAPI snapshot export script `scripts/export_openapi.py`
- API tests in `tests/test_api_conviction.py`

### Planned at v1.0.0 (since implemented in v1.1+ / v1.2.0)

- Chatbot (v1.1.0), Signals, Monitored Trades, Virtual Trading, Analytics, Macro (v1.2.0)
