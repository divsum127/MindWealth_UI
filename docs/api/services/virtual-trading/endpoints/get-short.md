# GET /api/v1/virtual-trading/short

## Summary

Short-side virtual trading positions from latest `virtual_trading_short.csv`.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/virtual-trading/short`
- **operationId:** `get_virtual_trading_short`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`reports_service.load_virtual_trading("short")`

## Response

200: `{ side, source_file, row_count, records }`

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/virtual-trading/short | jq '.row_count'
```
