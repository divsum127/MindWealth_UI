# GET /api/v1/conviction/tickers

## Summary

List conviction ticker records from conviction_store.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/conviction/tickers`
- **operationId:** `list_tickers`
- **Status:** implemented

## Maps to

`store.list_records()`

## Request

Query: fs_class, yield_trap, limit, offset, fields (summary|full)

## Response

200: array of ticker summary or full records

## Example

```bash
curl -s "http://51.20.53.218:8506/api/v1/conviction/tickers?limit=10" | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
