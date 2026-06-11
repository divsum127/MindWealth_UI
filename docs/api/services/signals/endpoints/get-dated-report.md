# GET /api/v1/signals/reports/{report_name}/{report_date}

## Summary

Specific dated trade-store report as JSON records.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/signals/reports/{report_name}/{report_date}`
- **operationId:** `get_dated_signal_report`
- **Status:** implemented
- **Typical status:** 200, 404

## Maps to

`reports_service.load_report_records(report_name, report_date=report_date)`

## Request

| Param | Location | Format |
|-------|----------|--------|
| `report_name` | path | slug or base filename |
| `report_date` | path | `YYYY-MM-DD` |

## Response

Same shape as [get-latest-report.md](get-latest-report.md).

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/signals/reports/new-signals/2026-05-20 | jq '.report_date'
```
