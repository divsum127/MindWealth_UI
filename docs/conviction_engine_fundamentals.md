# Conviction Engine — Fundamental Agent (Status & Operations)

This document describes how the **fundamental conviction** layer works today, what we **assume**, and how to **run and verify** it. It aligns with the implementation plan at `.cursor/plans/conviction_engine_79da0f8e.plan.md` and the v5 PDF conceptually (batch overlay + JSON store); the PDF is not modified in-repo.

## Current status (verified in this workspace)

- **Entry point:** `scripts/update_conviction_fundamentals.py` — scheduled job to pull **yfinance** data, update `conviction_store/{TICKER}.json`, optionally refresh overlay CSVs under `conviction_store/overlays/`.
- **Data path:** `fetch_yfinance_fundamentals` → `fundamentals_enriched.fetch_and_compute_fundamentals` (quarterly statements, TTM sums, trailing P/E series, dividend stats, retries on thin `info`).
- **Scoring:** `full_recalculation` / `daily_update` in `src/conviction_engine/engine.py`; rules in `src/conviction_engine/scoring.py`.
- **Last full run:** `--mode full --write-overlays` for **166** tickers — batch **status completed, 0 thrown errors**; **no `fetch_errors`** returned on ticker results.
- **Equity scores (approx. 112 scored names):** `conviction_score` range about **-11 to +4.5**; **BQ raw** about **-7 to +8**. Counts exactly at **-1 / 0 / +1** are small (on the order of ~7–10 each), i.e. scores are **not** mostly stuck at 0 or 1.
- **Overlay contract:** Original `trade_store` CSVs unchanged; overlays appended alongside (e.g. `*_conviction.csv`).

## Architecture (batch)

1. Discover tickers from latest `trade_store/US` signal files (+ optional universe / flags).
2. Fetch enriched fundamentals per ticker (`info` + mapped fields + non-fatal `errors` list).
3. **Full:** refresh static BQ, copy fundamentals into record, run `daily_update` for valuation fields. **Daily:** refresh price-sensitive fields from latest fetch.
4. If `--write-overlays`, run `apply_to_signal_file` on latest signal sources.

## Key modules

| Role | File                                                         |
| ---- | ------------------------------------------------------------ |
| CLI  | `scripts/update_conviction_fundamentals.py`                |
| Orchestration + fetch | `src/conviction_engine/fundamentals.py`             |
| Enriched yfinance      | `src/conviction_engine/fundamentals_enriched.py`   |
| Engine API             | `src/conviction_engine/engine.py`                       |
| Scoring / gates        | `src/conviction_engine/scoring.py`                       |
| Tests                  | `tests/test_conviction_engine.py`                       |

## Assumptions

1. **Primary source** for automated fundamentals is **yfinance**; the JSON / overlay **shape** is stable so other providers can supply the same fields later.
2. **Non-equities** (ETF, index, FX, crypto) get **no** numeric equity conviction score in the same sense; gating uses asset type + `NOT_APPLICABLE` where appropriate.
3. **`pe_20y_array`** is a **legacy name**: the implementation builds a **recent trailing P/E history** from rolling four-quarter EPS vs spot prices, not a full multi-decade Macrotrends series.
4. **Subjective BQ items** (CEO, moat, etc.) score **0** unless **manual overrides** are set — consistent with an analyst workflow in the PDF.
5. **Valuation tax** is non-positive, **capped at -5** total; extreme EV/revenue floor applies at the **top EV/rev tier** only.
6. **`heldPercentInsiders` / `insider_pct`** is normalized to a **0–100 percent** scale for auto-BQ (e.g. `0.065` → `6.5`) so insider scoring matches `_score_insider`.

## Implementation notes (recent)

- **Auto BQ** (`compute_bq_components_auto`) with **fallback** to legacy `compute_bq_components` when every auto component is zero (sparse data).
- **Retries** when `Ticker.info` is empty or flaky.
- **Business type:** e.g. “Software – Infrastructure” not misclassified as income purely on the word “infrastructure”; dividend yield normalization for yfinance percent vs decimal.
- **`fd_direction`:** inferred from revenue growth and gross margin trend when not overridden; `_copy_known_fields` no longer resets it to a stale default.
- **`insider_pct`:** stored on **0–100** scale after fetch for consistent `_score_insider` thresholds.

## How to run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Full refresh + overlays
.venv/bin/python scripts/update_conviction_fundamentals.py --mode full --write-overlays

# Price-sensitive only
.venv/bin/python scripts/update_conviction_fundamentals.py --mode daily --write-overlays
```

## How to verify

```bash
.venv/bin/python -m unittest tests.test_conviction_engine -v
```

Inspect JSON under `conviction_store/` for `conviction_score`, `bq_raw`, `valuation_tax`, `fetch_errors`. Successful runs should show **`fetch_errors`: []** or absent; batch JSON should report **`errors`: 0**.

## Gaps vs PDF (explicit)

- No live `trade_arrival_analysis` dispatcher in-repo; integration is **batch CSV overlay**.
- No replacement for **manual** 15-dimension analyst scores except overrides.
- No external **long-history PE** vendor unless added later.

---

*Update this file when scoring or fetch behavior changes materially.*
