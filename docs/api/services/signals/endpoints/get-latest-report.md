# GET /api/v1/signals/reports/{report_name}/latest

## Summary

Latest dated CSV for a report slug as JSON records.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/signals/reports/{report_name}/latest`
- **operationId:** `get_latest_signal_report`
- **Status:** implemented
- **Typical status:** 200, 404

## Maps to

`reports_service.load_report_records(report_name)`

## Request

Path: `report_name` — slug or base filename (e.g. `new-signals`, `sigma`)

## Response

200:

```json
{
  "report_name": "new-signals",
  "source_file": "/path/to/file.csv",
  "report_date": "2026-05-20",
  "format": "csv",
  "row_count": 42,
  "records": []
}
```

Claude shortlist with empty CSV returns `format: "markdown"` and `content` instead of records.

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/signals/reports/new-signals/latest | jq '.row_count'
```

## Notes

See [Signals overview](../README.md) for slug table.
