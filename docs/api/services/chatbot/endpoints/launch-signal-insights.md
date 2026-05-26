# POST /api/v1/chatbot/signal-insights

## Summary

New session + signal insights preset.

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/chatbot/signal-insights`
- **operationId:** `launch_signal_insights`
- **Status:** implemented
- **Typical status:** 202

## Maps to

`format_signal_insights_prompt + enqueue`

## Request

Optional dates

## Response

202 job payload

## Example

```bash
curl -s -X POST .../signal-insights
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
