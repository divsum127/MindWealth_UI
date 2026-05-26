# GET /api/v1/conviction/overlays/dates

## Summary

Sorted list of YYYY-MM-DD dates with archived daily overlays.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/conviction/overlays/dates`
- **operationId:** `list_overlay_dates`
- **Status:** implemented

## Maps to

`store.list_daily_snapshot_dates()`

## Request

None

## Response

200: string array of dates

## Example

```bash
curl -s http://localhost:8000/api/v1/conviction/overlays/dates | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
