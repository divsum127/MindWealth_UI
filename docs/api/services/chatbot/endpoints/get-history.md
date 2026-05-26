# GET /api/v1/chatbot/sessions/{session_id}/history

## Summary

Full conversation JSON.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/chatbot/sessions/{session_id}/history`
- **operationId:** `get_chat_history`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`ChatbotEngine.get_conversation_history`

## Request

Query: display=true for UI prompts

## Response

Message array

## Example

```bash
curl -s ".../history?display=true" | jq
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
