# POST /api/v1/chatbot/sessions/{session_id}/messages

## Summary

Queue async chat job.

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/chatbot/sessions/{session_id}/messages`
- **operationId:** `enqueue_chat_message`
- **Status:** implemented
- **Typical status:** 202

## Maps to

`smart_followup_query via job runner`

## Request

ChatMessageRequest body — see README presets

## Response

{"job_id","session_id","status","poll_url"}

## Example

```bash
curl -s -X POST .../messages -d '{"message":"hi","preset":"freeform"}'
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
