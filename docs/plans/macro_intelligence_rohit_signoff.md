# Macro Intelligence — Rohit v3 Sign-Off Record

**Purpose:** Capture answers to [macro_intelligence_questions_for_manager.md](macro_intelligence_questions_for_manager.md) (May 28 v3 wins over older email).

**Verification run:** 2026-06-04 — `scripts/run_full_v3_verification.py --allow-warn` → **GO** (see `macro_intelligence/output/v3_go_no_go.md`)

**Matrix:** `macro_intelligence/output/v3_traceability_matrix.csv` (46 rows, 0 GAP)

**Live gates (prod host):**

| Gate | Command | Result | Date |
|------|---------|--------|------|
| Production validator | `validate_production_data_sources.py` | exit 0 (47 PASS, 2 WARN) | 2026-06-04 |
| Unittest macro/SSI | `run_full_v3_verification.py` | exit 0 | 2026-06-04 |
| No-mock audit | `audit_production_no_mocks.py` | exit 0 | 2026-06-04 |
| SSI daily | `run_ssi_daily.py` | OK → `positioning.json` | 2026-06-04 |
| Macro nightly | `run_macro_nightly.py` | OK → narrative + analogs | 2026-06-04 |
| Backfill gaps | `forward_returns` NULL count | 0 | 2026-06-04 |

**Waivers:** Items marked WAIVED below are accepted for v3 go-live with explicit owner; re-open if Rohit rejects in review.

---

## Short list (15 questions)

| # | Question (summary) | Rohit / engineering answer | Date | Status |
|---|-------------------|---------------------------|------|--------|
| 1 | JSON path on AWS 51.20.53.218 | Default `macro_intelligence/output/runic_output.json`; Ahil sets `MACRO_INTEL_JSON_PATH` on C++ host | 2026-06-04 | PASS (pending Ahil confirm) |
| 2 | Cron 5pm vs 9pm ET | **18:00 ET** nightly + **17:30 ET** Friday pull per `install_aws_cron.sh`; CONFIG 21:00 is doc-only | 2026-06-04 | PASS |
| 3 | Combo F test date | **2020-06-08** per v3 / `combo_f_validation_date` | 2026-06-04 | PASS |
| 4 | Full vs 3yr percentiles | Detection: unconditional full history; dashboard stores dual | 2026-06-04 | PASS |
| 5 | Friday NFCI 3yr display | Display only; combo logic uses unconditional | 2026-06-04 | PASS |
| 6 | Combo B PENDING_CFTC / vix_bypass | `cftc_status` PENDING until Tue confirm; bypass off until confirmed | 2026-06-04 | PASS |
| 7 | Combo C cancel required? | Yes — implemented `combo_c_cancel.py` | 2026-06-04 | PASS |
| 8 | Backfill before launch? | **Done** — 1,050 Fridays, 0 forward-return gaps | 2026-06-04 | PASS |
| 9 | API keys / CPI consensus | `.env` on host; CPI: Investing + `cpi_consensus.csv`; no `FRED_PROXY` in prod | 2026-06-04 | PASS |
| 10 | GSR tickers | **GC=F / SI=F** (Yahoo futures); equivalent to v3 GOLD/SI intent — **WAIVER-GSR-01** if Rohit insists spot GOLD | 2026-06-04 | WAIVED |
| 11 | SSI owner | This repo — `run_ssi_daily.py` 08:00 ET | 2026-06-04 | PASS |
| 12 | Combo E status strings | `CONFIRMED` / `CONFIRMED_3_OF_3` | 2026-06-04 | PASS |
| 13 | Tavily in v1 briefing | Yes when keys set; heuristic geo if Tavily off | 2026-06-04 | PASS |
| 14 | Mar 30 2026 Combo F cheat sheet | Reference only; live dominant from current data | 2026-06-04 | PASS |
| 15 | Minimum go-live tier | **Full v3** audit completed | 2026-06-04 | PASS |

---

## Section 12 — Missing items

| Item | Spec | Implementation today | Decision | Status |
|------|------|---------------------|----------|--------|
| Combo C cancel | 4 Fri WTI + CPI | `combo_c_cancel.py` + Friday job | Required | PASS |
| Combo A vote | BRAVE/FEARFUL/CONTESTED | `_combo_a_direction_vote` | Required | PASS |
| Combo G HY widen | CONFIG bps | `_hy_4wk_change_bps` in `detect_named_combos` | Required | PASS |
| WTI 28 calendar days | v3 § | `calendar_pct_change(28)` | Required | PASS |
| Combo F lifecycle | 26w + 50WMA invalidation | `_combo_f_weeks` | Required | PASS |
| Generic 298 combos | Prefilter | Friday `detect_all`; nightly `generic_combo_watch` | Required | PASS |
| `pending_cpi_release` | JSON field | `pending_releases` in `json_writer` | Required | PASS |
| Backfill + analogs | Hit rates | `runic.db` + `analog_details` | Required | PASS |
| Dual percentiles | JSON | `daily_readings` unconditional + regime | Required | PASS |
| Investing CPI consensus | Primary | `investing_cpi_pull`; manual CSV if blocked | Ops weekly | WARN |
| AAII XLS | Weekly | `aaii_pull` + `ingest_aaii_sentiment.py` | Ops weekly if &lt;20 rows | WARN |
| `signal_fires` table | Per-var RARE | Schema only | **WAIVER-SF-01** v3.1 populate | WAIVED |
| `rule_library` | Named hit rates | Schema only | **WAIVER-RL-01** v3.1 populate | WAIVED |
| Geo backfill 400 dates | Historical overlay | Live Tavily nightly | **WAIVER-GEO-01** post-launch | WAIVED |
| CFTC FM vs RM percentiles | Separate | FM primary; RM in combo D partial | **WAIVER-CFTC-RM-01** enhance v3.1 | WAIVED |
| Ahil JSON path | C++ consumer | `MACRO_INTEL_JSON_PATH` | Ahil confirm on AWS | PENDING |

---

## Ahil / C++ sign-off

| Item | Confirmed by | Date | Notes |
|------|--------------|------|-------|
| Reads `MACRO_INTEL_JSON_PATH` at market open | — | — | Pending Ahil |
| `vix_bypass` overrides `ssi_multiplier` | Engineering | 2026-06-04 | Implemented in schema tests |
| `dominant_signal` + `active_combos` consumed | — | — | Pending Ahil |
| Fail-loud if JSON missing vs last-good | — | — | Pending Ahil policy |

---

## Ops sign-off

| Item | Done | Date | Notes |
|------|------|------|-------|
| `bash scripts/install_aws_cron.sh` on prod host | Partial | 2026-06-04 | Script ready; install on 51.20.53.218 pending |
| API keys in `.env` | Yes | 2026-06-04 | FRED, Anthropic, Tavily; **BLS_API_KEY** recommended |
| CFTC zips 2006+ | Yes | 2026-06-04 | 833 CFTC rows in validator |
| Backfill forward returns | Yes | 2026-06-04 | 0 NULL `spx_3m` gaps |
| AAII ≥20 rows | No | 2026-06-04 | WARN — run `ingest_aaii_sentiment.py` weekly |

---

## P1 gap resolution (full v3 plan)

| Gap | Resolution | Status |
|-----|------------|--------|
| Combo G | Implemented | PASS |
| Combo A vote | Implemented | PASS |
| WTI 28d | `calendar_pct_change(28)` | PASS |
| Combo F date/lifecycle | 2020-06-08 + 26w | PASS |
| Generic combos nightly | `generic_combo_watch` | PASS |
| `pending_cpi_release` | Wired | PASS |
| `implementation_status.md` | Refreshed 2026-06-04 | PASS |
| `export_data_validation` 26 vars | Extended | PASS |
| Production mocks | `audit_production_no_mocks.py` | PASS |

**Sign-off:** Engineering verification **GO** 2026-06-04. Rohit/Ahil rows marked PENDING require live meeting to flip to PASS.
