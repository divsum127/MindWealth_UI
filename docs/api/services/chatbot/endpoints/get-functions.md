# GET /api/v1/chatbot/functions

## Summary

Strategy function names.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/chatbot/functions`
- **operationId:** `get_chatbot_functions`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`ChatbotEngine.get_available_functions`

## Request

Query: ticker

## Response

string array

## Example

```bash
curl -s ".../functions?ticker=AAPL" | jq
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
