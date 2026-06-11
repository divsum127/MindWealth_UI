# GET /api/v1/conviction/tickers/{ticker}

## Summary

Full JSON fundamental record for one ticker.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/conviction/tickers/{ticker}`
- **operationId:** `get_ticker`
- **Status:** implemented

## Maps to

`store.load_record()`

## Request

Path: ticker

## Response

200: record object; 404 if missing

### v6 fields (when populated)

`bq_components` (15 keys), `fd_votes`, `fd_direction`, `fd_sizing_adj`, `valuation_tax_breakdown`, `debt_purpose`, `revenue_accelerating`, `yield_trap_mkt_threshold`, `pe_history_insufficient`, `macro_tailwind_detail` (agent), `position_layers`

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/conviction/tickers/AAPL | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
