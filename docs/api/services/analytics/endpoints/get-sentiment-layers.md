# GET /api/v1/analytics/sentiment/layers

## Summary

SSI positioning composite, layer inputs, and latest sentiment signal rows.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/analytics/sentiment/layers`
- **operationId:** `get_sentiment_layers`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`reports_service.sentiment_layers()` — merges `positioning.json` + latest sentiment CSV.

## Response

200:

```json
{
  "positioning": {},
  "composite": {
    "ssi_level": null,
    "ssi_percentile_5y": null,
    "layer2_status": null,
    "ssi_multiplier": null
  },
  "layer_inputs": {},
  "layer2_votes": [],
  "signal_rows": [],
  "signal_report_date": "2026-05-20"
}
```

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/analytics/sentiment/layers | jq '.composite'
```

## Notes

Primary endpoint for Alpha Terminal SSI / sentiment layer UI.
