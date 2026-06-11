# Monitored Trades API

**Status:** implemented (v1.2.0)

**Router:** `api/routers/monitored_trades.py`

**Source:** `src/utils/monitored_trades.py` → `monitored_trades.json`

## Endpoints

| Method | Path | Doc |
|--------|------|-----|
| GET | `/monitored-trades` | [list-trades.md](endpoints/list-trades.md) |
| POST | `/monitored-trades` | [create-trade.md](endpoints/create-trade.md) |
| DELETE | `/monitored-trades/{trade_id}` | [delete-trade.md](endpoints/delete-trade.md) |

All paths are prefixed with `/api/v1`.

## Errors

| Status | Cause |
|--------|-------|
| 409 | Trade already exists or save failed (POST) |
| 404 | Trade ID not found (DELETE) |
