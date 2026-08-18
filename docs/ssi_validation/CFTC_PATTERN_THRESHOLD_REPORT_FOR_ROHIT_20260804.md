# CFTC Positioning Pattern Thresholds — Experiment Results for Sign-Off

---

## 1. Purpose

Grid-search results for **SQUEEZE** (FM low + RM high) and **LIQUIDITY EXIT** (RM low + FM high) before locking production Sentiment Layer 3 flags. **Display/alert only** — not SSI sizing gates (per 2 Aug email you sent).

---

## 2. Data & methodology

| Item | Value |
|------|-------|
| CFTC Fast Money through | **2026-07-28** (Tuesday position date) |
| CFTC Real Money through | **2026-07-28** |
| Percentile window | 156 weeks (~3 years), rolling |
| Backtest start | 2006-01-01 |
| Forward returns | S&P 500 at 4w / 8w / 12w trading days |
| Grid step | 5 percentile points |
| SQUEEZE JSON | `03_squeeze_grid_20260804.json` |
| LIQUIDITY EXIT JSON | `04_liquidity_exit_grid_20260804.json` |

**SQUEEZE:** FM pctile < X AND RM pctile > Y (same week).

**LIQUIDITY EXIT:** RM pctile < X AND FM pctile > Y.

LIQUIDITY EXIT **4w down %** = share of episodes with negative 4w SPX return. SQUEEZE **12w win %** = share with positive 12w SPX return.

---

## 3. Executive summary

1. **SQUEEZE** is bullish context — best Sharpe (n≥50): **FM<20, RM>45** (n=125, 12w avg +3.3174%, Sharpe 1.1752, win 77.5%).
2. PDF default FM<30/RM>50: n=170, 12w avg +2.6634%, Sharpe 0.8782 — valid but less sharp than FM<20/RM>45.
3. **LIQUIDITY EXIT** RM<30/FM>60: n=116, 4w SPX-down 35.34%, 12w avg +2.8429% — modest stress flag, not a strong short.
4. Patterns are **common** (~5–10 fires/year) — use as context flags only.

### Recommended options

| Pattern | Option A (sharper) | Option B (PDF / more frequent) |
|---------|-------------------|-------------------------------|
| SQUEEZE | FM **< 20**, RM **> 45** (Sharpe 1.1752) | FM **< 30**, RM **> 50** (n=170, Sharpe 0.8782) |
| LIQUIDITY EXIT | RM **< 25**, FM **> 55** (see §5) | RM **< 30**, FM **> 60** (n=116, 4w down 35.34%) |

---

## 4. SQUEEZE heatmap — 12w avg SPX % / Sharpe

| FM < | RM>40 | RM>45 | RM>50 | RM>55 | RM>60 | RM>65 |
|------|------|------|------|------|------|------|
| 15 | 3.0529% / 1.057 | 3.1777% / 1.0925 | 3.1825% / 1.07 | 3.0791% / 1.0215 | 3.1236% / 1.0097 | 3.034% / 0.9398 |
| 20 | 3.2279% / 1.1526 | 3.3174% / 1.1752 | 3.3295% / 1.1619 | 3.2581% / 1.1212 | 3.2367% / 1.0806 | 3.1561% / 1.0182 |
| 25 | 3.0045% / 1.0184 | 3.0704% / 1.0324 | 3.0781% / 1.0139 | 3.0121% / 0.9808 | 2.8851% / 0.903 | 2.7436% / 0.8333 |
| 30 | 2.6982% / 0.9123 | 2.7143% / 0.9105 | 2.6634% / 0.8782 | 2.5981% / 0.8491 | 2.3708% / 0.7478 | 2.1971% / 0.6698 |
| 35 | 2.5421% / 0.7988 | 2.5515% / 0.7954 | 2.5287% / 0.7748 | 2.4262% / 0.7356 | 2.2238% / 0.6511 | 2.0415% / 0.5763 |

### Top SQUEEZE cells by 12w Sharpe (n ≥ 50)

| FM < | RM > | n | 4w avg | 4w win % | 12w avg | 12w win % | 12w Sharpe |
|------|------|---|--------|----------|---------|-----------|------------|
| 20 | 45 | 125 | 0.5872 | 63.2 | 3.3174 | 77.5 | 1.1752 |
| 20 | 50 | 118 | 0.7415 | 65.25 | 3.3295 | 77.88 | 1.1619 |
| 20 | 40 | 130 | 0.6246 | 64.62 | 3.2279 | 76.0 | 1.1526 |
| 20 | 55 | 114 | 0.7815 | 65.79 | 3.2581 | 77.06 | 1.1212 |
| 15 | 45 | 92 | 0.4542 | 61.96 | 3.1777 | 78.16 | 1.0925 |
| 20 | 60 | 107 | 0.7665 | 65.42 | 3.2367 | 75.49 | 1.0806 |
| 15 | 50 | 85 | 0.6575 | 64.71 | 3.1825 | 78.75 | 1.07 |
| 15 | 40 | 96 | 0.5151 | 63.54 | 3.0529 | 75.82 | 1.057 |
| 25 | 45 | 152 | 0.5561 | 65.79 | 3.0704 | 77.4 | 1.0324 |
| 15 | 55 | 82 | 0.716 | 65.85 | 3.0791 | 77.92 | 1.0215 |
| 25 | 40 | 157 | 0.5881 | 66.88 | 3.0045 | 76.16 | 1.0184 |
| 20 | 65 | 99 | 0.8143 | 65.66 | 3.1561 | 73.4 | 1.0182 |

---

## 5. LIQUIDITY EXIT — top cells (RM ≤ 35, FM ≥ 45)

| RM < | FM > | n | 4w avg | 4w down % | 12w avg | Median DD |
|------|------|---|--------|-----------|---------|-----------|
| 35 | 45 | 172 | 0.8228 | 33.14 | 2.7615 | -0.0161 |
| 35 | 50 | 160 | 0.6588 | 35.0 | 2.4619 | -0.4434 |
| 30 | 45 | 156 | 0.7126 | 33.33 | 2.9085 | 0.0996 |
| 35 | 55 | 146 | 0.6401 | 34.25 | 2.5948 | -0.0811 |
| 30 | 50 | 145 | 0.5789 | 35.17 | 2.6529 | -0.0563 |
| 25 | 45 | 134 | 0.7417 | 34.33 | 3.1469 | 0.1485 |
| 30 | 55 | 131 | 0.5496 | 34.35 | 2.8214 | 0.0525 |
| 35 | 60 | 129 | 0.611 | 35.66 | 2.6794 | -0.0563 |
| 25 | 50 | 124 | 0.5837 | 36.29 | 2.8128 | -0.0811 |
| 30 | 60 | 116 | 0.5472 | 35.34 | 2.8429 | 0.0492 |

### PDF default RM<30, FM>60

- **4w:** n=116, avg 0.5472%, down 35.34%, Sharpe 0.407
- **8w:** n=116, avg 1.3558%, down 37.07%, Sharpe 0.5679
- **12w:** n=116, avg 2.8429%, down 29.31%, Sharpe 0.8341

---

## 6. Sign-off

**SQUEEZE:** FM < ___ , RM > ___  (A: 20/45 · B: 30/50)

**LIQUIDITY EXIT:** RM < ___ , FM > ___  (A: 25/55 · B: 30/60)

---

## 8. Spot check (2026-08-04)

Latest COT position date **2026-07-28**: FM pctile **67.3**, RM pctile **60.9**.

| Pattern | Threshold | Fires today? |
|---------|-----------|--------------|
| SQUEEZE | FM<20, RM>45 | No |
| SQUEEZE | FM<30, RM>50 | No |
| LIQUIDITY EXIT | RM<25, FM>55 | No |
| LIQUIDITY EXIT | RM<30, FM>60 | No |

Neither pattern active at current prints — consistent with mid-range positioning.

---

## 9. Reproduce

```bash
cd MindWealth_UI
.venv/bin/python -c "from src.sentiment_superindex.analysis.cftc_grid import run_and_report; run_and_report('2006-01-01')"
.venv/bin/python scripts/compile_cftc_pattern_threshold_report.py
```
