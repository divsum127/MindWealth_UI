# API Changelog

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

### Planned (not yet implemented)

- Chatbot, Signals, Monitored Trades, Virtual Trading, Analytics routers
