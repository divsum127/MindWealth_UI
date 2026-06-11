# GET /api/v1/monitored-trades

## Summary

List all user-monitored trades from `monitored_trades.json`.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/monitored-trades`
- **operationId:** `list_monitored_trades`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`src/utils/monitored_trades.load_monitored_trades()`

## Request

| Query | Type | Default | Description |
|-------|------|---------|-------------|
| `refresh_prices` | bool | `false` | Refresh live prices before returning |

## Response

200: array of trade records (empty array when none)

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/monitored-trades | jq
curl -s "http://51.20.53.218:8506/api/v1/monitored-trades?refresh_prices=true" | jq length
```
