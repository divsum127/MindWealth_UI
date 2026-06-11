# GET /api/v1/conviction/universe

## Summary

Discovered ticker universe from signals + store.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/conviction/universe`
- **operationId:** `get_universe`
- **Status:** implemented

## Maps to

`fundamentals.discover_universe()`

## Request

None

## Response

200: array of ticker strings

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/conviction/universe | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
