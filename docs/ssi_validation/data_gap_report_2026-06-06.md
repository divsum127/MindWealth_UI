# SSI Validation — Data Gap Report

**Updated: 2026-08-02** (see addenda below; original report dated 2026-06-07)

Only variables with remaining data gaps are listed. Variables that are fully covered are omitted.

---

## Section 1 — SSI Variables

Variables computed into the daily SSI score. Data lives in CSV caches under `macro_intelligence/data/ssi/`.

| Data | Spec Requires | Have | Gap | Fixable? |
|------|--------------|------|-----|----------|
| CNN Fear & Greed | 2011–2026 **stock market** index | **2012-05-25 → today, real/reconstructed CNN F&G** (2026-08-02 free backfill — see addendum): real CNN API 2020-07-14→today + validated community wayback-reconstruction 2012-05-25→2020-07-13. Alternative.me **crypto** proxy remains only for non-trading days (weekends/holidays, ~22% of rows) and the disclosed 2011-01→2012-05-24 gap. | **Mostly fixed free.** Narrow, disclosed residual: 2011-01→2012-05-24 (~16 months) has no free source (zero Wayback CDX snapshots of the CNN F&G page exist before 2012-05-25) — stays empty/proxy, not silently dropped. | **Fixed free** (2026-08-02) for the bulk of the range. Remaining ~16-month gap: Bloomberg CSV export only, no free source found. |

---

## Section 2 — Runic DB Variables

Variables stored in `macro_intelligence/data/runic.db → daily_readings`. Used in the Runic nightly briefing, regime classification, and combo logic.

| Data | Spec Requires | Have | Gap | Fixable? |
|------|--------------|------|-----|----------|
| CFTC Fast Money (FM/RM) | 2006–2026 | 2010-06-18 → 2026-07-03 · 840 rows | 2006–2010 missing (~4 yr) | **No** — CFTC TFF format (FM/RM split) introduced Sep 2009; earlier data physically does not exist |
| HY Credit Spreads OAS | 2006–2026 real OAS | **1996-12-31 → today, real (see 2026-08-02 addendum — free wayback backfill)** | **Fixed free.** 6,620 of 6,627 `PROXY` rows replaced with real ICE BofA OAS via a Wayback Machine snapshot of FRED's own CSV. Only 7 dates (bond-market-only holidays with no wayback print) remain on the old BAA10Y+VIX Model v2 estimate — a disclosed, narrow residual. | **Fixed** (free) — was paid-only as of 2026-07-29; see 2026-08-02 addendum. |
| CPI Surprise | Enough history for 3yr percentile | 2024-01-12 → 2026-07-03 · 27 rows | Only 27 months — 3yr percentile unreliable until mid-2027 | Partial — FRED CPI actuals back to 1947; consensus estimates (needed for "surprise") from Cleveland Fed (free) |

---

## Summary

| Category | Total variables | No gap | Gap — fixable | Gap — paid data only | Gap — structural / impossible |
|----------|----------------|--------|--------------|---------------------|-------------------------------|
| SSI | 6 | 6\* | 0 | 0 | 0 |
| Runic DB | 12 | 10\* | 1 (CPI Surprise) | 0 | 1 (CFTC pre-2010) |
| **Total** | **18** | **16\*** | **1** | **0** | **1** |

\* HY OAS and CNN F&G both moved from "Gap — paid data only" to "No gap" on 2026-08-02 (free
wayback/community backfills — see addenda). Each carries a small disclosed residual not covered by
any free source: HY OAS's 7 orphan dates (0.1% of pre-2023 rows) and CNN F&G's 2011-01→2012-05-24
window (~16 months, zero verifiable Wayback snapshots exist). Neither residual is counted in the
"fixable"/"paid-only" columns above since no further free-source path was found for either.

---

## Addendum — 2026-07-29 (macro regime system fix-to-spec plan)

Follow-up on a status-check thread ("D— need a status check on the 5-regime system before Ahil
can wire regime-conditional leverage into the strategy book"). New findings and free-tier
improvements since the original 2026-06-07 report:

### New finding — FRED relicensed `BAMLH0A0HYM2` to a rolling 3-year window (April 2026)

Live-checked 2026-07-29: FRED's own series page for `BAMLH0A0HYM2` now states *"Starting in
April 2026, this series will only include 3 years of observations. For more data, go to the
source."* Confirmed via direct CSV pull — `fredgraph.csv?id=BAMLH0A0HYM2&cosd=1996-01-01` returns
data starting **2023-07-31 regardless of the requested start date**. This is a new ICE licensing
restriction that postdates the original June report; it explains why the repo's real (non-proxy)
HY rows only start mid-2023 and confirms full pre-2023 history is now **permanently paid-only**
(ICE Data Direct / Bloomberg) at the source, not something a different free API or query
parameter can route around. ALFRED (archival FRED vintages) also requires a paid-tier key to test
properly — no free workaround found.

### Shipped free improvement — HY OAS proxy recalibration (Model v2)

The flat linear proxy (`HY = 2.0528*BAA10Y − 0.1833`, R²=0.40) was replaced with a VIX-amplified
stress-aware calibration, fit on the (now larger, 770-row) real ICE OAS overlap plus 3
independently, publicly documented historical HY OAS peaks (2008 GFC, 2020 COVID, 2022 rate
shock — not a redistribution of the licensed ICE series). Full derivation, formulas, and
per-anchor error rates: `docs/ssi_validation/hy_oas_recalibration_2026-07-29.md`.

Net effect: blow-out understatement reduced from roughly -43%/-20%/-20% (2008/2020/2022) to
roughly -9%/+14%/-20%. **2022 is not meaningfully improved** — that episode was HY-specific
stress without a proportional investment-grade (BAA10Y) move, which this proxy family
structurally cannot see; documented as a known limitation, not oversold as fixed.

`daily_readings` rows remain tagged `signal_tier='PROXY'` — no consumer that already checks this
tag needs to change. Rolling-3yr percentiles were recomputed for the *entire* HY series (both
PROXY and real-tier rows), since real-tier dates before mid-2026 still have a 3-year lookback
window that includes pre-2023-07-13 proxy history.

### Shipped — consumer audit for PROXY handling

Audited every consumer of the `HY` variable (`combo_detector.py`, `portfolio_service._compute_
ceiling`, `four_book_engine.py`, SSI Layer-2 hyg_lqd vote) for `signal_tier=='PROXY'` handling —
this was an open item from the original June report ("ensure PROXY rows are handled correctly").
Full results: `docs/ssi_validation/hy_proxy_consumer_audit_2026-07-29.md`. Headline: `portfolio_
service._compute_ceiling` was not tier-aware and now is (no live behavior change; closes the gap
for future historical/backtest use); two other blind spots in `combo_detector.py` (Combo A HY
leg, Combo G HY leg) are documented but intentionally not fixed, since doing so would retroactively
change historical combo fire counts — flagged as a product decision, not an engineering default.

### Still open / paid-only (unchanged from June report)

- Full pre-2023 real ICE BofA HY OAS history — needs ICE Data Direct or Bloomberg subscription.
  **Superseded 2026-08-02 — see addendum below: a free source was found and applied.**
- CNN Fear & Greed true stock-market history pre-~2025 — no free source (see cnn-pc-eval work item
  for a partial, scoped evaluation of extending free-source component reconstruction to 2019+).
  **Partially superseded 2026-08-02 — see addendum below.**

## Addendum — 2026-08-02 (free-source backfill)

Direct follow-up to the 2026-07-29 addendum's "still open / paid-only" items. Found and applied
free sources for both, closing (or nearly closing) items previously marked paid-data-only.

### HY OAS — Wayback Machine FRED snapshot closes the gap, not just improves it

Found an Internet Archive (Wayback Machine) snapshot (captured 2025-11-04, days before the
April-2026 licensing cutoff) of FRED's own public CSV for `BAMLH0A0HYM2`, containing the
**real** ICE BofA HY OAS series 1996-12-31 → 2025-11-03. Combined with real data already
collected live since 2023-06-09, this gives continuous real coverage 1996-12-31 → today.
Applied via `scripts/backfill_hy_oas_from_wayback.py --apply`:

- 6,620 of 6,627 `PROXY` rows converted to real `NORMAL`/`RARE`/`EXTREME` tiers.
- 327 new dates inserted (present in the real ICE series, had no prior `daily_readings` row).
- 7 dates (bond-market-only holidays, e.g. Good Friday, not observed by the BAA10Y/Fed H.15
  calendar used for the original proxy backfill) have no wayback print — left on the old Model v2
  BAA10Y+VIX estimate, disclosed, not silently dropped.
- The 2026-07-29 Model v2 recalibration (`scripts/recalibrate_hy_oas_proxy.py`) is now
  **superseded** — real data beats any proxy, however improved. Kept in the repo for provenance.

Anchor cross-checks against known public HY OAS peaks all match exactly (real data, not fit):
2008-12-15 = 21.82%, 2020-03-23 = 10.87%, 2022-06-13 = 4.87% (vs Model v2's 4.37% estimate for
the same date — confirms the proxy was still understating even after recalibration).

Full detail: `docs/ssi_validation/hy_oas_wayback_backfill_2026-08-02.md`. Retroactive-effect
addendum: `docs/ssi_validation/hy_proxy_consumer_audit_2026-07-29.md`.

### CNN Fear & Greed — two free sources close most (not all) of the gap

1. **2020-07-14 → today:** root cause was a one-line bug, not a missing source — CNN's own
   unofficial API (`production.dataviz.cnn.io/index/fearandgreed/graphdata`) already returns the
   real CNN methodology score (plus all 7 component sub-scores) but was being called with no
   start-date suffix, so it silently returned only its own short default window. Fixed in
   `src/sentiment_superindex/data/cnn_fear_greed.py::fetch_cnn_history()`.
2. **2012-05-25 → 2020-07-13:** ingested a community-maintained, Wayback-Machine-reconstructed
   dataset (`whit3rabbit/fear-greed-data`), validated against CNN's real live API on 5 overlapping
   dates (4/5 within 0.1–1.0 points) and against 5 independent historical stress-event sanity
   checks (all directionally/magnitude correct).
3. **2011-01 → 2012-05-24 (~16 months): genuinely no free source found** — confirmed via direct
   Wayback CDX query that zero snapshots of the CNN F&G page exist before 2012-05-25. This narrow
   window stays on the old crypto-index proxy, disclosed, not silently dropped.

Full detail: `scripts/backfill_cnn_feargreed_free_sources.py`,
`docs/ssi_validation/cnn_fg_wayback_backfill_2026-08-02.md`.

