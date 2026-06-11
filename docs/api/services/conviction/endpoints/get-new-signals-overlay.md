# GET /api/v1/conviction/overlays/{report_date}/new-signals

## Summary

Archived New Signals full overlay CSV as JSON records.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/conviction/overlays/{report_date}/new-signals`
- **operationId:** `get_new_signals_overlay`
- **Status:** implemented

## Maps to

`store.load_daily_new_signal_overlay()`

## Request

Path: report_date (YYYY-MM-DD)

## Response

200: {report_date, overlay_file, row_count, records}; 404 if missing

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/conviction/overlays/2026-05-20/new-signals | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
