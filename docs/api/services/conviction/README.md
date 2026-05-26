# Conviction Engine API

Fundamental overlay on quant trade signals (v6 Internal). Scores individual equities using business quality (BQ, 15 stored sub-components), valuation tax breakdown, five-vote fundamental direction (FD), financial strength (FS), and yield-trap gates; produces verdicts and sizing for BUY/SELL rows.

## Domain documentation

- [Conviction Engine fundamentals](../../../documentation/conviction_engine_fundamentals.md)
- Python package: `src/conviction_engine/`

## Verdict tiers (BUY, post-FS-cap score)

| Score | Verdict | Sizing |
|-------|---------|--------|
| Yield trap | CANCEL BUY | 0% |
| ≥ 8 | MAX CONVICTION | 100% |
| ≥ 5 | TACTICAL BUY | 60–85% |
| ≥ 2 | REDUCED BUY | 25–50% |
| < 2 | CANCEL BUY | 0% |

ETFs, indices, FX, and crypto return `NOT_APPLICABLE`.

## Endpoints

### Tickers

| Method | Path | Doc |
|--------|------|-----|
| GET | `/conviction/tickers` | [list-tickers.md](endpoints/list-tickers.md) |
| GET | `/conviction/tickers/{ticker}` | [get-ticker.md](endpoints/get-ticker.md) |
| POST | `/conviction/tickers/{ticker}/recalculate` | [recalculate-ticker.md](endpoints/recalculate-ticker.md) |
| PATCH | `/conviction/tickers/{ticker}/daily` | [daily-update-ticker.md](endpoints/daily-update-ticker.md) |
| PATCH | `/conviction/tickers/{ticker}/overrides` | [update-overrides.md](endpoints/update-overrides.md) |

### Signals

| Method | Path | Doc |
|--------|------|-----|
| POST | `/conviction/signals/evaluate` | [evaluate-signal.md](endpoints/evaluate-signal.md) |
| POST | `/conviction/signals/overlay-file` | [overlay-signal-file.md](endpoints/overlay-signal-file.md) |

### Overlays

| Method | Path | Doc |
|--------|------|-----|
| GET | `/conviction/overlays/dates` | [list-overlay-dates.md](endpoints/list-overlay-dates.md) |
| GET | `/conviction/overlays/{date}/new-signals` | [get-new-signals-overlay.md](endpoints/get-new-signals-overlay.md) |
| GET | `/conviction/overlays/{date}/summary` | [get-overlay-summary.md](endpoints/get-overlay-summary.md) |
| GET | `/conviction/overlays/{date}/score-sheet` | [get-score-sheet.md](endpoints/get-score-sheet.md) |

### Universe & pipeline

| Method | Path | Doc |
|--------|------|-----|
| GET | `/conviction/universe` | [get-universe.md](endpoints/get-universe.md) |
| GET | `/conviction/coverage/pe-history` | [get-pe-history-coverage.md](endpoints/get-pe-history-coverage.md) |
| POST | `/conviction/pipeline/daily` | [run-daily-pipeline.md](endpoints/run-daily-pipeline.md) |
| GET | `/conviction/alerts/daily` | [get-daily-alerts.md](endpoints/get-daily-alerts.md) |

All paths are prefixed with `/api/v1`.
