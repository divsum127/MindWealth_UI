# API Conventions

## Versioning

All routes are prefixed with `/api/v1`. Breaking changes will increment the major version.

## Ticker symbols

- Path parameter `{ticker}` is sanitized to uppercase; `/` becomes `_` (e.g. `BRK-B`, `CAD=X`).
- Must match filenames in `conviction_store/{TICKER}.json`.

## Dates

- Report dates use `YYYY-MM-DD` (ISO 8601 date).
- Overlay archives live under `conviction_store/daily/{date}/`.

## Pagination

List endpoints support:

| Query | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | none | Max rows (where supported) |
| `offset` | int | 0 | Skip first N rows |

## Response format

- JSON bodies use `camelCase` field names only where Pydantic models define them; conviction records mirror the JSON store (mostly `snake_case`).
- DataFrame-backed endpoints return `{ "records": [...], "row_count": N }`.
- `null` for missing numeric fields (NaN from pandas is converted).

## HTTP status codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (e.g. pipeline could not resolve report date) |
| 401 | Missing or invalid `X-API-Key` when `API_KEY` is configured |
| 404 | Ticker, overlay date, or signal file not found |
| 422 | Validation error (invalid body or query) |
| 502 | Upstream failure (e.g. yfinance timeout during recalculate) |

## Error body

FastAPI standard:

```json
{
  "detail": "Human-readable message"
}
```

Validation errors include a `detail` array with `loc` and `msg` per field.

## Long-running operations

| Endpoint | Typical duration | Notes |
|----------|------------------|-------|
| `POST .../recalculate` | 10–30s per ticker | yfinance fetch |
| `POST .../pipeline/daily` | minutes | Full universe; may timeout behind reverse proxies |

Run pipeline via CLI (`scripts/run_conviction_engine_daily.py`) for production batch jobs if HTTP timeouts are an issue.
