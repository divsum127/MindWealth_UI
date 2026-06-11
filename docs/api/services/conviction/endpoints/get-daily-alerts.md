# GET /api/v1/conviction/alerts/daily

## Summary

Fundamental alert map and daily report text for current store.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/conviction/alerts/daily`
- **operationId:** `get_daily_alerts`
- **Status:** implemented

## Maps to

`engine.run_daily_universe() + generate_daily_report()`

## Request

None

## Response

200: {alerts, report, universe_size}

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/conviction/alerts/daily | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
