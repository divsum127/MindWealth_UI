# API Changelog

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
