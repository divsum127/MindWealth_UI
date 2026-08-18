# MindWealth_UI Repository Rules

Imported from Cursor rules (`.cursor/rules/*.mdc`, both `alwaysApply: true`). This file is always loaded — treat everything below as standing instructions for every session in this repo.

## Repository Scope

Unless the user explicitly provides another path or requests a broader search, work only within these directories.

### Editable (search, inspect, modify)

1. **MindWealth Core Repository** — `/home/ubuntu/MindWealth`
   * Trading strategies, signal generation, C++ codebase, Dash UI

2. **MindWealth UI dev/git clone** — `/home/ubuntu/uiv2/git/MindWealth_UI`
   * Chatbot, Streamlit UI, user-facing features, API source
   * **All code changes go here** (branch `chatbot-dev` → merge `chatbot-prod` → deploy)

### Read-only (inspect only — NEVER edit)

3. **Production deploy clone** — `/home/ubuntu/uiv2/prod/` and everything under it (including `/home/ubuntu/uiv2/prod/MindWealth_UI`)

   * **Out of scope for create / modify / delete / commit / push**
   * May read for debugging, health checks, logs, deploy verification
   * See **Production clone — do not edit** below

Do not search outside these directories unless the user explicitly provides another path or requests a broader search.

---

## Production clone — do not edit

**Protected path prefix:** `/home/ubuntu/uiv2/prod/`

This is the **live production deploy clone** (branch `chatbot-prod`). It is **pull-only**. Never treat it as a development workspace.

**Correct workflow:** edit `/home/ubuntu/uiv2/git/MindWealth_UI` on `chatbot-dev` → push → merge to `chatbot-prod` → deploy with pull/restart in prod clone only.

### Path guard (check before every edit)

Before any write, patch, delete, shell command, or git mutation, verify the target path:

* If it starts with `/home/ubuntu/uiv2/prod/` → **STOP. Do not proceed.**
* Redirect to `/home/ubuntu/uiv2/git/MindWealth_UI` and warn the user (see below).

This applies even when the user's open file, terminal cwd, or request points at prod.

### Forbidden in prod clone

Never **create, modify, or delete** anything under `/home/ubuntu/uiv2/prod/`:

* Source code (`.py`, `.ts`, `.vue`, `.sh`, configs tracked in git)
* `git commit`, `git push`, branch edits, or hand-edits to tracked files
* Agent-driven edits to runtime data (`.env`, `secrets.toml`, `trade_store/`, `conviction_store/`, etc.)

### Allowed in prod clone (deploy / read-only only)

* `git fetch` / `git pull origin chatbot-prod`
* `bash scripts/prod-pull-and-restart.sh`
* `.venv/bin/pip install -r requirements.txt` (deploy step only)
* `sudo systemctl restart mindwealth-api.service` (deploy step only)
* **Read-only** inspection: health checks, logs, `git status`, reading files

### Mandatory warning — accidental prod edit

**If you are about to (or nearly) touch `/home/ubuntu/uiv2/prod/` by mistake:**

1. **STOP.** Do not apply the edit or command.
2. **Warn the user explicitly** in the response, using wording like:

   > **Production path blocked:** I was about to change `/home/ubuntu/uiv2/prod/MindWealth_UI/...` but that tree is read-only (live prod). I will make this change in `/home/ubuntu/uiv2/git/MindWealth_UI` instead.

3. Continue work only in the **git clone** on `chatbot-dev`.

### Mandatory warning — user asks to edit prod

**If the user explicitly asks to edit, commit, or push in `/home/ubuntu/uiv2/prod/`:**

1. **Warn first — do not edit yet.** Explain prod is deploy-only and name the correct flow (git clone → `chatbot-dev` → merge `chatbot-prod` → `prod-pull-and-restart.sh`).
2. For normal requests ("fix this bug", "add this feature", "update this file"), **always** use the git clone even if the user names prod.
3. Edit prod **only** if the user clearly confirms an **emergency server exception** after reading the warning (e.g. break-glass hotfix). Prefer still patching git clone + deploy when possible.

Deploy workflow reference: [.claude/skills/prod-pull-and-details/SKILL.md](.claude/skills/prod-pull-and-details/SKILL.md)

---

## API documentation (canonical path)

**When the user says "update API docs", "API documentation", "api docs", or similar — always use:**

`/home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth-api-docs/`

| What | Path |
|------|------|
| Main index | `docs/mindwealth-api-docs/README.md` |
| Changelog | `docs/mindwealth-api-docs/changelog.md` |
| Service pages | `docs/mindwealth-api-docs/services/<service>/` |
| OpenAPI snapshot | `docs/mindwealth-api-docs/openapi/mindwealth-v1.json` |
| Export script | `scripts/export_openapi.py` → writes directly to the path above |

**Do not** create or edit `docs/api/` — that clone was removed to prevent drift. If the user names `docs/api`, redirect to `docs/mindwealth-api-docs`.

The separate git repo `mindwealth-api-docs` (GitHub `divsum127/mindwealth-api-docs`) mirrors this folder for published docs; commit there when pushing API doc releases.

---

## Job Status Tracking

All tasks, jobs, features, bug fixes, investigations, and implementations are tracked in two files:

### File 1 — Job Status (TODO / DONE)

**Path:** `/home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth_ui_job_status.md`

This file has two sections:

- `## TODO` — Tasks that are planned or in-progress.
- `## DONE` — Tasks that have been completed (SUCCESSFUL or UNSUCCESSFUL).

### File 2 — Job Status Details

**Path:** `/home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth_ui_repo_job_status_details.md`

This file records minute implementation details for every completed task, including:

- Assumptions made during implementation
- Things left for future (deferred, potential improvements, known gaps)
- Edge cases identified but not handled
- Architecture decisions and trade-offs
- Any caveats the next developer should know

### File 3 — Dev → Prod migration todos

**Path:** `/home/ubuntu/uiv2/git/MindWealth_UI/docs/dev_to_prod_migration_todos.md`

Living checklist for promoting `chatbot-dev` work to `chatbot-prod` / production. Records:

- Git files to merge (new + modified)
- **Dev-only** config that must be **reverted** at prod cutover (e.g. Nuxt pointing at `:8507`)
- Runtime files to **create or copy** on prod (never in git): `.env`, `config/users.json`, secrets
- **systemd** / Nuxt env changes on the host
- Bootstrap scripts, smoke tests, and pending follow-ups

---

## Mandatory Logging Protocol

After completing any task, whether SUCCESSFUL or UNSUCCESSFUL:

### Step 1 — Update Job Status file

Open `/home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth_ui_job_status.md` and:

1. **Check if the task already exists under `## TODO`.**
   - If YES: Move the entry from `## TODO` to `## DONE`, updating its status and adding outcome details.
   - If NO: Add a new entry directly under `## DONE`.

2. Each DONE entry must include:
   - Task description
   - Status: SUCCESSFUL / UNSUCCESSFUL
   - Date (YYYY-MM-DD)
   - Summary of outcome
   - Relevant files changed (if any)

3. Maintain sequential date-based numbering within each section.

### Step 2 — Update Job Status Details file

Open `/home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth_ui_repo_job_status_details.md` and add a detail block for the task containing:

- Implementation assumptions
- Things deferred or left for future
- Edge cases not handled
- Key decisions made
- Any caveats

### Step 3 — Update Dev → Prod migration todos

Open `/home/ubuntu/uiv2/git/MindWealth_UI/docs/dev_to_prod_migration_todos.md` and add or update an entry when the change affects production deployment:

1. List **new and modified git files** that must merge `chatbot-dev` → `chatbot-prod`.
2. Mark **dev-only** shortcuts (temporary config) that must be **reverted** on prod — e.g. Nuxt `NUXT_API_BASE_URL` on `:8507`, test flags.
3. List **runtime artifacts** to create/copy on prod (`.env` keys, `config/users.json`, bootstrap scripts) — explicitly **not** committed to git.
4. Note **systemd / Nuxt** host changes (`/etc/systemd/system/`, `npm run build`, restarts).
5. Add **smoke tests** and mark status `[PENDING]` or `[DONE]` with date.

Skip this step only for purely local/docs changes with **zero** prod impact (say so in the job status entry).

---

## Date-Based Numbering

Maintain sequential numbering for entries within each date group.

Example (DONE section):

### 2026-06-06

1. Added new signal generation logic — SUCCESSFUL
2. Fixed Streamlit authentication issue — SUCCESSFUL
3. Investigated portfolio calculation bug — UNSUCCESSFUL

### 2026-06-07

1. Added risk management module — SUCCESSFUL
2. Investigated websocket disconnect issue — UNSUCCESSFUL

Always continue numbering from the latest entry for that date.

---

## Completion Protocol

Before declaring any task complete:

1. Verify implementation or investigation results.
2. Update `mindwealth_ui_job_status.md` — move from TODO to DONE (or add to DONE if not previously in TODO).
3. Update `mindwealth_ui_repo_job_status_details.md` with implementation details.
4. Update `docs/dev_to_prod_migration_todos.md` when the change has prod deployment impact (see Step 3 above).
5. Record status as SUCCESSFUL or UNSUCCESSFUL.
6. Record the current date.
7. Maintain correct numbering for that date.
8. Then provide the final response to the user.

Failure to update job status tracking files is considered an incomplete task. Failure to update `dev_to_prod_migration_todos.md` is incomplete when the change affects prod migration.

---

# MindWealth Todos — Default Google Sheet

## Canonical sheet

Unless the user **explicitly names another spreadsheet, URL, or tab**, treat this as the default todo sheet:

| Field | Value |
|-------|-------|
| **Name** | mindwealth todos |
| **Spreadsheet ID** | `1a60p0E4D1w4X3xayV65UOvk9dz4b2q9bKLBPPnrHQKg` |
| **Default tab** | `v2_TODOs` (gid `1916178694`) |
| **Spreadsheet title** | Copy of Tasks_Mindwealth |
| **URL** | https://docs.google.com/spreadsheets/d/1a60p0E4D1w4X3xayV65UOvk9dz4b2q9bKLBPPnrHQKg/edit?gid=1916178694 |

Config file: `/home/ubuntu/.google-sheets-mcp/sheet-config.json`

MCP server: `mindwealth-todos` (added to Claude Code at user scope via `claude mcp add`, mirrors `~/.cursor/mcp.json`).

## Edit policy (mandatory)

**Default: read-only.** Never modify the sheet unless the user **explicitly** asks for a write (add, update, mark done, delete, clear, append, change status, etc.).

**Even when the user explicitly requests an edit**, you **must ask for confirmation once** before calling any write MCP tool (`update_cells`, `batch_update_cells`, or any other tool that mutates sheet data).

Confirmation must include:
- Exact spreadsheet + tab
- Cell/range or row to change
- Current value (if known) → proposed new value
- A clear yes/no prompt (e.g. "Confirm this edit?")

**Do not write** until the user confirms in a follow-up message. If they decline or do not confirm, stop — no write.

**Never** infer write permission from:
- Summarizing, listing, or analyzing todos
- Vague language ("clean this up", "sync todos", "fix the sheet")
- Completing related code/docs work elsewhere in the repo

Reads (`get_sheet_data`, `list_sheets`, `find_in_spreadsheet`, `search_spreadsheets`, etc.) are allowed without confirmation.

## When to use this sheet

Use **mindwealth todos** for any request about:

- todos / task list / backlog / checklist
- "what's pending", "show open items", "summarize todos"
- MindWealth work tracking in Google Sheets

**Do not ask** which sheet to use for read-only todo queries — assume this one.

Write requests ("add a task", "mark done", "update status") still require the **confirmation step** above before any MCP write.

## When to use a different sheet

Only switch away from this default when the user:

- Pastes a different Google Sheets URL or spreadsheet ID
- Names another spreadsheet or tab explicitly
- Says "use a different sheet" or similar

The same **read-only default + confirmation-before-write** policy applies to any Google Sheet accessed via MCP.

## MCP usage

1. Use the `mindwealth-todos` MCP server tools.
2. Pass `spreadsheet_id` = `1a60p0E4D1w4X3xayV65UOvk9dz4b2q9bKLBPPnrHQKg` unless overridden.
3. Default tab name: **`v2_TODOs`** (gid `1916178694`). Use this tab unless user names another.
4. **Read first** when structure is unknown or before proposing an edit.
5. **Write only** after explicit user request **and** one confirmed yes.

## Auth note

Requires Google Sheets API + Drive API enabled on GCP project `mindwealth-gmail-mcp`, and OAuth token at `~/.google-sheets-mcp/token.json`.
