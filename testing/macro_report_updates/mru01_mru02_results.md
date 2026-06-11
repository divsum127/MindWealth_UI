# G→B Cascade & Combo B HY Audit Results

**Generated:** 2026-06-06T23:01:56.332013
**Scan:** 2007-01-01 → 2026-07-03

## DB state (persisted combo_fires)

| Combo | Status | Count | Min | Max |
|-------|--------|-------|-----|-----|
| B | WATCH | 89 | 2023-06-09 | 2026-07-03 |

## MRU-01 — G→B cascade (detector rescan)

- B episodes (ACTIVE): **3**
- With prior G within 6 weeks: **0**
- B without G warning: **3**

| B episode start | Nearest prior G | Weeks G→B | Within 6w |
|-----------------|-----------------|-----------|-----------|
| 2012-06-01 | — | — | ❌ |
| 2020-05-01 | — | — | ❌ |
| 2020-07-10 | — | — | ❌ |

## MRU-02 — HY at B episodes

**Recommendation:** keep_400bps

| B start | HY bps | HY pctile | Abs≥400 | Pct≥80 | Dual OK | VIX | All 3 OK |
|---------|--------|-----------|---------|--------|---------|-----|----------|
| 2012-06-01 | 681.7 | None | ✅ | ❌ | ❌ | 26.66 | ❌ |
| 2020-05-01 | 648.8 | None | ✅ | ❌ | ❌ | 37.19 | ❌ |
| 2020-07-10 | 544.1 | None | ✅ | ❌ | ❌ | 27.29 | ❌ |

### Reference dates

- **Pre-Aug 2015** (2015-08-21): HY 618.0 bps, pctile None
- **Pre-Dec 2018** (2018-12-21): HY 455.9 bps, pctile None
- **Pre-COVID** (2020-03-20): HY 850.0 bps, pctile None
- **Oct 2022 bottom** (2022-10-07): HY 427.1 bps, pctile None
