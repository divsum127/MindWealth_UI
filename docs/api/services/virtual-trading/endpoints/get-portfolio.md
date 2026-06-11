# GET /api/v1/virtual-trading/portfolio

## Summary

Combined long/short virtual trading summary (row counts and open positions).

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/virtual-trading/portfolio`
- **operationId:** `get_portfolio_summary`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`reports_service.portfolio_summary()`

## Response

200:

```json
{
  "long": { "row_count": 10, "open_count": 7 },
  "short": { "row_count": 5, "open_count": 3 },
  "combined_open": 10
}
```

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/virtual-trading/portfolio | jq
```

## Notes

Used by Alpha Terminal portfolio views. YTD P&L is on [get-portfolio-ytd.md](../../analytics/endpoints/get-portfolio-ytd.md).
