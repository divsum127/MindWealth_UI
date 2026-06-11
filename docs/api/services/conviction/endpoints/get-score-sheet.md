# GET /api/v1/conviction/overlays/{report_date}/score-sheet

## Summary

Compact conviction score sheet for a report date.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/conviction/overlays/{report_date}/score-sheet`
- **operationId:** `get_score_sheet`
- **Status:** implemented

## Maps to

`daily_run.conviction_score_sheet()`

## Request

Path: report_date

## Response

200: `{ report_date, row_count, records }`

Each record includes conviction columns plus MTM fields when available in the overlay:

- `mtm_pct` — mark-to-market percentage
- `today_price` — latest price used for MTM
- `holding_period_days` — days since signal entry

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/conviction/overlays/2026-05-20/score-sheet | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
