# GET /api/v1/analytics/sigma

## Summary

Latest sigma report rows for dashboard KPI widgets.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/analytics/sigma`
- **operationId:** `get_sigma_report`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`reports_service.latest_sigma()` — reads latest `sigma.csv` from trade store.

## Response

200: `{ source_file, report_date, row_count, records }`

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/analytics/sigma | jq '.row_count'
```
