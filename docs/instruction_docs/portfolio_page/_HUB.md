# portfolio_page — feature hub

> Everything known about this feature: what we were told, what we decided, what
> is still open, and which chat did the work.
>
> Sections between the generated markers are rebuilt by
> `scripts/memory_sync.py`. **Everything below "Decisions ledger" is yours** —
> the sync never touches it.

<!-- MEMORY:BEGIN generated — rewritten by scripts/memory_sync.py -->
## Spec sources

| File | Type | Modified |
|---|---|---|
| `docs/instruction_docs/portfolio_page/portfolio_implementation_log.md` | md | 2026-09-02 |
| `docs/instruction_docs/portfolio_page/portfolio_sizer_v2_18June.md` | md | 2026-08-17 |
| `docs/instruction_docs/portfolio_page/spec_15July.md` | md | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/mindwealth_portfolio_v4.html` | html | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/ikbr_details.md` | md | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/ahil_analysis/MindWealth_Consolidated_Report.pdf` | pdf | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/ahil_analysis/MindWealth_Ahil_NAV_FILLED_VersionA_GATED_FIXED_DAILYDD.xlsx` | xlsx | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/ahil_analysis/MindWealth_Ahil_NAV_FILLED_GATED_FIXED_DAILYDD.xlsx` | xlsx | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/Parth_Portfolio_Spec_v1.docx.pdf` | pdf | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/PORTFOLIO_PAGE_AIM_AND_STATUS.md` | md | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/PORTFOLIO_DATA_ISSUES.md` | md | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/PORTFOLIO_API_HANDOFF_02.md` | md | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/PORTFOLIO_API_HANDOFF_01.md` | md | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md` | md | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/MindWealth_Portfolio_Unified_v5.html` | html | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/Ahil_portfolio_page_docs_2.md` | md | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/Ahil_portfolio_page_docs.md` | md | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/23July_reply_to_ahil_7_items.md` | md | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/21July_review_specs.md` | md | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/15July_imp_spec_additions.md` | md | 2026-07-26 |
| `docs/instruction_docs/portfolio_page/14July_axioms_and_specs.md` | md | 2026-07-26 |

## Mail threads

| Thread | First | Last | Msgs |
|---|---|---|---|
| [Claude Signals Prompt v3 Addendum (Aug 12) — 5 docs attached, 4 i](https://mail.google.com/mail/u/0/#all/19ff3ad4e412a7d2) | 2026-08-11 | 2026-08-26 | 4 |
| [Making Claude more consistent with Payload - Claude Signals Promp](https://mail.google.com/mail/u/0/#all/1a03fa4b34f09d14) | 2026-08-26 | 2026-08-26 | 1 |
| [Architectural Shift - Moving to Dynamic Autonomous Loops](https://mail.google.com/mail/u/0/#all/1a02a0b26ae4082f) | 2026-08-22 | 2026-08-22 | 1 |
| [Some feedback and priorities - additional to prior emails](https://mail.google.com/mail/u/0/#all/19f83b17bff9295b) | 2026-07-21 | 2026-08-06 | 2 |
| [Re: regime doubts — answers on all three, plus portfolio/regime h](https://mail.google.com/mail/u/0/#all/19fd667fd4b1b9d8) | 2026-08-06 | 2026-08-06 | 1 |
| [hi Divyanshu - I need this done as of two days ago - Re: AHIL/DIV](https://mail.google.com/mail/u/0/#all/19f83ebc238c8f11) | 2026-07-21 | 2026-07-22 | 2 |
| [Feedback on 20 July Consolidated Report](https://mail.google.com/mail/u/0/#all/19f83bc51839e192) | 2026-07-21 | 2026-07-21 | 1 |
| [IBKR API integration — plan and parallel paper/live setup](https://mail.google.com/mail/u/0/#all/19f873418327f002) | 2026-07-21 | 2026-07-21 | 1 |
| [Review 1 as we come close to the end of summer holidays - In betw](https://mail.google.com/mail/u/0/#all/19f4dbabc584fb15) | 2026-07-10 | 2026-07-19 | 2 |
| [IMPORTANT - PLEASE READ TODAY - Portfolio finalization — four-boo](https://mail.google.com/mail/u/0/#all/19f659d0e9202556) | 2026-07-15 | 2026-07-15 | 2 |
| [MindWealth · Portfolio Page (Unified) — PAGE BRIEF · Frontend Bui](https://mail.google.com/mail/u/0/#all/19f6762ddd4889f3) | 2026-07-15 | 2026-07-15 | 1 |
| [AHIL/DIVYANSHU FOLLOW-UP - (Parth just fyi)](https://mail.google.com/mail/u/0/#all/19f679cf72751af2) | 2026-07-15 | 2026-07-15 | 1 |
| [MindWealth — Consolidated Test Plan: Optimal N, Stop-Loss, Regime](https://mail.google.com/mail/u/0/#all/19f41f2769a5a6ac) | 2026-07-08 | 2026-07-08 | 1 |
| [MindWealth — composite score v4, forward-test Sharpe methodology,](https://mail.google.com/mail/u/0/#all/19eee89cefe73a96) | 2026-06-22 | 2026-06-22 | 1 |
| [Fwd: Portfolio Sizer v2 — Updated Spec (what you have vs what to ](https://mail.google.com/mail/u/0/#all/19ed9d0c9706f14a) | 2026-06-18 | 2026-06-18 | 1 |
| [portfolio specs](https://mail.google.com/mail/u/0/#all/19ed9de28c792e20) | 2026-06-18 | 2026-06-18 | 1 |
| [Signals MasterSpec](https://mail.google.com/mail/u/0/#all/19eca4af7a26aab8) | 2026-06-15 | 2026-06-15 | 1 |
| [Three updates — SSI (to build), Claude prompt v2, ranked signal s](https://mail.google.com/mail/u/0/#all/19eba5eebc341663) | 2026-06-11 | 2026-06-11 | 1 |
| [VERY IMPORTANT - PLEASE READ - replacing claude api report with a](https://mail.google.com/mail/u/0/#all/19dfa267adbff196) | 2026-05-06 | 2026-05-06 | 1 |
| [IMPORTANT Please read - Re: Signal Breadth Indicator (SBI) - Apr ](https://mail.google.com/mail/u/0/#all/19dc48480e3aa9d8) | 2026-04-26 | 2026-04-26 | 1 |
| [fundamental sub agent updated](https://mail.google.com/mail/u/0/#all/19d91291f4d1969a) | 2026-04-16 | 2026-04-16 | 1 |
| [AHIL Pl read. - what claude does - Re: Forced Allocation Logic an](https://mail.google.com/mail/u/0/#all/19d69ad8afc176d7) | 2026-04-08 | 2026-04-08 | 1 |
| [Fwd: MindWealth Pro ioS app post integrating](https://mail.google.com/mail/u/0/#all/19d58319ff871060) | 2026-04-05 | 2026-04-05 | 1 |
| [easy test to try - let me know what backtest looks like](https://mail.google.com/mail/u/0/#all/19d57fa0b248a0dd) | 2026-04-04 | 2026-04-04 | 1 |
| [Fwd: Claude Signals Report - Mar 31, 2026 6:00 PM EST](https://mail.google.com/mail/u/0/#all/19d4ddbcf5757b31) | 2026-04-03 | 2026-04-03 | 1 |
| [Fwd: Claude Signals Report - Mar 30, 2026 6:00 PM EST](https://mail.google.com/mail/u/0/#all/19d4ddc399b25692) | 2026-04-03 | 2026-04-03 | 1 |
| [Forced Allocation Logic and some rough thoughts on how i pick ass](https://mail.google.com/mail/u/0/#all/19d5093aa0d82413) | 2026-04-03 | 2026-04-03 | 1 |
| [Fwd: Important - Re: Improving chatbot as I had requested earlier](https://mail.google.com/mail/u/0/#all/19d48e3cc3e67bde) | 2026-04-02 | 2026-04-02 | 1 |
| [Fwd: Claude Signals Report - Apr 01, 2026 6:08 PM EST](https://mail.google.com/mail/u/0/#all/19d4dd2c425819a6) | 2026-04-02 | 2026-04-02 | 1 |

## Claude chats

| Started | Chat | Prompts | Resume |
|---|---|---|---|
| 2026-09-02 | * Harness Memory : Need a consolidated memory for my harness | 8 | `claude --resume 999bab73` |

## Owed to prod

_Nothing pending for prod._

## Job status entries (19)

| Date | Status | Entry | Anchor |
|---|---|---|---|
| 2026-07-27 | SUCCESSFUL | **Investigate: dev `:8507` "service unavailable" + slow login for team | `docs/mindwealth_ui_job_status.md#L1099` |
| 2026-07-27 | SUCCESSFUL | **Analyze `PORTFOLIO_API_HANDOFF_02.md` + `PORTFOLIO_DATA_ISSUES.md`,  | `docs/mindwealth_ui_job_status.md#L1075` |
| 2026-07-23 | SUCCESSFUL | **Draft reply document to Ahil's "7 items to finalize test suite" emai | `docs/mindwealth_ui_job_status.md#L1218` |
| 2026-07-22 | SUCCESSFUL | **Daily personal-book (`book_id=personal`) snapshot job for future NAV | `docs/mindwealth_ui_job_status.md#L1346` |
| 2026-07-22 | SUCCESSFUL | **Ahil nav_engine.py integrated + live engine verification** — SUCCESS | `docs/mindwealth_ui_job_status.md#L1270` |
| 2026-07-22 | SUCCESSFUL | **New Signals page empty while nav shows 7 — BFF data source fix** — S | `docs/mindwealth_ui_job_status.md#L1246` |
| 2026-07-22 | SUCCESSFUL | **Consolidated "questions for Rohit" — portfolio page backend review** | `docs/mindwealth_ui_job_status.md#L1326` |
| 2026-07-22 | SUCCESSFUL | **Portfolio daily NAV API + configurable sizer notional (v1.8.3)** — S | `docs/mindwealth_ui_job_status.md#L1274` |
| 2026-07-22 | SUCCESSFUL | **Portfolio implementation log — product overview section at top** — S | `docs/mindwealth_ui_job_status.md#L1258` |
| 2026-07-22 | SUCCESSFUL | **Portfolio Backend Remaining Build — Phases 0-9 (config layer, D1 siz | `docs/mindwealth_ui_job_status.md#L1334` |
| 2026-07-22 | SUCCESSFUL | **Ahil NAV analysis deliverables — implementation status refresh** — S | `docs/mindwealth_ui_job_status.md#L1262` |
| 2026-07-22 | PARTIAL | **Portfolio HANDOFF v1.8.2 — API + docs commit and push** — PARTIAL (d | `docs/mindwealth_ui_job_status.md#L1234` |
| 2026-07-22 | SUCCESSFUL | **Portfolio NAV history layer + workbook ingest + nav_engine adapter** | `docs/mindwealth_ui_job_status.md#L1266` |
| 2026-07-21 | SUCCESSFUL | **Portfolio "Could not compute" / BLOCKED $0 for ETFs & indexes (^GSPC | `docs/mindwealth_ui_job_status.md#L1366` |
| 2026-07-20 | SUCCESSFUL | **Portfolio aim & status doc (beginner-friendly)** — SUCCESSFUL | `docs/mindwealth_ui_job_status.md#L1391` |

_4 older entries — see `docs/mindwealth_ui_job_status.md`._
<!-- MEMORY:END generated -->

## Decisions ledger

Every row needs a source. `msg:<id>` points at a mail in `index.jsonl`;
`call`/`doc` are fine too, as long as the origin is named.

| Date | Decision | Source | Code ref |
|---|---|---|---|
| | | | |

## Open questions

`status`: `NOT_ASKED` (we owe Rohit the question) · `ASKED` (sent, waiting) ·
`ANSWERED` (fill the answer source). This table is the "what is communicated,
what is not" ledger — keep it honest.

| # | Question | Asked on | Channel | Status | Answer source |
|---|---|---|---|---|---|
| | | | | | |
