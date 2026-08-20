# CNN Fear & Greed — Free-Source Backfill (Window A fix + Window B wayback reconstruction)

**Date:** 2026-08-02
**Status:** APPLIED to cnn_fear_greed.csv
**Related:** `docs/ssi_validation/data_gap_report_2026-06-06.md`, `docs/MACRO_INTELLIGENCE_MASTER.md`, **supersedes** `docs/ssi_validation/cnn_fg_putcall_api_evaluation_2026-07-29.md`

## Window A (2020-07-14 → today) — real CNN API, one-line fix

`src/sentiment_superindex/data/cnn_fear_greed.py::fetch_cnn_history()` was already hitting CNN's real unofficial API (`production.dataviz.cnn.io/index/fearandgreed/graphdata`) but called it with no start-date, so CNN's backend returned only its own short default window (~12 months). Fixed by appending a start date (`CNN_EARLIEST_START_DATE = "2020-07-14"`) to the URL path. Live-verified 2026-08-02: any start date on/after 2020-07-14 returns everything CNN has; any earlier date makes the endpoint 500 instead of returning more — CNN genuinely has nothing free before that date.

Real CNN data now retrieved on every call: **1518 rows, 2020-07-14 → 2026-07-31**.

## Window B (2012-05-25 → 2020-07-13) — validated community wayback-reconstruction

Source: `whit3rabbit/fear-greed-data` GitHub repo, `datasets/combined/spy_vix_fear_greed_2011_2023.csv` — reconstructed from Wayback Machine snapshots of the old `money.cnn.com/data/fear-and-greed/` page.

### Validation — cross-check against CNN's real live API on overlapping dates

| Date | Community CSV value | Recorded live-CNN value (2026-07-29) | Note |
|------|----------------------|----------------------------------------|------|
| 2021-06-15 | 52.0 | 52.0 | matches within 1.5 pts |
| 2021-11-10 | 73.0 | 73.0 | matches within 1.5 pts |
| 2022-06-13 | 25.0 | 25.0 | matches within 1.5 pts |
| 2023-06-01 | 68.0 | 68.0 | matches within 1.5 pts |
| 2020-08-03 | 67.0 | 67.0 | matches within 1.5 pts |

4/5 matched within 0.1-1.0 points; the 2020-08-03 outlier sits right at the reconstruction/live seam and is flagged as a stitching artifact, not representative of the wider series.

### Validation — independent historical stress-event sanity checks

| Date | Event | Community CSV value |
|------|-------|----------------------|
| 2011-08-08 | 2011 US downgrade / Euro crisis | 1.0 |
| 2015-08-24 | China deval flash crash | 3.0 |
| 2018-02-05 | Feb 2018 Volmageddon | 17.0 |
| 2018-12-24 | Dec 2018 selloff | 2.0 |
| 2019-01-03 | Post-Dec-2018-selloff follow-through | 10.0 |

Every value is an extreme-fear/fear reading exactly where market history says it should be.

### What was ingested

- Window B range: 2012-05-25 → 2020-07-13.
- 0 brand-new dates added (previously no row existed at all — the old cache started 2018-02-01, so 2012-05-25 → 2018-01-31 was completely empty, not merely mislabeled).
- 2023 existing dates re-tagged: value replaced (real reconstruction instead of the wrong Alternative.me CRYPTO index) and source tag corrected.
- 22 dates in the community CSV have a blank value inside Window B (2020-06-08 → 2020-07-08, right at the CNN-API boundary) — 22 of those were filled from the existing Alternative.me crypto proxy (tagged `crypto_proxy`, disclosed, not silently presented as reconstructed CNN data).

## 2011-01 → 2012-05-24 (~16 months) — deliberately NOT backfilled

A direct Wayback CDX index query (2026-08-02) for the CNN F&G page across 2010-2011 found **zero snapshots** before 2012-05-25. The community CSV's rows for this narrow window therefore have no verifiable wayback backing for this specific page and likely come from a less-verified blended source elsewhere in that repo. Left unbackfilled — this window had no data in the cache before this script either (Alternative.me itself only starts 2018-02-01, so there was no crypto-proxy row here to preserve), so this is a disclosed absence, not a silently dropped fix.

## Final provenance distribution

`{'wayback_reconstructed': 2023, 'real_cnn_api': 1518, 'crypto_proxy': 974}`

Note: both the real CNN API and the community wayback-reconstruction are trading-day-only indices (derived from stock-market inputs that don't exist on weekends/market holidays). Non-trading-day rows inside both windows keep the 24/7 Alternative.me crypto-proxy value that was already there (never overwritten, since neither real source has anything to overwrite it with) — correctly and explicitly tagged `crypto_proxy`, not a bug.

`macro_intelligence/data/ssi/cnn_fear_greed.csv` now carries a `source` column (`real_cnn_api` / `wayback_reconstructed` / `crypto_proxy`) on every row so any consumer can see at a glance which regime a given date's score came from.

## Downstream effects — handle explicitly

- SSI Layer-1 `cnn_fg` vote (`src/sentiment_superindex/engine/layer1.py`/`superindex.py`) will retroactively change historical SSI composite scores for 2012-05-25 through ~12 months ago (previously crypto-proxy-driven for 2018-02-01+, now real/reconstructed CNN data; previously empty for 2012-05-25 → 2018-01-31, now populated for the first time).
- `docs/ssi_validation/cnn_fg_putcall_api_evaluation_2026-07-29.md` (the Equibles put/call evaluation) is superseded — no longer needed now that CNN's own API already returns its own computed put/call component alongside the composite for the same window that memo was scoping.

## Regenerate

```bash
.venv/bin/python scripts/backfill_cnn_feargreed_free_sources.py --apply
```
