# GET /api/v1/analytics/portfolio-ytd

## Summary

Year-to-date P&L proxy from virtual trading long positions entered this calendar year.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/analytics/portfolio-ytd`
- **operationId:** `get_portfolio_ytd`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`reports_service.forced_portfolio_ytd()` — sums `Realised/Unrealised Profit` for YTD entries in long CSV.

## Response

200:

```json
{
  "forced_portfolio_ytd": 12.34,
  "year": 2026,
  "position_count": 5
}
```

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/analytics/portfolio-ytd | jq '.forced_portfolio_ytd'
```

## Notes

Maps to Overwatch `forced_portfolio_ytd` in the Alpha Terminal frontend.
