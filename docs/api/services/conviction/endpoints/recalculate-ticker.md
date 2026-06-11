# POST /api/v1/conviction/tickers/{ticker}/recalculate

## Summary

Full fundamentals refresh via yfinance (slow).

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/conviction/tickers/{ticker}/recalculate`
- **operationId:** `recalculate_ticker`
- **Status:** implemented

## Maps to

`engine.full_recalculation()`

## Request

Path: ticker

## Response

200: updated record; 502 on yfinance failure

## Example

```bash
curl -s -X POST http://51.20.53.218:8506/api/v1/conviction/tickers/AAPL/recalculate | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
