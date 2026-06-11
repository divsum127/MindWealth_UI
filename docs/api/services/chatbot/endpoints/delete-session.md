# DELETE /api/v1/chatbot/sessions/{session_id}

## Summary

Delete session file.

## HTTP

- **Method:** `DELETE`
- **Path:** `/api/v1/chatbot/sessions/{session_id}`
- **operationId:** `delete_chat_session`
- **Status:** implemented
- **Typical status:** 204

## Maps to

`SessionManager.delete_session`

## Request

Path: session_id

## Response

No body

## Example

```bash
curl -s -X DELETE http://51.20.53.218:8506/api/v1/chatbot/sessions/{session_id}
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
