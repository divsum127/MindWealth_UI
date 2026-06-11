# Virtual Trading API

**Status:** implemented (v1.2.0)

**Router:** `api/routers/virtual_trading.py`

**Source:** `trade_store/US/virtual_trading_long.csv`, `virtual_trading_short.csv`

## Endpoints

| Method | Path | Doc |
|--------|------|-----|
| GET | `/virtual-trading/long` | [get-long.md](endpoints/get-long.md) |
| GET | `/virtual-trading/short` | [get-short.md](endpoints/get-short.md) |
| GET | `/virtual-trading/portfolio` | [get-portfolio.md](endpoints/get-portfolio.md) |

All paths are prefixed with `/api/v1`.

## Related

- YTD P&L: [get-portfolio-ytd.md](../analytics/endpoints/get-portfolio-ytd.md)
