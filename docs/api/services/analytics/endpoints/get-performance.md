# GET /api/v1/analytics/performance

## Summary

Combined performance report with optional aggregate stats.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/analytics/performance`
- **operationId:** `get_performance_summary`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`reports_service.performance_summary()` — reads `combined_performance_report.csv`.

## Response

200:

```json
{
  "source_file": "/path/to/combined_performance_report.csv",
  "row_count": 12,
  "avg_win_rate": 0.65,
  "total_trades": 450,
  "records": []
}
```

`avg_win_rate` and `total_trades` are present when CSV columns allow.

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/analytics/performance | jq '.avg_win_rate'
```
