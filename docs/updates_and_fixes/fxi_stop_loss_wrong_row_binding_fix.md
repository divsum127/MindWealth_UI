# FXI Wrong Stop Loss — Issue & Resolution

This document describes the **FXI stop-loss mix-up** flagged in [`chatbot/flagged_pairs/flag_20260520_773c6548.json`](../../chatbot/flagged_pairs/flag_20260520_773c6548.json): what went wrong, what we changed, and how those changes prevent recurrence.

**Related:** [REPORTS.md — Targets / Stop Loss columns](../documentation/REPORTS.md), [analyze_asset_prompt_update.md](analyze_asset_prompt_update.md), flag session `fb0be99c-ee58-44f4-978e-6b9aed381417`.

---

## Symptom

During a China ETF comparison, the assistant described **FXI FRACTAL TRACK Weekly** with:

- Entry: **$35.34 on 2026-04-12** (correct position identity)
- Stop loss: **$38.60 (Recent Extrema) / $38.66 (EMA 200)** — **above** current price **$36.28**
- Take profit: **$41.26 / $45.78 / $52.50**

The user correctly noted that for a **Long**, stop loss must be **below** spot. A follow-up in the same session re-fetched data and corrected to **$34.85** Recent Extrema. **CSV data for the April row was already correct**; the first narrative was wrong.

---

## Exact issue (root cause)

Two separate failures, not bad underlying data:

| Failure | What happened | Evidence in `chatbot/data/entry.csv` |
|--------|----------------|-------------------------------------|
| **Wrong signal row** | TP/SL from **2026-01-04** FRACTAL TRACK weekly were attached to the **2026-04-12** position header | Jan row: stop `38.6/...`, targets `41.2296/45.6815/52.5`. Apr row: stop `34.85`, targets `37.5622/41.6766/48.93`, open `35.34` |
| **Targets vs Stop confusion** | **$38.66** was reported as “EMA 200 stop” but is the **7th slot of the Targets column**; April stop column says **No EMA 200 Stop Loss** | Same 7-slot ladder order for Targets vs Stop Loss per REPORTS.md |

Contributing factors:

- Multiple open FXI FRACTAL TRACK rows in one date window (Jan + Apr).
- No row-binding guardrail forcing TP/SL/entry to share one `Symbol, Signal, Signal Date/Price[$]` row.
- No automated check that Long stops are below today’s price.
- Large conversation context (~15 prior turns) increased row mix-up risk.

---

## Changes made

### 1. Prompt row-binding rules

| File | Change |
|------|--------|
| [`prompts/engine.py`](../../prompts/engine.py) | `TARGET_STOP_ROW_BINDING_RULES` appended to `SYSTEM_PROMPT` via [`chatbot/config.py`](../../chatbot/config.py) |
| [`prompts/chatbot_system.txt`](../../prompts/chatbot_system.txt) | Documented Targets vs Stop ladders and row-binding for column selection |
| [`prompts/ui_buttons.py`](../../prompts/ui_buttons.py) | Analyze Asset RULES: same row binding + Long/Short vs today price |

### 2. Paired Targets + Stop fetch guardrail

| File | Change |
|------|--------|
| [`chatbot/chatbot_engine.py`](../../chatbot/chatbot_engine.py) | `_apply_entry_target_stop_guardrails()` merges **Targets (...)** and **Stop Loss (...)** into entry column fetches when the query or selected columns imply levels |

Constants: `ENTRY_TARGETS_STOP_COLUMN_NAMES` in [`chatbot/smart_data_fetcher.py`](../../chatbot/smart_data_fetcher.py).

### 3. Post-fetch signal level validation

| File | Change |
|------|--------|
| [`chatbot/signal_level_validator.py`](../../chatbot/signal_level_validator.py) | **New:** `validate_entry_record()`, `build_entry_validation_section()` — flags Long stop ≥ today, Short stop ≤ today, EMA target mislabeled as stop |
| [`chatbot/chatbot_engine.py`](../../chatbot/chatbot_engine.py) | Appends `=== SIGNAL LEVEL VALIDATION ===` block to smart-query prompt |
| [`chatbot/agents/synthesis_agent.py`](../../chatbot/agents/synthesis_agent.py) | Same validation block in hybrid SOURCE A |

### 4. Fetch disambiguation

| File | Change |
|------|--------|
| [`chatbot/smart_data_fetcher.py`](../../chatbot/smart_data_fetcher.py) | `parse_cited_entry_hints()`, `filter_rows_by_cited_entry_hints()` — when user text cites `Entry: $X on DATE`, keep matching rows only |
| | `collapse_latest_per_function_interval()` — for single-ticker non–deep-dive queries, one row per Function+interval (latest signal date) |
| | `user_message` passed through `fetch_data` / `fetch_data_consolidated` / `_fetch_signal_type_data_consolidated` |

### 5. Tests

| File | Coverage |
|------|----------|
| [`tests/test_signal_level_validator.py`](../../tests/test_signal_level_validator.py) | Jan FXI row warns; Apr row EMA target note; cited-entry hint parsing |

---

## How the changes help

- **Correct row binding** — April FXI open position shows **$34.85** extrema stop and April targets, not January’s **$38.6** / **$41.26** ladder.
- **Column clarity** — EMA **target** (e.g. 38.66) is not mislabeled as EMA **stop** when the stop column has no EMA level.
- **Automatic inconsistency flags** — Long + stop above today surfaces as stale/breached in `=== SIGNAL LEVEL VALIDATION ===` instead of being presented as live protection.
- **Cited-entry filtering** — When the user quotes `Entry: $35.34 on 2026-04-12`, the fetcher can narrow to that row before the model answers.
- **Regression anchor** — Flag JSON + CSV row table give QA a fixed replay case (FXI, FRACTAL TRACK, Apr 12 vs Jan 4).

---

## What we did not change

- Underlying **entry.csv** values for FXI April rows (already correct).
- The correction-turn behavior (follow-up already fetched correct rows); fixes target the **first wrong narrative** class of bugs.
