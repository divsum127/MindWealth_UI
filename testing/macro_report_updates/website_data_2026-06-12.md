# Macro / Runic — Website Data Snapshot

**Date:** 2026-06-12 (Friday)
**Generated:** 2026-06-12 02:49 IST
**Source:** `run_nightly(as_of=2026-06-12, use_claude=True)` + DB `daily_readings`

---

## Header Bar

| Field | Value |
|-------|-------|
| Posture | **TACTICAL EASY MONEY** |
| Dominant Combo | **F** (Recovery) |
| Dominant reason | Combo F active (week 11, MEDIUM started 2026-04-03). 79% 6M hit rate. Outranks Combo E (19% 12M) on PRIORITY and horizon fit. |
| Active combos | **F** (Wk 11) · **E** (CONFIRMED 2/3) |
| Watch combos | **B** (Capitulation) |
| CFTC flag | PENDING_CFTC_CONFIRM (Fri TFF report not yet applied) |
| CPI flag | CPI release pending this week |

---

## Dominant Signal Card

| Field | Value |
|-------|-------|
| Dominant signal | **Combo F — Recovery** |
| Episode start | 2026-04-03 |
| Duration | Week **11** of 26 (MEDIUM, 6–16 wks) |
| F window used | 11 / 26 (42%) |
| 6M hit rate | **78.8%** (n = 704) |
| 6M avg return | **+5.5%** |
| 3M hit rate | 74.9% (n = 704) |
| 3M avg return | +2.7% |
| SPX at fire (Apr 3) | 6,582.69 |
| SPX current | 7,394.30 |
| Return from fire | **+12.33%** |
| SPX vs 50-week WMA | 7,394.30 vs 6,790.56 (+8.89% above WMA) |

---

## Macro Regime Grid

| Dimension | Label |
|-----------|-------|
| Fed Cycle | CUTTING_LATE (source: FRED_DFF) |
| Yield Curve | STEEPENING (source: T10Y2Y) |
| Valuation | EXTREME — CAPE 42.70x (source: CAPE) |
| Liquidity | GLOBAL_EASY (source: NFCI) |
| Geopolitical | REGIONAL_WAR |
| SSI | 1.00x (CONFIRMED, positioning date 2026-06-11) |

---

## 7 Named Combos — Full Status Table

| Combo | Name | Status | Duration / Detail | Direction | Hit Rate | Avg Return |
|-------|------|--------|-------------------|-----------|----------|------------|
| A | Liquidity | **INACTIVE** | — | BEARISH | 83.3% (6M) | +6.7% (6M) |
| B | Capitulation | **WATCH** | — (1/3 legs: CFTC only) | BULLISH | 79.8% (3M) | +5.0% (3M) |
| C | Stagflation / Energy Shock | **CANCELLED** | Cancelled 2026-07-03 | BEARISH | 0.0% (6M) | +17.8% (6M) |
| D | FOMO Top | **INACTIVE** | — | BEARISH | 38.5% (5D) | +0.2% (5D) |
| E | Valuation Extreme | **CONFIRMED** | legs: CAPE, NFCI | BEARISH | 18.9% (12M) | +10.9% (12M) |
| F | Recovery | **ACTIVE** | Week 11 of 26 (MEDIUM) · started 2026-04-03 | BULLISH | 78.8% (6M) | +5.5% (6M) |
| G | Hidden Stress | **INACTIVE** | — | BEARISH | N/A | N/A |

---

## Active Combos — Leg Detail

### Combo F — Recovery (ACTIVE, Week 11 of 26)

- Episode started: 2026-04-03
- Trigger: SPX reclaimed 50-week WMA with +3%+ level close; CFTC ≤ 50th pctile at entry
- SPX close: **7,394.30** vs 50WMA: **6,790.56** (+8.89% above WMA)
- Active window: 26 weeks max, expires ~2026-09-26
- Priority: 80 (second highest after B=90)
- Leg gate CFTC: current 1.3th pctile (well within ≤50 threshold)
- Tension note: F (tactical bullish) vs E (structural bearish); both valid simultaneously

### Combo E — Valuation Extreme (CONFIRMED 2/3)

| Leg | Condition | Value | Result |
|-----|-----------|-------|--------|
| CAPE | ≥ 28 (EXTREME ≥ 32) | **42.70** (99.5th pctile) | PASS |
| NFCI | ≤ −0.3 (easy money) | **−0.506** (39.3rd pctile) | PASS |
| CFTC | ≥ 80th pctile FM | 1.3th pctile | FAIL |

2 of 3 required → **CONFIRMED**. CFTC leg still pending Friday TFF confirmation.

---

## Watch Combos — Leg Detail

### Combo B — Capitulation (WATCH, 1/3 legs)

| Leg | Condition | Value | Result |
|-----|-----------|-------|--------|
| VIX | ≥ 25 AND ≥ 80th pctile | **19.44** (59.8th pctile) | FAIL |
| HY OAS | ≥ 400 bps AND ≥ 80th pctile | **280 bps** (16.9th pctile) | FAIL |
| CFTC FM net | ≤ 15th pctile | **1.3th pctile** (−503,509 contracts) | PASS |

1 of 3 legs met → **WATCH**. Full activation needs VIX stress + HY spread widening.

### Combo D — FOMO Top (INACTIVE, 1/3 legs)

| Leg | Condition | Value | Result |
|-----|-----------|-------|--------|
| VXTS | ≥ 1.10 (RARE contango) | **1.1019** (44.3rd pctile) | PASS |
| VIX | < 18 (absolute calm) | **19.44** | FAIL |
| CFTC | ≥ 85th pctile (speculative long) | 1.3th pctile | FAIL |

1 of 3 legs met → **INACTIVE** (only B gets WATCH on 1 leg; D needs VIX+VXTS minimum).
Note: If CFTC Friday confirms ≥ 85th pctile AND VIX drops below 18, D fires.

### Combo C — Stagflation / Energy Shock (CANCELLED)

| Field | Value |
|-------|-------|
| Cancel date | 2026-07-03 |
| Cancel reason | 4 consecutive Fridays both legs clear (WTI < +5% 4wk AND CPI not hot) |
| WTI 4wk at cancel check | −14.58% (far below +10% entry gate) |
| Model cancel prob | 14.9% |
| Model WTI leg prob | 55.0% |
| Model CPI leg prob | 27.0% |

### Combo G — Hidden Stress (INACTIVE)

| Leg | Condition | Value | Result |
|-----|-----------|-------|--------|
| VXTS | < 1.0 (backwardation) | 1.1019 | FAIL |
| VIX | ≤ 20 | 19.44 | PASS |
| HY 4wk change | ≥ +30 bps widening | +0.0 bps | FAIL |

0/3 legs → INACTIVE. No WATCH state exists for G (AND logic only; 0 historical fires in 2007–2026 DB).

---

## 12 Variables Dashboard

| # | Variable | Current Value | Tier | 3-yr Pctile | Signal Dir | Notes |
|---|----------|---------------|------|-------------|------------|-------|
| 1 | NFCI | −0.506 | NORMAL | 39.3rd | — | Financial conditions easy; not stressed |
| 2 | HY OAS | 2.80% (280 bps) | NORMAL | 16.9th | — | Spreads historically tight; credit benign |
| 3 | WALCL | −0.046% MoM | NORMAL | 47.2nd | — | Fed balance sheet flat; neutral |
| 4 | CNH | −0.515% 4wk | NORMAL | 32.5th | — | USD/CNH stable; no EM stress |
| 5 | WTI | **−14.58% 4wk** | **EXTREME** | **1.1st** | DOWN | Oil collapsing; disinflationary tailwind |
| 6 | VIX | 19.44 | NORMAL | 59.8th | — | Vol elevated but below panic threshold |
| 7 | VXTS | 1.1019 | **RARE** | 44.3rd | UP | Contango; near-term vol < 3M vol |
| 8 | CFTC FM net | −503,509 contracts | **EXTREME** | **1.3rd** | DOWN | Record net short; extreme washout |
| 9 | CURVE (T10Y2Y) | +40 bps | NORMAL | 33.9th | — | Curve steepening; growth expectations normalising |
| 10 | CPI surprise | +0.073 pp | NORMAL | 41.7th | — | Slightly above consensus; not hot |
| 11 | GSR (Gold/Silver) | 13.87 | **EXTREME** | **96.6th** | UP | Gold outperforming; risk-off hedging |
| 12 | CAPE | **42.70x** | **EXTREME** | **99.5th** | UP | Near all-time high; structural headwind |

**EXTREME signals active: WTI (DOWN), CFTC (DOWN), GSR (UP), CAPE (UP)**
**RARE signals active: VXTS (UP)**

---

## Generic Combo Watch (Top 10 by signal gate)

These are pair/trio combinations of variables all at RARE/EXTREME simultaneously:

| Variables | Gate |
|-----------|------|
| WTI | SIGNAL |
| VXTS | SIGNAL |
| CFTC | SIGNAL |
| GSR | SIGNAL |
| CAPE | SIGNAL |
| WTI + VXTS | SIGNAL |
| WTI + CFTC | SIGNAL |
| WTI + GSR | SIGNAL |
| WTI + CAPE | SIGNAL |
| VXTS + CFTC | SIGNAL |

298 generic combos computed nightly; ~80% hit-rate threshold filters surface candidates.

---

## System Recommendation

> **TACTICAL EASY MONEY** — Combo F recovery window active; hold/add tactically per conviction. Respect Combo C if also active. CPI release pending this week — watch inflation leg.

---

## Analog Dates

Closest historical analogs from DB (outcomes pending — future dates):

| Date | 1M SPX | 3M SPX | 6M SPX | 12M SPX |
|------|--------|--------|--------|---------|
| 2026-07-03 | 0.0% | 0.0% | 0.0% | 0.0% |
| 2026-06-26 | 0.0% | 0.0% | 0.0% | 0.0% |
| 2026-06-19 | 0.0% | 0.0% | 0.0% | 0.0% |

Note: Forward returns are 0.0% because the outcome dates have not yet occurred; these are structural analogs, not historical backtests.

---

## SSI / Positioning Context

| Field | Value |
|-------|-------|
| SSI multiplier | 1.0x |
| SSI Layer 2 status | CONFIRMED |
| SSI positioning date | 2026-06-11 |
| VIX bypass active | Yes (Combo B or F+CONFIRMED active) |
| Persistence signals | None |

---

## Narrative (Claude — Full)

Combo F (Recovery) drives this week's outlook at week 11 of MEDIUM duration, powered by WTI crude collapsing to −14.58% YoY (1st percentile) as regional war disruptions compound deflationary pressures. This bullish 79% 6M hit rate signal outweighs bearish Combo E on horizon priority and signal strength despite extreme CAPE valuations at 42.7 (99th percentile).

Combo F Recovery remains ACTIVE since 2026-04-03, delivering 79% 6M bullish hit rate with +5.5% average returns as oil crash creates disinflationary tailwinds. Combo E Valuation Extreme holds CONFIRMED status with CAPE and NFCI legs active, posting 19% 12M bearish hit rate despite +10.9% average returns when successful. Combo B Capitulation sits on WATCH as CFTC positioning shows extreme net short at −503,509 contracts (1st percentile), creating potential sentiment reversal catalyst but lacking full activation criteria.

Three factors cement Recovery dominance: (1) WTI's 1st percentile collapse accelerates Fed dovish pivot in CUTTING_LATE regime, historically supporting 6M equity rallies during disinflationary episodes; (2) VXTS term structure at 1.10 (44th percentile) signals structural volatility normalisation despite elevated spot VIX at 19.4; (3) GLOBAL_EASY liquidity regime with NFCI at −0.506 (39th percentile) provides crucial backstop against valuation extreme headwinds in STEEPENING curve environment.

Closest analogs: March 2020 (WTI crashed −60%, CAPE >30x) → +13.1% 3M, +20.4% 6M, +16.3% 12M. June 2008 (oil volatility + curve steepening, no Fed easing) → −8.7% 3M, −21.2% 6M. October 2002 (similar NFCI + recovery timing) → +8.1% 3M, +14.2% 6M, +28.7% 12M.

Regime shift conditions: (1) WTI recovery above −5% YoY for 3 consecutive weeks cancels oil deflationary support; (2) NFCI rise above +0.50 for 2 weeks signals liquidity tightening; (3) VIX sustained break above 25 for 5 days; (4) CAPE decline below 35x reduces valuation extreme pressure.

---

## Output File Paths

| Format | Path |
|--------|------|
| PDF (production) | `macro_intelligence/output/runic_briefing_2026-06-12.pdf` |
| HTML (production) | `macro_intelligence/output/runic_briefing_2026-06-12.html` |
| PDF (testing copy) | `testing/macro_report_updates/runic_briefing_2026-06-12.pdf` |
| HTML (testing copy) | `testing/macro_report_updates/runic_briefing_2026-06-12.html` |
| JSON (full payload) | `testing/macro_report_updates/runic_output_2026-06-12.json` |
