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

200: `{ source_file, row_count, summary, records }`; 404 if CSV missing

When the CSV is empty (e.g. `claude_signals_report.csv` is a 1-byte placeholder), the response also includes:

- `csv_empty: true`
- `shortlist` — markdown + metadata from `GET /signals/shortlist` (`.txt` fallback)

## Example

```bash
curl -s -X POST http://51.20.53.218:8506/api/v1/conviction/signals/overlay-file \
  -H "Content-Type: application/json" \
  -d '{"report_name":"new_signal.csv"}' | jq

curl -s -X POST http://51.20.53.218:8506/api/v1/conviction/signals/overlay-file \
  -H "Content-Type: application/json" \
  -d '{"report_name":"claude_signals_report.csv","save_output":false}' | jq '.shortlist.markdown | length'
```

## Notes

See [Conviction Engine overview](../README.md), [Signals shortlist](../../signals/README.md), and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
