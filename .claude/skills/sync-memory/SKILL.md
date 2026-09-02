---
name: sync-memory
description: >-
  Refresh the harness memory layer — pull new mail from Rohit, register Claude
  Code chats, re-read the job status and dev-to-prod docs, and regenerate the
  map, prod queue and feature hubs. Use when the user invokes /sync-memory,
  asks to "update memory", "refresh the memory layer", "check for new mail
  from Rohit", or asks what changed since the last sync.
---

# Sync memory

Rebuilds `docs/memory/` and the seven feature hubs from four sources: Gmail,
the Claude Code session transcripts, `docs/dev_to_prod_migration_todos.md` and
`docs/mindwealth_ui_job_status.md`.

**Read-only against every source.** The Gmail token carries `gmail.readonly`
and the sender allowlist in `~/.gmail-mcp/filters.yaml` is re-applied by the
fetcher, so this can never reach mail the filter policy hides. It writes only
inside `docs/memory/` and the `_HUB.md` files.

---

## Run it

```bash
python3 scripts/memory_sync.py --fetch-mail
```

Drop `--fetch-mail` to rebuild from local sources only (much faster, no
network). Use `--render-only` to regenerate the views from the existing index
without re-scraping anything.

---

## Then report what actually changed

The script prints record counts, not news. Turn them into something worth
reading:

1. **New mail since the last sync.** Compare `docs/memory/.sync_state.json`
   (its `last_sync`) against the newest `message` records. Name the threads
   that gained messages and say which feature they belong to.
2. **Open questions the new mail may answer.** For each feature hub whose
   threads moved, read the *Open questions* table. If a new message plausibly
   answers a row marked `ASKED`, say so and quote the evidence — but **do not
   flip the status yourself**. That table is hand-maintained; propose the edit
   and let the user confirm.
3. **Prod queue drift.** Report the pending count, the oldest block's age, and
   any block carrying a DEV-ONLY revert, from `docs/memory/PROD_QUEUE.md`.
4. **Unlinked chats.** If `MAP.md` shows chats with no thread linked and one
   obviously belongs to a thread, suggest the `/link-thread` call rather than
   guessing — heuristic links render in italics precisely so nobody mistakes
   them for confirmed ones.

---

## What not to do

- Do not hand-edit `MAP.md`, `PROD_QUEUE.md`, `features_index.md` or anything
  between the `MEMORY:BEGIN generated` markers in a hub. They are rebuilt on
  every run and your edit will vanish.
- Do not commit `docs/memory/.mail_cache.json`. It holds raw unscrubbed
  subjects and snippets and is gitignored for the same reason
  `docs/cursor_chat_archive/` is.
- Do not flip a `[PENDING]` migration block to `[DONE]`. A block is DONE when
  it is on prod, not when it is committed to `chatbot-dev`.
