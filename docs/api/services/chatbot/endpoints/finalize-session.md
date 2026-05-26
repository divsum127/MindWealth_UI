# POST /api/v1/chatbot/sessions/{session_id}/finalize

## Summary

Extract cross-session memory.

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/chatbot/sessions/{session_id}/finalize`
- **operationId:** `finalize_chat_session`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`ChatbotEngine.finalize_session`

## Request

None

## Response

{"session_id","memory_saved"}

## Example

```bash
curl -s -X POST .../finalize
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
