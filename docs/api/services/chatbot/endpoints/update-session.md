# PATCH /api/v1/chatbot/sessions/{session_id}

## Summary

Rename session.

## HTTP

- **Method:** `PATCH`
- **Path:** `/api/v1/chatbot/sessions/{session_id}`
- **operationId:** `update_chat_session`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`SessionManager.update_session_title`

## Request

Body: {"title"}

## Response

{"session_id","title"}

## Example

```bash
curl -s -X PATCH ... -d '{"title":"Renamed"}'
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
