# POST /api/v1/chatbot/analyze-asset

## Summary

New session + analyze asset preset.

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/chatbot/analyze-asset`
- **operationId:** `launch_analyze_asset`
- **Status:** implemented
- **Typical status:** 202

## Maps to

`format_analyze_asset_prompt + enqueue`

## Request

Body: asset required, from_date, to_date

## Response

202 job payload

## Example

```bash
curl -s -X POST .../analyze-asset -d '{"asset":"AAPL"}'
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
