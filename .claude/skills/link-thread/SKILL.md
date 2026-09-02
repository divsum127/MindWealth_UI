---
name: link-thread
description: >-
  Record that this Claude Code chat is working on a particular mail thread from
  Rohit, so the thread-to-chat map can find it later. Use when the user invokes
  /link-thread, says "link this chat to that mail", "remember which thread this
  is", or starts work from a pasted mail and wants the connection kept.
---

# Link thread

Stamps an explicit `session -> thread` link into `docs/memory/index.jsonl` and
regenerates `MAP.md` and the feature hubs.

Why it matters: the sync infers links from shared words and timing, and renders
those in *italics* because they are guesses. An explicit link is rendered plain
and is never overwritten by a later guess. Months from now, `MAP.md` is how the
user finds which chat handled which mail — so a stamped link is worth the five
seconds.

---

## Steps

1. **Find the thread.** If the user pasted a subject or a Gmail link, use that.
   Otherwise search the index:

   ```bash
   grep '"type": "thread"' docs/memory/index.jsonl | grep -i '<keyword>'
   ```

   If nothing matches, run `/sync-memory` first — the thread may be newer than
   the last sync.

2. **Find this chat's session id.** It is the current session's UUID. If you
   cannot determine it, the newest session record is almost always this one:

   ```bash
   grep '"type": "session"' docs/memory/index.jsonl | tail -3
   ```

3. **Stamp the link.** Both arguments accept id prefixes or a substring of the
   title/subject:

   ```bash
   python3 scripts/memory_sync.py --link <session-prefix> <thread-id>
   ```

4. **Confirm** by quoting the line the script prints. If it reports an
   ambiguous match it lists the candidates — pick one and re-run rather than
   guessing, because a wrong link is worse than no link.

---

## Notes

- Linking is many-to-many by design. One chat can be linked to several threads
  and one thread to several chats; run the command once per pair.
- The link records `conf: explicit`, which the sync will not clobber.
- This writes only to `docs/memory/`. It never touches mail, the job status
  docs, or the migration doc.
