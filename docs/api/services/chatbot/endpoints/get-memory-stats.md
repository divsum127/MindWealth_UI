# GET /api/v1/chatbot/memory/stats

## Summary

Rolling memory log statistics.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/chatbot/memory/stats`
- **operationId:** `get_memory_stats`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`ChatbotEngine.get_memory_stats`

## Request

None

## Response

stats object

## Example

```bash
curl -s .../memory/stats | jq
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
