# PATCH /api/v1/conviction/tickers/{ticker}/overrides

## Summary

Apply manual BQ/FD/business_type overrides.

## HTTP

- **Method:** `PATCH`
- **Path:** `/api/v1/conviction/tickers/{ticker}/overrides`
- **operationId:** `update_ticker_overrides`
- **Status:** implemented

## Maps to

`engine.update_overrides()`

## Request

Body: {"overrides": {"bq_raw": 7}, "recompute": true}

## Response

200: updated record

## Example

```bash
curl -s -X PATCH http://51.20.53.218:8506/api/v1/conviction/tickers/AAPL/overrides -H "Content-Type: application/json" -d '{"overrides":{"bq_raw":7}}' | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
