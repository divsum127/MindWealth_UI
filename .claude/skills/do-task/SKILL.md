---
name: do-task
description: >-
  Execute a MindWealth task end to end from a pasted task description: analyze
  the task and the codebase, pull context from the gmail-filtered and
  mindwealth-todos MCP servers when needed, list clarifications required from
  Rohit sir, reproduce the visible issue, find the true root cause, fix the
  root cause (not the symptom), verify, and log to the job status docs. Use
  when the user invokes /do-task or pastes a task/bug/feature description and
  asks to analyze and fix it.
---

# Do Task

Input: a task description (bug report, feature ask, WhatsApp/email paste, todo row).
Output: root-cause fix in the git clone + verification + clarification list + job status logs.

**Never** create/modify/delete under `/home/ubuntu/uiv2/prod/`. All edits in
`/home/ubuntu/uiv2/git/MindWealth_UI` (branch `chatbot-dev`) or `/home/ubuntu/MindWealth`.

---

## Phase 0 — Restate the task

Before touching code, write:

| Field | Value |
|-------|-------|
| Task (one line) | verbatim intent, not paraphrase-drift |
| Type | bug / feature / investigation / data issue |
| Visible symptom | what user sees, exact numbers/strings/screens |
| Expected behaviour | what should happen instead |
| Scope guess | files/services likely involved |
| Unknowns | what is not stated in the task |

If the task text is a paste from chat/email, keep the original wording in the
symptom row. Do not "clean up" numbers or error strings.

---

## Phase 1 — Gather context

Work only inside the repo scope (`/home/ubuntu/MindWealth`,
`/home/ubuntu/uiv2/git/MindWealth_UI`) unless the user gives another path.

1. **Codebase** — locate the code path that produces the symptom. Grep for the
   exact error string, label, endpoint, or number from the task. Read the real
   call chain end to end (router → service → core module → data file). Note
   `file:line` for every claim.
2. **Docs** — check for prior context before re-deriving:
   - `docs/mindwealth_ui_job_status.md` (was this done/attempted before?)
   - `docs/mindwealth_ui_repo_job_status_details.md` (known caveats, deferred items)
   - `docs/dev_to_prod_migration_todos.md` (is dev/prod drift the cause?)
   - topic docs: `docs/MACRO_INTELLIGENCE_MASTER.md`, `docs/ssi_validation/*`,
     `docs/rohit_*_answers_*.md`
3. **MCP — only when the codebase does not answer it:**

   | Need | Server | Tools |
   |------|--------|-------|
   | Original ask / thread from Rohit sir (`rohit.malhotra1@gmail.com`) | `gmail-filtered` | `search_emails`, `fetch_emails`, `get_email_metadata` |
   | Todo row, priority, prior status of this task | `mindwealth-todos` | `get_sheet_data`, `find_in_spreadsheet`, `list_sheets` |

   Sheet defaults: spreadsheet `1a60p0E4D1w4X3xayV65UOvk9dz4b2q9bKLBPPnrHQKg`, tab `v2_TODOs`.
   Sheets and Gmail are **read-only** here. Any write (mark done, update status,
   send/draft mail) needs an explicit user request **and** one confirmation
   before the call.
4. **Runtime** — logs, API responses, data files, DB rows when the symptom is
   runtime-only. Prod tree may be **read** for this (logs, health checks).

Stop gathering when you can name the failing line. Do not keep reading.

---

## Phase 2 — Reproduce the visible issue

Never fix on theory alone.

- Reproduce with a command, endpoint call, script, or data read, and paste the
  actual output.
- If it cannot be reproduced locally (prod-only data, market hours, missing
  secrets), say so plainly and state what evidence you used instead.
- Record the reproduction command in the final report so the next dev can rerun it.

---

## Phase 3 — Root cause

Rule: the root cause is the earliest point where correct input became wrong
output. Keep asking "why is that value wrong?" until the answer is code, config,
or data you can point at with `file:line` or a path.

Symptom vs root cause — do not stop at the left column:

| Symptom-level (wrong) | Root-cause-level (right) |
|-----------------------|--------------------------|
| Add null check at render | Upstream service returns `None` because the fetch failed silently |
| Clamp the number in the UI | Wrong scaling factor applied in the signal calc |
| Retry the API call | Auth token cached past expiry |
| Regenerate the CSV | Loader writes stale date because it never advances the cursor |
| `try/except: pass` | Real exception path never handled |

Then state:

- **Root cause:** one sentence + `file:line`.
- **Why it surfaced now:** what changed (commit, data, config, date rollover).
- **Blast radius:** every other caller/screen/job hitting the same defect.

If evidence points to two plausible causes, test to discriminate — do not fix both blindly.

---

## Phase 4 — Fix the root cause

- Fix at the root-cause layer. Add a symptom-level guard **only** in addition to
  the real fix, and say why it is there.
- Match surrounding code style, naming, comment density.
- Fix every site in the blast radius, or list explicitly which ones were left and why.
- No new mocks, no hardcoded sample data, no silent `except: pass`.
- Keep the diff scoped to the task. Anything else you spot goes in the
  clarification/follow-up list, not into the diff.

---

## Phase 5 — Verify

- Rerun the Phase 2 reproduction — it must now pass. Paste the output.
- Run relevant tests (`pytest` for touched modules) and endpoint smoke checks.
- Check the blast-radius callers still behave.
- Report failures honestly with the output; never claim green without a run.

For full pre-prod verification and dev deploy, hand off to the
`robust-test-and-dev-deploy` skill.

---

## Phase 6 — Clarifications from Rohit sir

Always produce this section, even if empty.

Split into:

- **Blocking** — proceeding under any assumption risks wrong business logic
  (thresholds, formulas, regime rules, what a metric should mean). Do not guess.
  Deliver everything not blocked, then ask.
- **Non-blocking** — you assumed a reasonable default and shipped; state the
  assumption so it can be corrected.

Each question: one line, answerable yes/no or with a number. Give the option set
you see in the code so a one-word answer suffices.

If the user asks for a message to send, use the `human-reply` skill for the
wording. Do not send mail or edit the sheet without explicit request + confirmation.

---

## Phase 7 — Mandatory logging (task not complete without this)

1. `docs/mindwealth_ui_job_status.md` — move the entry from `## TODO` to `## DONE`,
   or add under `## DONE`. Include description, SUCCESSFUL/UNSUCCESSFUL, date
   (today), outcome summary, files changed. Keep date-based numbering sequential.
2. `docs/mindwealth_ui_repo_job_status_details.md` — detail block: assumptions,
   root cause, deferred items, edge cases not handled, decisions, caveats.
3. `docs/dev_to_prod_migration_todos.md` — when the change has prod impact: new +
   modified files to merge, dev-only config to revert, runtime files to create on
   prod, systemd/Nuxt changes, smoke tests `[PENDING]`/`[DONE]`.
   Skip only for pure docs/local changes with zero prod impact — and say so in the
   job status entry.

---

## Final response format

```
Task        — one line
Symptom     — what was visible
Root cause  — one sentence + file:line
Fix         — what changed, where, why it is the root fix
Verified    — command run + result
Left out    — blast-radius sites or scope not touched, with reason
Ask Rohit   — blocking questions (or "none")
Logged      — the doc files updated
```

Keep it tight. Evidence over narrative.
