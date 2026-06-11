# GET /api/v1/analytics/sentiment

## Summary

Latest PULSEGAUGE sentiment signal rows from `sentiment.csv`.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/analytics/sentiment`
- **operationId:** `get_sentiment_signals`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`reports_service.latest_sentiment_signals()`

## Response

200: `{ source_file, report_date, row_count, records }`

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/analytics/sentiment | jq '.records | length'
```
