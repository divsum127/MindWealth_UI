# GET /api/v1/chatbot/jobs

## Summary

List recent jobs.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/chatbot/jobs`
- **operationId:** `list_chat_jobs`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`JobStore.list_by_session`

## Request

Query: session_id, limit

## Response

Job array

## Example

```bash
curl -s ".../jobs?session_id=..." | jq
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
