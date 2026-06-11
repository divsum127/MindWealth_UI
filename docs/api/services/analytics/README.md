# Analytics API

**Status:** implemented (v1.2.0)

**Router:** `api/routers/analytics.py`

**Source:** Latest trade-store CSVs, virtual trading long CSV, SSI positioning JSON

## Endpoints

| Method | Path | Doc |
|--------|------|-----|
| GET | `/analytics/sigma` | [get-sigma.md](endpoints/get-sigma.md) |
| GET | `/analytics/sentiment` | [get-sentiment.md](endpoints/get-sentiment.md) |
| GET | `/analytics/sentiment/layers` | [get-sentiment-layers.md](endpoints/get-sentiment-layers.md) |
| GET | `/analytics/performance` | [get-performance.md](endpoints/get-performance.md) |
| GET | `/analytics/portfolio-ytd` | [get-portfolio-ytd.md](endpoints/get-portfolio-ytd.md) |

All paths are prefixed with `/api/v1`.

## Frontend mapping (Alpha Terminal)

| UI area | Endpoint |
|---------|----------|
| Dashboard sigma KPI | `/analytics/sigma` |
| PULSEGAUGE rows | `/analytics/sentiment` |
| SSI layers | `/analytics/sentiment/layers` |
| Performance table | `/analytics/performance` |
| Overwatch YTD | `/analytics/portfolio-ytd` |
