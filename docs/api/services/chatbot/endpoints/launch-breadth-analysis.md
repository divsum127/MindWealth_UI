# POST /api/v1/chatbot/breadth-analysis

## Summary

New session + breadth preset.

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/chatbot/breadth-analysis`
- **operationId:** `launch_breadth_analysis`
- **Status:** implemented
- **Typical status:** 202

## Maps to

`format_breadth_analysis_prompt + enqueue`

## Request

Optional dates

## Response

202 job payload

## Example

```bash
curl -s -X POST .../breadth-analysis
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
