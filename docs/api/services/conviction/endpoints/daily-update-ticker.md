# PATCH /api/v1/conviction/tickers/{ticker}/daily

## Summary

Price-sensitive daily refresh only.

## HTTP

- **Method:** `PATCH`
- **Path:** `/api/v1/conviction/tickers/{ticker}/daily`
- **operationId:** `daily_update_ticker`
- **Status:** implemented

## Maps to

`engine.daily_update()`

## Request

Path: ticker

## Response

200: updated record; 502 on failure

## Example

```bash
curl -s -X PATCH http://51.20.53.218:8506/api/v1/conviction/tickers/AAPL/daily | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
