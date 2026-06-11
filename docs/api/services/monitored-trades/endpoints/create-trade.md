# POST /api/v1/monitored-trades

## Summary

Add a trade to the monitored list.

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/monitored-trades`
- **operationId:** `create_monitored_trade`
- **Status:** implemented
- **Typical status:** 201, 409

## Maps to

`src/utils/monitored_trades.add_trade_to_monitored()`

## Request

JSON body: trade object (must include fields expected by monitored trades store, e.g. `trade_id`, `symbol`).

## Response

201: created trade object

409: trade already exists or save failed

## Example

```bash
curl -s -X POST http://51.20.53.218:8506/api/v1/monitored-trades \
  -H "Content-Type: application/json" \
  -d '{"trade_id":"TEST-1","symbol":"AAPL","side":"long"}' | jq
```
