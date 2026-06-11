# POST /api/v1/conviction/pipeline/daily

## Summary

Batch: refresh fundamentals + overlay signal CSVs + archive.

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/conviction/pipeline/daily`
- **operationId:** `run_daily_pipeline`
- **Status:** implemented

## Maps to

`daily_run.run_daily_conviction_pipeline()`

## Request

Body: report_date, fundamentals_mode, skip_fundamentals, skip_overlays, dry_run, overlay_reports

## Response

200: manifest; 400 on error status; 502 on exception

## Example

```bash
curl -s -X POST http://51.20.53.218:8506/api/v1/conviction/pipeline/daily -H "Content-Type: application/json" -d '{"dry_run":true}' | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
