# POST /api/v1/conviction/signals/overlay-file

## Summary

Overlay conviction columns onto a trade-store signal CSV.

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/conviction/signals/overlay-file`
- **operationId:** `overlay_signal_file`
- **Status:** implemented

## Maps to

`engine.apply_to_signal_file()`

## Request

Body: report_date, report_name (default new_signal.csv), save_output, update_layers

## Response

200: records + summary; 404 if CSV missing

## Example

```bash
curl -s -X POST http://localhost:8000/api/v1/conviction/signals/overlay-file -H "Content-Type: application/json" -d '{"report_name":"new_signal.csv"}' | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
