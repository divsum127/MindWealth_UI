# GET /api/v1/signals/reports

## Summary

Catalog of discoverable trade-store CSV reports.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/signals/reports`
- **operationId:** `list_signal_reports`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`reports_service.list_available_reports()` — scans `trade_store/US/` via `discover_csv_files()`.

## Request

None

## Response

200: array of `{ page_name, base_filename, path, report_date }`

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/signals/reports | jq
```

## Notes

See [Signals overview](../README.md).
