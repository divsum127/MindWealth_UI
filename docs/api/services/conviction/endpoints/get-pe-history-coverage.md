# GET /api/v1/conviction/coverage/pe-history

## Summary

P/E history span distribution across conviction store.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/conviction/coverage/pe-history`
- **operationId:** `get_pe_history_coverage`
- **Status:** implemented

## Maps to

`data_coverage.summarize_pe_history_distribution()`

## Request

None

## Response

200: coverage statistics object

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/conviction/coverage/pe-history | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
