# SSI Validation — Data Gap Report

**Updated: 2026-06-07**

Only variables with remaining data gaps are listed. Variables that are fully covered are omitted.

---

## Section 1 — SSI Variables

Variables computed into the daily SSI score. Data lives in CSV caches under `macro_intelligence/data/ssi/`.

| Data | Spec Requires | Have | Gap | Fixable? |
|------|--------------|------|-----|----------|
| CNN Fear & Greed | 2011–2026 **stock market** index | 2018-02-01 → 2026-06-06 · 3,052 rows (Alternative.me **crypto** F&G) | Wrong index. Cache is crypto sentiment, not CNN stock market F&G. Also missing 2011–2018. | Bloomberg CSV export only — no free source exists |

---

## Section 2 — Runic DB Variables

Variables stored in `macro_intelligence/data/runic.db → daily_readings`. Used in the Runic nightly briefing, regime classification, and combo logic.

| Data | Spec Requires | Have | Gap | Fixable? |
|------|--------------|------|-----|----------|
| CFTC Fast Money (FM/RM) | 2006–2026 | 2010-06-18 → 2026-07-03 · 840 rows | 2006–2010 missing (~4 yr) | **No** — CFTC TFF format (FM/RM split) introduced Sep 2009; earlier data physically does not exist |
| HY Credit Spreads OAS | 2006–2026 real OAS | 2023–2026 real (163 rows) + 1997–2026 BAA10Y proxy · R²=0.40 | Proxy explains only 40% of OAS variance. Understates blow-outs in 2008/2020/2022. 3yr percentile skewed in stress regimes. | Paid data only — Bloomberg terminal or ICE Direct |
| CPI Surprise | Enough history for 3yr percentile | 2024-01-12 → 2026-07-03 · 27 rows | Only 27 months — 3yr percentile unreliable until mid-2027 | Partial — FRED CPI actuals back to 1947; consensus estimates (needed for "surprise") from Cleveland Fed (free) |

---

## Summary

| Category | Total variables | No gap | Gap — fixable | Gap — paid data only | Gap — structural / impossible |
|----------|----------------|--------|--------------|---------------------|-------------------------------|
| SSI | 6 | 5 | 0 | 1 (CNN F&G) | 0 |
| Runic DB | 12 | 9 | 1 (CPI Surprise) | 1 (HY OAS) | 1 (CFTC pre-2010) |
| **Total** | **18** | **14** | **1** | **2** | **1** |

