# POST /api/v1/conviction/signals/evaluate

## Summary

Score a single BUY/SELL signal and return verdict + sizing.

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/conviction/signals/evaluate`
- **operationId:** `evaluate_signal`
- **Status:** implemented

## Maps to

`engine.modify_signal()`

## Request

Body: ticker, technical_signal (BUY|SELL), signal_timeframe (long|short), optional long_position_near_stop, persist

## Response

200: SignalModification; 502 on failure

## Example

```bash
curl -s -X POST http://51.20.53.218:8506/api/v1/conviction/signals/evaluate -H "Content-Type: application/json" -d '{"ticker":"AAPL","technical_signal":"BUY","signal_timeframe":"long"}' | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
