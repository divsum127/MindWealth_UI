# Macro Variable Threshold Validation: Testing v2 Results

I ran the full threshold validation experiment across all 12 macro variables plus named combo gates B, F, E, and D. The goal was simple: check whether our current RARE/EXTREME cutoffs in `CONFIG.yaml` still produce the best probability-weighted (PW) forward SPX returns, or whether a different threshold would clear Rohit's four success bars (PW excess +2pp vs current, n≥5, hit≥60%, hostile-regime slice OK).

## 1. The short version

| Phase | What we did | Outcome |
|-------|-------------|---------|
| P1 | Normalized 220 legacy 0–1 percentile rows; fixed `per_variable_threshold_sweep.py` bands to 0–100 | Scale bug fixed; 12/12 vars now have events in corrected sweep |
| P2 | Built and ran `threshold_sweep_v2.py` on all 12 variables | 12 JSONs + `SUMMARY.json` written |
| P3 | Combo B/F/E/D gate sweeps via leg replay on `daily_readings` | 4 combo JSONs written |
| P4 | This report | See tables below |

**Bottom line:** Most CONFIG thresholds are confirmed at same-side alternatives. **WTI down-side** improves at looser cut (−15% 4wk) but up-side RARE stays weak. Combo B strict 3-of-3 now shows **n=9** at current gates after fixing HY leg to CONFIG OR (was AND in leg replay).

## 2. Method, instruments, and test specification

I ran this as a single-variable isolation backtest: for each macro input, I ask whether a different RARE/EXTREME cutoff would produce better probability-weighted (PW) forward SPX returns than the current `CONFIG.yaml` value.

### 2a. Method

| Step | Detail |
|------|--------|
| Event definition | **First crossing:** variable enters a threshold band from outside the band |
| Cooldown | 5 calendar days between events (avoids re-counting one prolonged episode) |
| Forward returns | SPX (`^GSPC`, Yahoo Finance) measured in **NYSE trading days** |
| Horizons tested | 1M=21d, 3M=63d, 6M=126d, 9M=189d, 12M=252d |
| Return framing | Hit rate, avg win, avg loss, PW expected = (hit × avg_win) + ((1-hit) × avg_loss) |
| Benchmarks (drift) | +0.5% (1M), +2.5% (3M), +5.0% (6M), +7.5% (9M), +10.0% (12M) |
| Excess | PW expected minus benchmark at that horizon |
| Hostile slice | Subset where `fed_cycle` ∈ {HIKING_EARLY, HIKING_LATE, TIGHTENING} OR `curve_regime`=INVERTED (`macro_regime_log`) |
| Verdict methodology | Analyst judgment per variable: combo role, n, hit/avg SPX, economic meaning — not hard Δ/hit gates |
| Data store | `macro_intelligence/data/runic.db` → `daily_readings` (raw_value, unconditional_pctile, meta_json) |
| Script | `scripts/threshold_sweep_v2.py` (run date 2026-06-15) |
| P1 fix | Normalized 220 legacy percentile rows from 0–1 scale to 0–100 before sweep |

### 2b. Duration and range

| Item | Value |
|------|-------|
| Event scan start | **1990-01-01** (script default `--start`) |
| Event scan end | Latest date in `daily_readings` per variable (mostly **2026-07-03**) |
| SPX history for forwards | Pulled via `fetch_yahoo_close('^GSPC')` aligned to NYSE session calendar |
| Primary horizon per variable | VIX/HY/CFTC/NFCI/WALCL/CNH/GSR/VXTS/CPI/CURVE → **3M**; WTI → **6M**; CAPE → **12M** |
| Combo B validated horizon | **3M** bullish |
| Combo F validated horizon | **6M** bullish |
| Combo E validated horizon | **12M** bearish |
| Combo D validated horizon | **5D** bearish |

### 2c. Band ranges swept (summary)

| Variable | Bands tested | Current RARE (CONFIG) | Current EXTREME (CONFIG) |
|----------|-------------|------------------------|---------------------------|
| VIX | 15, 18, 20, **25**, 28, 30, **35**, 40 + pctile 65–79 | level ≥25 AND pctile ≥80 | level ≥35 AND pctile ≥95 |
| HY | 300–600 bps + pctile 70/75 | OAS ≥400 OR pctile ≥80 | OAS ≥500 OR pctile ≥95 |
| CFTC | Short ≤30/20/**15**/10/**5**; Long ≥70/80/**85**/90/**95** | pctile ≤15 or ≥85 | pctile ≤5 or ≥95 |
| NFCI | Easy/tight at ±0.1, ±0.2, **±0.3**, ±0.5, ±0.8 SD | pctile ≤20/≥80 or SD ±0.3 | pctile ≤5/≥95 or SD ±0.8 |
| WALCL | Expand/contract at 0.3, 0.5, **0.8**, 1.5, **2.0**, 3.0% MoM | \|MoM\| ≥0.8% | \|MoM\| ≥2.0% |
| WTI | Down/up at 3, 5, 6, 8, 10, **15**% 4wk | \|4wk\| ≥6% | \|4wk\| ≥10% |
| CNH | ±0.5, ±1.0, **±1.5**, ±2.5, **±3.5**% 4wk | \|4wk\| ≥1.5% | \|4wk\| ≥3.5% |
| GSR | Up at 2–10% 4wk | \|4wk\| ≥5% | \|4wk\| ≥8% |
| VXTS | Backward ≥1.02–1.20; Contango ≤0.80–**0.95** | ratio ≤0.95 or ≥1.10 | ratio ≤0.85 or ≥1.20 |
| CAPE | High 22–38; Low **16**, 14, **12** | level ≥28 or ≤16 | level ≥32 or ≤12 |
| CPI | Hot surprise +0.05 to +0.60 pp | \|surprise\| ≥0.2pp | \|surprise\| ≥0.4pp |
| CURVE | Invert −10 to −100 bps; Steepen +5 to +40 bps | spread ≤−30 or steepen ≥15 | spread ≤−80 or steepen ≥40 |

Full per-band hit rates at all five horizons are in the appendix sections below.


## 3. Infrastructure fixes (P1)

| Fix | Before | After |
|-----|--------|-------|
| DB percentile normalization | 220 rows at 0–1 scale | 0 legacy rows remaining; all multiplied by 100 |
| `per_variable_threshold_sweep.py` bands | 0.70–0.79 (0–1 scale), 11 vars | 70–79 (0–100 scale), 12 vars incl. CURVE |
| Corrected regression sweep | VIX high_80_plus n=30 (partial) | VIX high_80_plus n=30; CURVE inverted_80_plus n=7 |

Legacy rows by variable before migration:

| Variable | Legacy rows fixed |
|----------|-------------------|
| VIX | 63 |
| NFCI | 48 |
| GSR | 25 |
| WTI | 19 |
| CFTC | 17 |
| CNH | 17 |
| WALCL | 15 |
| HY | 8 |
| VXTS | 8 |

## 4. Per-variable: current vs best threshold

Metrics are at each variable's **primary validation horizon** (3M for most; WTI 6M; CAPE 12M). Each variable may have multiple RARE or EXTREME bands (e.g. WTI up/down, CFTC short/long). **Best alt** = best same-side swept alternative at the same tier (n≥5), ranked by PW excess for bull bands and by bear hit rate then excess for bear bands.

**Verdict** = analyst judgment (not a hard Δ/hit gate): whether the best alt materially improves CONFIG given the variable's role in combos, sample size, direction (bull/bear), and whether PW excess is economically meaningful (e.g. bearish rows where SPX rallied despite low bear hit).

### 4a. RARE thresholds (CONFIG vs best RARE alternative)

**Hit% ↓** = bearish hit rate (SPX down). **Avg SPX** = mean forward return at primary horizon; for bearish rows, high Avg SPX with 0% hit means the signal missed (SPX rallied). Best alt compares **same-side** bands only (e.g. CAPE high vs high, not high vs low).

**CONFIG RARE** and **CONFIG EXTREME** columns show the current production cutoffs from `CONFIG.yaml` for that band side (unchanged on Best alt rows so you can compare swept alternatives against what we run today).

**Raw returns CSV:** `section_4a_rare_threshold_raw_returns.csv` — one row per first-crossing event (4,169 rows) for all RARE-tier and alternative bands (excludes CONFIG EXTREME-only bands). Columns include event date, variable reading, SPX forward returns at 1M/3M/6M/9M/12M, benchmarks, and hostile-regime flags.

| Variable | Hz | Dir | Role | Band | CONFIG RARE | CONFIG EXTREME | n | Hit% | Avg SPX | PW excess | Verdict |
|----------|-----|-----|------|------|-------------|----------------|---|------|---------|-----------|---------|
| CAPE | 12M | Bear | Current | CAPE_high_28 | high ≥28 | high ≥32 | 7 | 14.3% ↓ | +19.50% | +9.50% | |
| CAPE | 12M | Bear | Best alt | CAPE_high_30 | high ≥28 | high ≥32 | 11 | 27.3% ↓ | +11.71% | +1.71% | Keep CONFIG — Combo E uses CAPE≥28; alt high_30 raises bear hit to 27% but still poor timing signal and lowers structural severity |
| CAPE | 12M | Bull | Current | CAPE_low_16 | low ≤16 | low ≤12 | 2 | 100.0% | +18.86% | +8.86% | |
| CAPE | 12M | Bull | Best alt | — | low ≤16 | low ≤12 | n/a | n/a | n/a | n/a | Keep CONFIG — only 2 deep-value episodes; threshold defines historic capitulation bucket, not optimizable |
| CFTC | 3M | Bull | Current | CFTC_short_15 | pctile ≤15 | pctile ≤5 | 38 | 63.2% | +1.61% | −0.89% | |
| CFTC | 3M | Bull | Best alt | CFTC_short_10 | pctile ≤15 | pctile ≤5 | 30 | 70.0% | +3.23% | +0.73% | Keep CONFIG — contrarian short-squeeze bucket (63% bull hit); loosening to ≤10 adds fires with only +1.6pp excess — not worth diluting capitulation purity |
| CFTC | 3M | Bear | Current | CFTC_long_85 | pctile ≥85 | pctile ≥95 | 39 | 20.5% ↓ | +4.77% | +2.27% | |
| CFTC | 3M | Bear | Best alt | CFTC_long_90 | pctile ≥85 | pctile ≥95 | 35 | 17.1% ↓ | +5.33% | +2.83% | Keep CONFIG — crowded-fast-money warning for Combo E; bear hit stays ~20% at 3M (structural, not timing); long_90 not materially better |
| CNH | 3M | Bull | Current | CNH_down_1.5pct | \|4wk\| ≥1.5% (down) | \|4wk\| ≥3.5% (down) | 17 | 82.4% | +5.08% | +2.58% | |
| CNH | 3M | Bull | Best alt | CNH_down_1.0pct | \|4wk\| ≥1.5% (down) | \|4wk\| ≥3.5% (down) | 41 | 85.4% | +4.54% | +2.04% | Keep CONFIG — yuan-strength shock already 82% bull hit at 3M; looser 1.0% trades 0.5pp excess for less specific geo signal |
| CNH | 3M | Bear | Current | CNH_up_1.5pct | \|4wk\| ≥1.5% (up) | \|4wk\| ≥3.5% (up) | 22 | 18.2% ↓ | +3.35% | +0.85% | |
| CNH | 3M | Bear | Best alt | CNH_up_0.5pct | \|4wk\| ≥1.5% (up) | \|4wk\| ≥3.5% (up) | 46 | 30.4% ↓ | +2.78% | +0.28% | Keep CONFIG — yuan weakness is geo-stress marker but poor SPX down-timing at 3M; no alt fixes economic story |
| CPI | 3M | Bear | Current | CPI_hot_0.20 | \|surprise\| ≥0.20pp | \|surprise\| ≥0.40pp | 1 | 0.0% ↓ | +5.95% | +3.45% | |
| CPI | 3M | Bear | Best alt | — | \|surprise\| ≥0.20pp | \|surprise\| ≥0.40pp | n/a | n/a | n/a | n/a | Defer — single event at 0.20pp; need more CPI surprise releases before any threshold move |
| CURVE | 3M | Bear | Current | CURVE_invert_30bps | spread ≤−30bps | spread ≤−80bps | 10 | 50.0% ↓ | −0.60% | −3.10% | |
| CURVE | 3M | Bear | Best alt | CURVE_invert_20bps | spread ≤−30bps | spread ≤−80bps | 7 | 57.1% ↓ | +0.84% | −1.66% | Keep CONFIG — −30bps inversion is standard recession watch; milder −20bps does not improve recession-timing hit enough to matter |
| CURVE | 3M | Bull | Current | CURVE_steepen_15bps | steepen ≥15bps (4wk) | steepen ≥40bps (4wk) | 29 | 75.9% | +3.53% | +1.03% | |
| CURVE | 3M | Bull | Best alt | CURVE_steepen_5bps | steepen ≥15bps (4wk) | steepen ≥40bps (4wk) | 26 | 65.4% | +1.75% | −0.75% | Keep CONFIG — post-trough steepening (76% bull hit) is recovery confirm; looser 5bps steepen dilutes signal |
| GSR | 3M | Bear | Current | GSR_up_5pct | \|4wk\| ≥5% | \|4wk\| ≥8% | 90 | 24.4% ↓ | +3.30% | +0.80% | |
| GSR | 3M | Bear | Best alt | GSR_up_3pct | \|4wk\| ≥5% | \|4wk\| ≥8% | 133 | 34.6% ↓ | +1.53% | −0.97% | Keep CONFIG — gold/silver risk-off proxy; 3M SPX timing weak across all bands; 5% is adequate RARE without overfitting |
| HY | 3M | Bear | Current | HY_400bps | OAS ≥400 OR pctile ≥80 | OAS ≥500 OR pctile ≥95 | 42 | 45.2% ↓ | +3.32% | +0.82% | |
| HY | 3M | Bear | Best alt | HY_600bps | OAS ≥400 OR pctile ≥80 | OAS ≥500 OR pctile ≥95 | 25 | 28.0% ↓ | +4.35% | +1.85% | Keep CONFIG — OAS≥400 OR pctile≥80 matches Combo B/A credit stress; tighter 600bps raises excess slightly but cuts n and bear hit |
| NFCI | 3M | Bull | Current | NFCI_easy_0.3 | SD ≤−0.3 OR pctile ≤20 | SD ≤−0.8 OR pctile ≤5 | 12 | 75.0% | +4.42% | +1.92% | |
| NFCI | 3M | Bull | Best alt | NFCI_easy_0.5 | SD ≤−0.3 OR pctile ≤20 | SD ≤−0.8 OR pctile ≤5 | 15 | 66.7% | +2.90% | +0.40% | Keep CONFIG — easy conditions (Combo A/E); small n but 75% hit; alt easy_0.5 loosens definition without economic gain |
| NFCI | 3M | Bear | Current | NFCI_tight_0.3 | SD ≥+0.3 OR pctile ≥80 | SD ≥+0.8 OR pctile ≥95 | 8 | 37.5% ↓ | +4.42% | +1.92% | |
| NFCI | 3M | Bear | Best alt | NFCI_tight_0.5 | SD ≥+0.3 OR pctile ≥80 | SD ≥+0.8 OR pctile ≥95 | 7 | 42.9% ↓ | −0.01% | −2.51% | Keep CONFIG — tight liquidity marker; n=8 borderline; paired easy/tight ±0.3 SD is CONFIG standard |
| VIX | 3M | Bear | Current | VIX_25plus | level ≥25 AND pctile ≥80 | level ≥35 AND pctile ≥95 | 72 | 26.4% ↓ | +3.87% | +1.37% | |
| VIX | 3M | Bear | Best alt | VIX_pctile_65_79 | level ≥25 AND pctile ≥80 | level ≥35 AND pctile ≥95 | 140 | 33.6% ↓ | +2.27% | −0.23% | Keep CONFIG — n=72 robust; level≥25+pctile≥80 is Combo B capitulation gate; pctile-only alt trades fear level for weaker discrimination |
| VXTS | 3M | Bear | Current | VXTS_backward_1.10 | ratio ≥1.10 | ratio ≥1.20 | 104 | 26.0% ↓ | +2.21% | −0.29% | |
| VXTS | 3M | Bear | Best alt | VXTS_backward_1.05 | ratio ≥1.10 | ratio ≥1.20 | 85 | 28.2% ↓ | +2.37% | −0.13% | Keep CONFIG — backwardation is stress (Combo D); 3M bear hit ~26% — term structure warns but does not time SPX dips; 1.10 ratio standard |
| VXTS | 3M | Bull | Current | VXTS_contango_0.95 | ratio ≤0.95 | ratio ≤0.85 | 26 | 76.9% | +4.34% | +1.84% | |
| VXTS | 3M | Bull | Best alt | VXTS_contango_0.90 | ratio ≤0.95 | ratio ≤0.85 | 12 | 83.3% | +4.59% | +2.09% | Keep CONFIG — complacency (76% bull hit); 0.95 contango is Combo G/D reference; 0.90 alt adds +0.25pp only with n=12 |
| WALCL | 3M | Bull | Current | WALCL_expand_0.8 | \|MoM\| ≥0.8% (expand) | \|MoM\| ≥2.0% (expand) | 76 | 68.4% | +2.12% | −0.38% | |
| WALCL | 3M | Bull | Best alt | WALCL_expand_0.5 | \|MoM\| ≥0.8% (expand) | \|MoM\| ≥2.0% (expand) | 85 | 67.1% | +3.04% | +0.54% | Keep CONFIG — QE impulse (Combo A/C); expand_0.5 adds events but excess only +0.9pp; 0.8% MoM is meaningful liquidity injection |
| WALCL | 3M | Bear | Current | WALCL_contract_0.8 | \|MoM\| ≥0.8% (contract) | \|MoM\| ≥2.0% (contract) | 66 | 30.3% ↓ | +2.49% | −0.01% | |
| WALCL | 3M | Bear | Best alt | WALCL_contract_1.5 | \|MoM\| ≥0.8% (contract) | \|MoM\| ≥2.0% (contract) | 24 | 29.2% ↓ | +3.20% | +0.70% | Keep CONFIG — QT marker; bearish SPX read weak at 3M (liquidity lags); threshold OK |
| WTI | 6M | Bull | Current | WTI_down_6pct | \|4wk\| ≥6% (down) | \|4wk\| ≥10% (down) | 112 | 67.9% | +4.35% | −0.65% | |
| WTI | 6M | Bull | Best alt | WTI_down_15pct | \|4wk\| ≥6% (down) | \|4wk\| ≥10% (down) | 30 | 73.3% | +5.16% | +0.16% | Consider down_15pct — large oil drawdown bucket (n=30, 73% bull hit 6M) better matches supply-shock recovery than ±6% symmetric leg; modest +0.8pp excess vs down_6pct |
| WTI | 6M | Bear | Current | WTI_up_6pct | \|4wk\| ≥6% (up) | \|4wk\| ≥10% (up) | 130 | 31.5% ↓ | +3.01% | −1.99% | |
| WTI | 6M | Bear | Best alt | WTI_up_15pct | \|4wk\| ≥6% (up) | \|4wk\| ≥10% (up) | 40 | 37.5% ↓ | +2.81% | −2.19% | Keep CONFIG — oil spike is stress marker for Combo C but weak SPX-timing (31% bear hit); no same-side alt improves both hit and excess |

### 4b. EXTREME thresholds (CONFIG vs best EXTREME alternative)

**CPI / CAPE_low_12:** CPI surprise DB starts 2024-01 (31 rows); CAPE ≤12 has **0** first-crossings since 1990.

**Raw returns CSV:** `section_4b_extreme_threshold_raw_returns.csv` — one row per first-crossing event (3,726 rows) for all EXTREME-tier and alternative bands (excludes CONFIG RARE-only bands). Same column layout as 4a.

| Variable | Hz | Dir | Role | Band | CONFIG RARE | CONFIG EXTREME | n | Hit% | Avg SPX | PW excess | Verdict |
|----------|-----|-----|------|------|-------------|----------------|---|------|---------|-----------|---------|
| CAPE | 12M | Bear | Current | CAPE_high_32 | high ≥28 | high ≥32 | 5 | 0.0% ↓ | +17.84% | +7.84% | |
| CAPE | 12M | Bear | Best alt | CAPE_high_30 | high ≥28 | high ≥32 | 11 | 27.3% ↓ | +11.71% | +1.71% | Keep CONFIG — extreme high CAPE is slow-burn valuation risk; alt high_30 is less extreme, not more informative |
| CAPE | 12M | Bull | Current | CAPE_low_12 | low ≤16 | low ≤12 | 0 | n/a | n/a | n/a | |
| CAPE | 12M | Bull | Best alt | — | low ≤16 | low ≤12 | n/a | n/a | n/a | n/a | Keep CONFIG — zero first-crossings at ≤12 since 1990; level retained for symmetry with low_16 RARE |
| CFTC | 3M | Bull | Current | CFTC_short_5 | pctile ≤15 | pctile ≤5 | 18 | 66.7% | +3.09% | +0.59% | |
| CFTC | 3M | Bull | Best alt | CFTC_short_10 | pctile ≤15 | pctile ≤5 | 30 | 70.0% | +3.23% | +0.73% | Keep CONFIG — extreme short positioning aligns with Combo B; alt ≤10 similar profile |
| CFTC | 3M | Bear | Current | CFTC_long_95 | pctile ≥85 | pctile ≥95 | 27 | 18.5% ↓ | +5.06% | +2.56% | |
| CFTC | 3M | Bear | Best alt | CFTC_long_90 | pctile ≥85 | pctile ≥95 | 35 | 17.1% ↓ | +5.33% | +2.83% | Keep CONFIG — 95th pctile extreme crowding; marginal alt gain not worth retiering |
| CNH | 3M | Bull | Current | CNH_down_3.5pct | \|4wk\| ≥1.5% (down) | \|4wk\| ≥3.5% (down) | 2 | 50.0% | +0.86% | −1.64% | |
| CNH | 3M | Bull | Best alt | CNH_down_1.0pct | \|4wk\| ≥1.5% (down) | \|4wk\| ≥3.5% (down) | 41 | 85.4% | +4.54% | +2.04% | Keep CONFIG — only n=2 at extreme; cannot retune; 3.5% remains policy extreme |
| CNH | 3M | Bear | Current | CNH_up_3.5pct | \|4wk\| ≥1.5% (up) | \|4wk\| ≥3.5% (up) | 3 | 33.3% ↓ | +2.77% | +0.27% | |
| CNH | 3M | Bear | Best alt | CNH_up_0.5pct | \|4wk\| ≥1.5% (up) | \|4wk\| ≥3.5% (up) | 46 | 30.4% ↓ | +2.78% | +0.28% | Keep CONFIG — n=3 at extreme up; insufficient to move; 3.5% retained |
| CPI | 3M | Bear | Current | CPI_hot_0.40 | \|surprise\| ≥0.20pp | \|surprise\| ≥0.40pp | 0 | n/a | n/a | n/a | |
| CPI | 3M | Bear | Best alt | — | \|surprise\| ≥0.20pp | \|surprise\| ≥0.40pp | n/a | n/a | n/a | n/a | Defer — no EXTREME fires yet; 0.40pp retained pending longer CPI surprise series |
| CURVE | 3M | Bear | Current | CURVE_invert_80bps | spread ≤−30bps | spread ≤−80bps | 2 | 0.0% ↓ | +5.01% | +2.51% | |
| CURVE | 3M | Bear | Best alt | CURVE_invert_20bps | spread ≤−30bps | spread ≤−80bps | 7 | 57.1% ↓ | +0.84% | −1.66% | Keep CONFIG — deep inversion (n=2) too sparse; −80bps kept as deep recession marker |
| CURVE | 3M | Bull | Current | CURVE_steepen_40bps | steepen ≥15bps (4wk) | steepen ≥40bps (4wk) | 17 | 70.6% | +3.29% | +0.79% | |
| CURVE | 3M | Bull | Best alt | CURVE_steepen_5bps | steepen ≥15bps (4wk) | steepen ≥40bps (4wk) | 26 | 65.4% | +1.75% | −0.75% | Keep CONFIG — violent steepening already strong (71% hit); looser alts worse |
| GSR | 3M | Bear | Current | GSR_up_8pct | \|4wk\| ≥5% | \|4wk\| ≥8% | 39 | 23.1% ↓ | +2.37% | −0.13% | |
| GSR | 3M | Bear | Best alt | GSR_up_3pct | \|4wk\| ≥5% | \|4wk\| ≥8% | 133 | 34.6% ↓ | +1.53% | −0.97% | Keep CONFIG — extreme GSR rise is risk-off context, not actionable SPX timer at 3M |
| HY | 3M | Bear | Current | HY_500bps | OAS ≥400 OR pctile ≥80 | OAS ≥500 OR pctile ≥95 | 28 | 35.7% ↓ | +1.45% | −1.05% | |
| HY | 3M | Bear | Best alt | HY_600bps | OAS ≥400 OR pctile ≥80 | OAS ≥500 OR pctile ≥95 | 25 | 28.0% ↓ | +4.35% | +1.85% | Keep CONFIG — 500bps / 95th pctile is standard extreme widening; alt 600bps loses events |
| VIX | 3M | Bear | Current | VIX_35plus | level ≥25 AND pctile ≥80 | level ≥35 AND pctile ≥95 | 19 | 10.5% ↓ | +7.91% | +5.41% | |
| VIX | 3M | Bear | Best alt | VIX_pctile_65_79 | level ≥25 AND pctile ≥80 | level ≥35 AND pctile ≥95 | 140 | 33.6% ↓ | +2.27% | −0.23% | Keep CONFIG — extreme fear episodes (n=19); alt does not improve fear-spike signal meaningfully |
| VXTS | 3M | Bear | Current | VXTS_backward_1.20 | ratio ≥1.10 | ratio ≥1.20 | 86 | 34.9% ↓ | +1.61% | −0.89% | |
| VXTS | 3M | Bear | Best alt | VXTS_backward_1.05 | ratio ≥1.10 | ratio ≥1.20 | 85 | 28.2% ↓ | +2.37% | −0.13% | Keep CONFIG — extreme backwardation (n=86); marginal alt improvement not worth retiering |
| VXTS | 3M | Bull | Current | VXTS_contango_0.85 | ratio ≤0.95 | ratio ≤0.85 | 4 | 75.0% | +3.93% | +1.43% | |
| VXTS | 3M | Bull | Best alt | VXTS_contango_0.90 | ratio ≤0.95 | ratio ≤0.85 | 12 | 83.3% | +4.59% | +2.09% | Keep CONFIG — n=4 at 0.85; too few extreme complacency fires to loosen further |
| WALCL | 3M | Bull | Current | WALCL_expand_2.0 | \|MoM\| ≥0.8% (expand) | \|MoM\| ≥2.0% (expand) | 43 | 81.4% | +3.56% | +1.06% | |
| WALCL | 3M | Bull | Best alt | WALCL_expand_0.5 | \|MoM\| ≥0.8% (expand) | \|MoM\| ≥2.0% (expand) | 85 | 67.1% | +3.04% | +0.54% | Keep CONFIG — crisis-era expansion (81% hit); already strong; no need to retune |
| WALCL | 3M | Bear | Current | WALCL_contract_2.0 | \|MoM\| ≥0.8% (contract) | \|MoM\| ≥2.0% (contract) | 11 | 27.3% ↓ | +2.97% | +0.47% | |
| WALCL | 3M | Bear | Best alt | WALCL_contract_1.5 | \|MoM\| ≥0.8% (contract) | \|MoM\| ≥2.0% (contract) | 24 | 29.2% ↓ | +3.20% | +0.70% | Keep CONFIG — severe QT episodes rare (n=11); alt does not change policy read |
| WTI | 6M | Bull | Current | WTI_down_10pct | \|4wk\| ≥6% (down) | \|4wk\| ≥10% (down) | 70 | 68.6% | +3.52% | −1.48% | |
| WTI | 6M | Bull | Best alt | WTI_down_15pct | \|4wk\| ≥6% (down) | \|4wk\| ≥10% (down) | 30 | 73.3% | +5.16% | +0.16% | Consider down_15pct — same recovery thesis as RARE down leg; +1.6pp excess with similar hit |
| WTI | 6M | Bear | Current | WTI_up_10pct | \|4wk\| ≥6% (up) | \|4wk\| ≥10% (up) | 93 | 33.3% ↓ | +1.87% | −3.13% | |
| WTI | 6M | Bear | Best alt | WTI_up_15pct | \|4wk\| ≥6% (up) | \|4wk\| ≥10% (up) | 40 | 37.5% ↓ | +2.81% | −2.19% | Keep CONFIG — extreme up-oil fires are real (n=93) but SPX path is mixed; no compelling same-side retune |

On the flip side, VIX RARE at ≥25 already looks reasonable: 72 events, hostile excess +2.86% at 3M. Tightening to ≥30 would drop n to 44 with only +0.66pp more excess, so I would leave VIX RARE at 25.

## 5. Named combo gate results

### 5a. Combo B (Capitulation): 3M horizon, bullish

Leg replay on `daily_readings`. **HY leg uses CONFIG OR** (OAS≥threshold **or** pctile≥80); VIX requires level **and** pctile≥80. Rows below are strict **3-of-3** unless noted.

| Test | Gate change | n | Hit% | PW excess 3M |
|------|-------------|---|------|--------------|
| CB_VIX_20 | VIX≥20 (+pctile≥80) | 10 | 70.0% | +2.92% |
| CB_VIX_25 (current) | VIX≥25 (+pctile≥80) | 9 | 77.8% | +3.96% |
| CB_VIX_30 | VIX≥30 (+pctile≥80) | 7 | 85.7% | +7.02% |
| CB_HY_350 | HY≥350bps (OAS OR pctile≥80) | 9 | 77.8% | +3.96% |
| CB_HY_400 (current) | HY≥400bps (OAS OR pctile≥80) | 9 | 77.8% | +3.96% |
| CB_HY_450 | HY≥450bps (OAS OR pctile≥80) | 7 | 85.7% | +5.85% |
| CB_CFTC_10 | CFTC≤10th | 7 | 71.4% | +2.99% |
| CB_CFTC_15 (current) | CFTC≤15th | 9 | 77.8% | +3.96% |
| CB_CFTC_20 | CFTC≤20th | 10 | 70.0% | +3.20% |
| CB_2of3_legs | 2-of-3 legs | 41 | 75.6% | +2.15% |

With HY OR per CONFIG, strict **3-of-3** first-crossings are rare but not zero: **n=9** at current VIX/HY/CFTC gates (77.8% hit, +3.96% PW excess 3M). The 2-of-3 variant adds events (n=41) at similar hit rate. Production `combo_detector` still uses AND for HY level+pctile — align if intentional.

### 5b. Combo F (Recovery): 6M horizon, bullish

| SPX threshold above 50WMA | n | Hit% | PW excess 6M |
|----------------------------|---|------|--------------|
| 1% | 45 | 80.0% | +2.41% |
| 2% | 45 | 82.2% | +2.27% |
| **3% (current)** | 42 | 85.7% | +3.15% |
| 5% | 41 | 85.4% | **+3.50%** |

Current 3% is already strong. Tightening to 5% adds +0.35pp excess with similar hit rate, but the sample is basically the same size. I would keep 3% unless we want fewer marginal reclaims.

### 5c. Combo E (Valuation Extreme): 12M horizon, bearish

| Gate | Value | n | Hit% (down) | PW excess 12M |
|------|-------|---|-------------|---------------|
| CAPE≥25 | 25 | 18 | 5.6% | +7.51% |
| CAPE≥28 (current) | 28 | 22 | 9.1% | +5.96% |
| CAPE≥30 | 30 | 31 | 9.7% | +4.74% |
| CAPE≥32 | 32 | 30 | 6.7% | +4.33% |
| NFCI≤−0.2 | −0.2 | 23 | 8.7% | +5.31% |
| NFCI≤−0.3 (current) | −0.3 | 22 | 9.1% | +5.96% |
| CFTC≥75 | 75 | 27 | 11.1% | +5.07% |
| CFTC≥80 (current) | 80 | 22 | 9.1% | +5.96% |

Current CAPE≥28 looks fine. Loosening to 25 adds events but lowers hit rate. Tightening to 30/32 does not improve PW excess enough to bother.

### 5d. Combo D (FOMO Top): 5D horizon, bearish

| Test | Gate | n | Hit% (down) | PW excess 5D |
|------|------|---|-------------|--------------|
| CD_VXTS_1.05 | VXTS≥1.05 | 32 | 37.5% | −0.23% |
| CD_VXTS_1.10 (current) | VXTS≥1.10 | 31 | 41.9% | −0.28% |
| CD_VXTS_1.15 | VXTS≥1.15 | 25 | 40.0% | −0.48% |
| CD_CFTC_80 | CFTC≥80th | 33 | 39.4% | −0.11% |
| CD_CFTC_85 (current) | CFTC≥85th | 31 | 41.9% | −0.28% |
| CD_VIX_15 | VIX≤15 | 24 | 45.8% | −0.47% |
| CD_VIX_18 (current) | VIX≤18 | 31 | 41.9% | −0.28% |
| CD_2of3_legs | 2-of-3 | 86 | 33.7% | −0.23% |

Combo D does not clear the hit≥60% bar at any gate setting on 5D. Current gates are as good as any alternative we tested, but the signal is weak overall (all variants negative PW excess vs +0.5% benchmark).

## 6. What I'd change based on this

| Priority | Recommendation | Data backing |
|----------|----------------|--------------|
| 1 | **WTI down-side:** consider down_15pct for down-leg only (RARE and EXTREME); large drawdown bucket better matches supply-shock recovery thesis; keep symmetric ±6%/10% on up-leg | down_6pct → down_15pct +0.8pp excess, 73% bull hit; up-side weak SPX-timing |
| 2 | **Combo B:** current 3-of-3 gates validated with n=9 after HY OR fix; consider 2-of-3 WATCH promotion (n=41, +2.15% excess) | CB_VIX_25: n=9, hit=77.8%, excess=+3.96%; CB_2of3: n=41 |
| 3 | **Combo F:** keep SPX≥3% above 50WMA (optional tighten to 5% for +0.35pp) | 3%: hit=85.7%, excess=+3.15%; 5%: hit=85.4%, excess=+3.50% |

Everything else I would leave at current CONFIG values for now. HY, VIX, CURVE, and GSR show higher-excess alternatives on paper, but those alts trade off hit rate, sample size, or combo semantics — not worth retiering (see §4 verdicts).

## 7. Output artifacts

| Artifact | Path |
|----------|------|
| Per-variable sweeps (12) | `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2/*_sweep.json` |
| Cross-variable summary | `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2/SUMMARY.json` |
| Combo sweeps | `threshold_sweep_v2/COMBO_B_gate_sweep.json`, `COMBO_F_spx_sweep.json`, `COMBO_E_cape_sweep.json`, `COMBO_D_gate_sweep.json` |
| Corrected pctile regression | `macro_intelligence/analysis/regime_v2_experiments/F_per_variable_sweep_v2.json` |
| Scripts | `scripts/normalize_pctile_scale.py`, `scripts/threshold_sweep_v2.py`, `scripts/combo_gate_sweep_v2.py`, `scripts/export_threshold_raw_returns.py` |
| Section 4a raw returns CSV | `testing/macro_th_exp/testingv2/section_4a_rare_threshold_raw_returns.csv` (4,169 events) |
| Section 4b raw returns CSV | `testing/macro_th_exp/testingv2/section_4b_extreme_threshold_raw_returns.csv` (3,726 events) |
| Raw returns metadata | `testing/macro_th_exp/testingv2/section_4_raw_returns_meta.json` |

Run timestamps (UTC approx): P1 migration + F sweep ~23s; P2 full sweep ~227s; P3 combo sweeps ~20s.

## 8. My doubts and questions

- Combo B 3-of-3 with simultaneous VIX level≥25 AND pctile≥80 AND HY level≥400 AND pctile≥80 AND CFTC≤15 may be too strict for historical first-crossing replay. Combo leg replay now uses HY OR per CONFIG; strict 3-of-3 yields n=9 at current gates. Production `combo_detector` still uses AND for HY — align if intentional.
- WTI's justified change flips from up-side to down-side rare events. That is a paradigm shift, not a simple threshold tweak. Should ROC rare stay symmetric at |6%| or split into directional tiers?
- CPI has only 1 first-crossing at the 0.20pp RARE band since 1990. Do we have enough CPI surprise history in `daily_readings`, or is the sparse count a data coverage issue?
- Combo D never gets close to 60% hit rate on 5D. Is 5D the right horizon, or is this combo structurally more of a 1–2 week fade signal?
- Hostile-regime slices depend on `macro_regime_log` coverage (1,919 rows). Some CAPE and VXTS events fall outside hostile periods with null hostile excess. How much should we weight those nulls in the four-criteria check?


# Appendix: full supporting data

<!-- AUTO-GENERATED from threshold_sweep_v2 JSON -->

## 9. Instrument and test window reference

| Variable | Instrument | Data source | Field tested | Percentile window | Signal direction | Named combos | DB start | DB end | DB rows |
|----------|------------|-------------|--------------|-------------------|------------------|--------------|----------|--------|---------|
| CAPE | Shiller CAPE | CAPE scrape | Level (P/E ratio) | Full expanding from 1881-01-01 | High=bearish structural (12M) | E | 1990-01-05 | 2026-07-03 | 1911 |
| CFTC | CFTC TFF Fast Money net | CFTC TFF (S&P E-mini) | Net contracts, 3yr rolling pctile | Rolling 3y from 2006-01-01 | Short side bullish; long side bearish | B, D, E, F | 2010-06-18 | 2026-07-03 | 844 |
| CNH | USD/CNH | Yahoo USDCNH=X / FRED DEXCHUS | 4-week % change | Rolling 3y from 2010-01-01 | Up=CNH weakness/risk-off | A, C, G | 2010-01-08 | 2026-07-03 | 867 |
| CPI | CPI surprise | BLS/FRED vs consensus | Actual minus consensus (pp) | Rolling 3y | Hot CPI bearish (Combo C) | C | 2024-01-12 | 2026-07-03 | 31 |
| CURVE | 10Y-2Y yield spread | FRED T10Y2Y | Spread (bps) + steepen_4wk_bps in meta | Full expanding from 1976-01-01 | Inversion bearish; steepening post-trough | A, E | 1990-01-05 | 2026-07-03 | 1911 |
| GSR | Gold/Silver ratio | Yahoo GC=F / SI=F | 4-week % change | Rolling 3y | Rising GSR = risk-off | A | 2000-09-01 | 2026-07-03 | 1355 |
| HY | HY OAS spread | FRED BAMLH0A0HYM2 | Level (bps OAS) | Full expanding from 1996-01-01 | Bearish when UP (widening) | A, B, F, G | 1997-01-02 | 2026-07-03 | 7368 |
| NFCI | Chicago Fed NFCI | FRED NFCI | Level (SD units) | Full expanding from 1973-01-01 | Easy=bullish, Tight=bearish | A, E | 1990-01-05 | 2026-07-03 | 1911 |
| VIX | CBOE VIX spot | Yahoo ^VIX | Level (index points) | Full expanding from 1990-01-01 | Bearish when UP (fear spike) | B, D, G | 1990-01-05 | 2026-07-03 | 1911 |
| VXTS | VIX term structure | Yahoo ^VIX3M / ^VIX | Ratio (3M VIX / spot VIX) | Full expanding from 2007-01-01 | Backwardation bearish; contango complacency | D, G | 2007-01-05 | 2026-07-03 | 1024 |
| WALCL | Fed balance sheet | FRED WALCL | MoM % change | Full expanding from 2008-01-01 | Expansion bullish, contraction bearish | A, C | 2003-01-31 | 2026-07-03 | 1229 |
| WTI | WTI crude | Yahoo CL=F (FRED fallback) | 4-week % change | Rolling 3y | Context-dependent; large down = recovery catalyst | C | 2000-08-25 | 2026-07-03 | 1356 |

**Forward return instrument:** S&P 500 (`^GSPC`, Yahoo Finance)

**Event detection window:** 1990-01-01 through latest reading date (variable-specific DB coverage in table)

**Horizons (NYSE trading days):** 1M=21, 3M=63, 6M=126, 9M=189, 12M=252

**Benchmarks (unconditional drift):** +0.5% / +2.5% / +5.0% / +7.5% / +10.0%

## 10. CAPE: full sweep data

**CONFIG RARE:** `{"high_level": 28, "low_level": 16}`

**CONFIG EXTREME:** `{"high_level": 32, "low_level": 12}`

**Primary horizon:** 12M (252d)

| Band | Current? | Threshold | n | Hit @ primary | PW expected | Excess |
|------|----------|-----------|---|---------------|-------------|--------|
| CAPE_high_22 |  | 22 | 6 | 0.0% | +16.85% | +6.85pp |
| CAPE_high_25 |  | 25 | 10 | 0.0% | +22.95% | +12.95pp |
| CAPE_high_28_CURRENT_RARE | Y | 28 | 7 | 14.3% | +19.50% | +9.50pp |
| CAPE_high_30 |  | 30 | 11 | 27.3% | +11.71% | +1.71pp |
| CAPE_high_32_CURRENT_EXTREME | Y | 32 | 5 | 0.0% | +17.84% | +7.84pp |
| CAPE_high_35 |  | 35 | 5 | 0.0% | +19.63% | +9.63pp |
| CAPE_high_38 |  | 38 | 5 | 33.3% | +7.69% | -2.31pp |
| CAPE_low_16_CURRENT_RARE | Y | 16 | 2 | 100.0% | +18.86% | +8.86pp |
| CAPE_low_14 |  | 14 | 1 | 100.0% | +66.60% | +56.60pp |
| CAPE_low_12_CURRENT_EXTREME | Y | 12 | 0 | n/a | n/a | n/a |

### 10a. CAPE: all horizons per band

**CAPE_high_22** | threshold=22 | direction=UP | bullish=False | events n=6

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 6 | 0.0% | +0.00% | +3.43% | +3.43% | +0.5% | +2.93pp | +2.47pp |
| 3M (63d) | 6 | 33.3% | -6.27% | +8.85% | +3.81% | +2.5% | +1.31pp | +4.96pp |
| 6M (126d) | 6 | 0.0% | +0.00% | +9.08% | +9.08% | +5.0% | +4.08pp | +8.38pp |
| 9M (189d) | 6 | 16.7% | -4.14% | +15.22% | +11.99% | +7.5% | +4.49pp | +14.75pp |
| 12M (252d) | 6 | 0.0% | +0.00% | +16.85% | +16.85% | +10.0% | +6.85pp | +13.36pp |

**CAPE_high_25** | threshold=25 | direction=UP | bullish=False | events n=10

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 10 | 10.0% | -1.17% | +4.34% | +3.79% | +0.5% | +3.29pp | +1.43pp |
| 3M (63d) | 10 | 0.0% | +0.00% | +6.79% | +6.79% | +2.5% | +4.29pp | +3.17pp |
| 6M (126d) | 10 | 0.0% | +0.00% | +12.11% | +12.11% | +5.0% | +7.11pp | +6.80pp |
| 9M (189d) | 10 | 0.0% | +0.00% | +14.67% | +14.67% | +7.5% | +7.17pp | +4.85pp |
| 12M (252d) | 10 | 0.0% | +0.00% | +22.95% | +22.95% | +10.0% | +12.95pp | +12.99pp |

**CAPE_high_28_CURRENT_RARE **CURRENT**** | threshold=28 | direction=UP | bullish=False | events n=7

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 7 | 14.3% | -1.52% | +2.95% | +2.31% | +0.5% | +1.81pp | +1.89pp |
| 3M (63d) | 7 | 0.0% | +0.00% | +8.11% | +8.11% | +2.5% | +5.61pp | +7.13pp |
| 6M (126d) | 7 | 0.0% | +0.00% | +10.62% | +10.62% | +5.0% | +5.62pp | +3.16pp |
| 9M (189d) | 7 | 14.3% | -11.07% | +19.59% | +15.21% | +7.5% | +7.71pp | +9.87pp |
| 12M (252d) | 7 | 14.3% | -26.70% | +27.20% | +19.50% | +10.0% | +9.50pp | +15.13pp |

**CAPE_high_30** | threshold=30 | direction=UP | bullish=False | events n=11

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 11 | 27.3% | -2.20% | +3.55% | +1.98% | +0.5% | +1.48pp | +1.39pp |
| 3M (63d) | 11 | 36.4% | -6.89% | +5.97% | +1.29% | +2.5% | -1.21pp | +0.83pp |
| 6M (126d) | 11 | 27.3% | -7.73% | +10.42% | +5.47% | +5.0% | +0.47pp | +4.10pp |
| 9M (189d) | 11 | 27.3% | -12.72% | +15.26% | +7.63% | +7.5% | +0.13pp | +5.50pp |
| 12M (252d) | 11 | 27.3% | -16.87% | +22.43% | +11.71% | +10.0% | +1.71pp | +7.41pp |

**CAPE_high_32_CURRENT_EXTREME **CURRENT**** | threshold=32 | direction=UP | bullish=False | events n=5

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 5 | 0.0% | +0.00% | +3.29% | +3.29% | +0.5% | +2.79pp | +2.24pp |
| 3M (63d) | 5 | 20.0% | -3.52% | +5.84% | +3.97% | +2.5% | +1.47pp | -0.40pp |
| 6M (126d) | 5 | 20.0% | -3.61% | +8.37% | +5.98% | +5.0% | +0.98pp | -2.11pp |
| 9M (189d) | 5 | 0.0% | +0.00% | +15.08% | +15.08% | +7.5% | +7.58pp | +4.75pp |
| 12M (252d) | 5 | 0.0% | +0.00% | +17.84% | +17.84% | +10.0% | +7.84pp | +3.81pp |

**CAPE_high_35** | threshold=35 | direction=UP | bullish=False | events n=5

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 5 | 40.0% | -3.57% | +4.92% | +1.52% | +0.5% | +1.02pp | -7.34pp |
| 3M (63d) | 5 | 0.0% | +0.00% | +6.94% | +6.94% | +2.5% | +4.44pp | -0.12pp |
| 6M (126d) | 5 | 20.0% | -6.96% | +14.99% | +10.60% | +5.0% | +5.60pp | +1.74pp |
| 9M (189d) | 5 | 20.0% | -9.07% | +15.83% | +10.85% | +7.5% | +3.35pp | -16.57pp |
| 12M (252d) | 5 | 0.0% | +0.00% | +19.63% | +19.63% | +10.0% | +9.63pp | +2.50pp |

**CAPE_high_38** | threshold=38 | direction=UP | bullish=False | events n=5

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 5 | 40.0% | -3.36% | +7.46% | +3.14% | +0.5% | +2.64pp | -6.98pp |
| 3M (63d) | 4 | 50.0% | -8.55% | +7.28% | -0.63% | +2.5% | -3.13pp | -15.05pp |
| 6M (126d) | 4 | 25.0% | -15.04% | +7.97% | +2.22% | +5.0% | -2.78pp | +2.12pp |
| 9M (189d) | 4 | 25.0% | -12.24% | +14.66% | +7.93% | +7.5% | +0.43pp | +7.46pp |
| 12M (252d) | 3 | 33.3% | -18.96% | +21.02% | +7.69% | +10.0% | -2.31pp | +11.08pp |

**CAPE_low_16_CURRENT_RARE **CURRENT**** | threshold=16 | direction=DOWN | bullish=True | events n=2

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 2 | 0.0% | +0.00% | -3.81% | -3.81% | +0.5% | -4.31pp | n/a |
| 3M (63d) | 2 | 50.0% | +1.75% | -11.15% | -4.70% | +2.5% | -7.20pp | n/a |
| 6M (126d) | 2 | 50.0% | +15.94% | -2.43% | +6.75% | +5.0% | +1.75pp | n/a |
| 9M (189d) | 2 | 100.0% | +12.07% | +0.00% | +12.07% | +7.5% | +4.57pp | n/a |
| 12M (252d) | 2 | 100.0% | +18.86% | +0.00% | +18.86% | +10.0% | +8.86pp | n/a |

**CAPE_low_14** | threshold=14 | direction=DOWN | bullish=True | events n=1

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 1 | 100.0% | +22.26% | +0.00% | +22.26% | +0.5% | +21.76pp | n/a |
| 3M (63d) | 1 | 100.0% | +37.56% | +0.00% | +37.56% | +2.5% | +35.06pp | n/a |
| 6M (126d) | 1 | 100.0% | +46.81% | +0.00% | +46.81% | +5.0% | +41.81pp | n/a |
| 9M (189d) | 1 | 100.0% | +60.95% | +0.00% | +60.95% | +7.5% | +53.45pp | n/a |
| 12M (252d) | 1 | 100.0% | +66.60% | +0.00% | +66.60% | +10.0% | +56.60pp | n/a |

---

## 11. CFTC: full sweep data

**CONFIG RARE:** `{"low_pctile": 15, "high_pctile": 85}`

**CONFIG EXTREME:** `{"low_pctile": 5, "high_pctile": 95}`

**Primary horizon:** 3M (63d)

| Band | Current? | Threshold | n | Hit @ primary | PW expected | Excess |
|------|----------|-----------|---|---------------|-------------|--------|
| CFTC_short_30 |  | 30 | 58 | 73.7% | +2.74% | +0.24pp |
| CFTC_short_20 |  | 20 | 47 | 62.2% | +1.92% | -0.58pp |
| CFTC_short_15_CURRENT_RARE | Y | 15 | 40 | 63.2% | +1.61% | -0.89pp |
| CFTC_short_10 |  | 10 | 31 | 70.0% | +3.23% | +0.73pp |
| CFTC_short_5_CURRENT_EXTREME | Y | 5 | 19 | 66.7% | +3.09% | +0.59pp |
| CFTC_long_70 |  | 70 | 42 | 14.6% | +3.37% | +0.87pp |
| CFTC_long_80 |  | 80 | 40 | 10.3% | +5.81% | +3.31pp |
| CFTC_long_85_CURRENT_RARE | Y | 85 | 40 | 20.5% | +4.77% | +2.27pp |
| CFTC_long_90 |  | 90 | 36 | 17.1% | +5.33% | +2.83pp |
| CFTC_long_95_CURRENT_EXTREME | Y | 95 | 27 | 18.5% | +5.06% | +2.56pp |

### 11a. CFTC: all horizons per band

**CFTC_short_30** | threshold=30 | direction=DOWN | bullish=True | events n=58

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 58 | 79.3% | +3.30% | -3.76% | +1.84% | +0.5% | +1.34pp | -0.53pp |
| 3M (63d) | 57 | 73.7% | +6.30% | -7.21% | +2.74% | +2.5% | +0.24pp | -1.14pp |
| 6M (126d) | 57 | 75.4% | +9.86% | -6.33% | +5.88% | +5.0% | +0.88pp | -0.97pp |
| 9M (189d) | 57 | 82.5% | +13.10% | -5.68% | +9.81% | +7.5% | +2.31pp | -1.45pp |
| 12M (252d) | 54 | 94.4% | +16.52% | -7.23% | +15.20% | +10.0% | +5.20pp | +3.93pp |

**CFTC_short_20** | threshold=20 | direction=DOWN | bullish=True | events n=47

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 45 | 71.1% | +2.94% | -5.94% | +0.37% | +0.5% | -0.13pp | -0.82pp |
| 3M (63d) | 45 | 62.2% | +6.67% | -5.91% | +1.92% | +2.5% | -0.58pp | -1.99pp |
| 6M (126d) | 44 | 77.3% | +9.60% | -4.88% | +6.31% | +5.0% | +1.31pp | -0.61pp |
| 9M (189d) | 43 | 88.4% | +12.66% | -8.88% | +10.16% | +7.5% | +2.66pp | -2.89pp |
| 12M (252d) | 41 | 97.6% | +16.98% | -12.59% | +16.26% | +10.0% | +6.26pp | +4.26pp |

**CFTC_short_15_CURRENT_RARE **CURRENT**** | threshold=15 | direction=DOWN | bullish=True | events n=40

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 38 | 65.8% | +3.87% | -5.27% | +0.75% | +0.5% | +0.25pp | -0.45pp |
| 3M (63d) | 38 | 63.2% | +6.36% | -6.53% | +1.61% | +2.5% | -0.89pp | -1.17pp |
| 6M (126d) | 35 | 74.3% | +10.37% | -4.64% | +6.51% | +5.0% | +1.51pp | +0.51pp |
| 9M (189d) | 34 | 94.1% | +13.66% | -9.37% | +12.31% | +7.5% | +4.81pp | +2.76pp |
| 12M (252d) | 32 | 96.9% | +19.18% | -12.59% | +18.18% | +10.0% | +8.18pp | +8.26pp |

**CFTC_short_10** | threshold=10 | direction=DOWN | bullish=True | events n=31

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 30 | 63.3% | +3.32% | -5.32% | +0.15% | +0.5% | -0.35pp | +0.11pp |
| 3M (63d) | 30 | 70.0% | +6.73% | -4.92% | +3.23% | +2.5% | +0.73pp | +1.57pp |
| 6M (126d) | 27 | 77.8% | +10.97% | -2.30% | +8.02% | +5.0% | +3.02pp | +3.90pp |
| 9M (189d) | 25 | 96.0% | +16.64% | -3.36% | +15.84% | +7.5% | +8.34pp | +8.29pp |
| 12M (252d) | 23 | 100.0% | +21.94% | +0.00% | +21.94% | +10.0% | +11.94pp | +11.85pp |

**CFTC_short_5_CURRENT_EXTREME **CURRENT**** | threshold=5 | direction=DOWN | bullish=True | events n=19

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 18 | 66.7% | +4.01% | -4.66% | +1.12% | +0.5% | +0.62pp | -0.80pp |
| 3M (63d) | 18 | 66.7% | +6.63% | -4.00% | +3.09% | +2.5% | +0.59pp | -1.23pp |
| 6M (126d) | 18 | 83.3% | +10.54% | -4.23% | +8.08% | +5.0% | +3.08pp | +0.14pp |
| 9M (189d) | 18 | 94.4% | +16.17% | -3.36% | +15.09% | +7.5% | +7.59pp | +4.09pp |
| 12M (252d) | 18 | 100.0% | +20.96% | +0.00% | +20.96% | +10.0% | +10.96pp | +7.63pp |

**CFTC_long_70** | threshold=70 | direction=UP | bullish=False | events n=42

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 42 | 42.9% | -3.78% | +3.91% | +0.62% | +0.5% | +0.12pp | -0.03pp |
| 3M (63d) | 41 | 14.6% | -6.14% | +5.00% | +3.37% | +2.5% | +0.87pp | -0.51pp |
| 6M (126d) | 41 | 24.4% | -4.34% | +9.58% | +6.19% | +5.0% | +1.19pp | -0.29pp |
| 9M (189d) | 41 | 22.0% | -7.28% | +13.17% | +8.68% | +7.5% | +1.18pp | +1.47pp |
| 12M (252d) | 41 | 24.4% | -4.71% | +14.21% | +9.60% | +10.0% | -0.40pp | -1.01pp |

**CFTC_long_80** | threshold=80 | direction=UP | bullish=False | events n=40

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 40 | 20.0% | -3.91% | +4.02% | +2.43% | +0.5% | +1.93pp | +0.87pp |
| 3M (63d) | 39 | 10.3% | -4.32% | +6.96% | +5.81% | +2.5% | +3.31pp | +0.88pp |
| 6M (126d) | 39 | 10.3% | -2.13% | +10.26% | +8.99% | +5.0% | +3.99pp | +1.52pp |
| 9M (189d) | 39 | 25.6% | -6.60% | +15.34% | +9.71% | +7.5% | +2.21pp | +1.12pp |
| 12M (252d) | 39 | 17.9% | -6.73% | +17.10% | +12.82% | +10.0% | +2.82pp | +1.97pp |

**CFTC_long_85_CURRENT_RARE **CURRENT**** | threshold=85 | direction=UP | bullish=False | events n=40

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 40 | 32.5% | -3.21% | +3.68% | +1.44% | +0.5% | +0.94pp | -1.06pp |
| 3M (63d) | 39 | 20.5% | -3.63% | +6.94% | +4.77% | +2.5% | +2.27pp | +0.19pp |
| 6M (126d) | 39 | 17.9% | -5.64% | +9.27% | +6.60% | +5.0% | +1.60pp | -0.08pp |
| 9M (189d) | 39 | 25.6% | -9.06% | +12.60% | +7.05% | +7.5% | -0.45pp | +0.04pp |
| 12M (252d) | 39 | 20.5% | -8.84% | +14.60% | +9.79% | +10.0% | -0.21pp | +0.43pp |

**CFTC_long_90** | threshold=90 | direction=UP | bullish=False | events n=36

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 36 | 36.1% | -3.28% | +4.18% | +1.48% | +0.5% | +0.98pp | -0.88pp |
| 3M (63d) | 35 | 17.1% | -3.55% | +7.16% | +5.33% | +2.5% | +2.83pp | +1.08pp |
| 6M (126d) | 35 | 14.3% | -6.72% | +10.06% | +7.66% | +5.0% | +2.66pp | +1.01pp |
| 9M (189d) | 35 | 20.0% | -9.04% | +13.81% | +9.24% | +7.5% | +1.74pp | +0.41pp |
| 12M (252d) | 35 | 17.1% | -9.45% | +16.34% | +11.92% | +10.0% | +1.92pp | +1.63pp |

**CFTC_long_95_CURRENT_EXTREME **CURRENT**** | threshold=95 | direction=UP | bullish=False | events n=27

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 27 | 33.3% | -2.49% | +4.07% | +1.89% | +0.5% | +1.39pp | -0.56pp |
| 3M (63d) | 27 | 18.5% | -3.24% | +6.94% | +5.06% | +2.5% | +2.56pp | +0.53pp |
| 6M (126d) | 27 | 7.4% | -9.65% | +10.85% | +9.33% | +5.0% | +4.33pp | +2.60pp |
| 9M (189d) | 27 | 22.2% | -6.85% | +14.91% | +10.07% | +7.5% | +2.57pp | -0.72pp |
| 12M (252d) | 27 | 18.5% | -4.98% | +17.42% | +13.27% | +10.0% | +3.27pp | +1.93pp |

---

## 12. CNH: full sweep data

**CONFIG RARE:** `{"pct_4wk": 1.5}`

**CONFIG EXTREME:** `{"pct_4wk": 3.5}`

**Primary horizon:** 3M (63d)

| Band | Current? | Threshold | n | Hit @ primary | PW expected | Excess |
|------|----------|-----------|---|---------------|-------------|--------|
| CNH_down_0.5pct |  | -0.5 | 60 | 74.1% | +3.17% | +0.67pp |
| CNH_down_1.0pct |  | -1.0 | 42 | 85.4% | +4.54% | +2.04pp |
| CNH_down_1.5pct_CURRENT_RARE | Y | -1.5 | 17 | 82.4% | +5.08% | +2.58pp |
| CNH_down_2.5pct |  | -2.5 | 4 | 50.0% | +0.85% | -1.65pp |
| CNH_down_3.5pct_CURRENT_EXTREME | Y | -3.5 | 2 | 50.0% | +0.86% | -1.64pp |
| CNH_up_0.5pct |  | 0.5 | 47 | 30.4% | +2.78% | +0.28pp |
| CNH_up_1.0pct |  | 1.0 | 27 | 25.9% | +3.06% | +0.56pp |
| CNH_up_1.5pct_CURRENT_RARE | Y | 1.5 | 22 | 18.2% | +3.35% | +0.85pp |
| CNH_up_2.5pct |  | 2.5 | 10 | 30.0% | +3.96% | +1.46pp |
| CNH_up_3.5pct_CURRENT_EXTREME | Y | 3.5 | 3 | 33.3% | +2.77% | +0.27pp |

### 12a. CNH: all horizons per band

**CNH_down_0.5pct** | threshold=-0.5 | direction=DOWN | bullish=True | events n=60

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 59 | 76.3% | +3.18% | -3.79% | +1.53% | +0.5% | +1.03pp | +1.33pp |
| 3M (63d) | 58 | 74.1% | +6.07% | -5.14% | +3.17% | +2.5% | +0.67pp | +1.55pp |
| 6M (126d) | 58 | 84.5% | +9.92% | -6.56% | +7.36% | +5.0% | +2.36pp | +4.66pp |
| 9M (189d) | 57 | 78.9% | +13.62% | -7.27% | +9.22% | +7.5% | +1.72pp | +2.94pp |
| 12M (252d) | 56 | 87.5% | +16.04% | -8.28% | +13.00% | +10.0% | +3.00pp | +5.13pp |

**CNH_down_1.0pct** | threshold=-1.0 | direction=DOWN | bullish=True | events n=42

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 42 | 71.4% | +3.29% | -3.32% | +1.40% | +0.5% | +0.90pp | +1.39pp |
| 3M (63d) | 41 | 85.4% | +6.45% | -6.63% | +4.54% | +2.5% | +2.04pp | +2.58pp |
| 6M (126d) | 39 | 87.2% | +10.34% | -5.88% | +8.26% | +5.0% | +3.26pp | +3.93pp |
| 9M (189d) | 39 | 87.2% | +14.19% | -6.11% | +11.59% | +7.5% | +4.09pp | +3.73pp |
| 12M (252d) | 38 | 84.2% | +19.80% | -4.49% | +15.96% | +10.0% | +5.96pp | +8.39pp |

**CNH_down_1.5pct_CURRENT_RARE **CURRENT**** | threshold=-1.5 | direction=DOWN | bullish=True | events n=17

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 17 | 76.5% | +3.03% | -3.51% | +1.49% | +0.5% | +0.99pp | +1.18pp |
| 3M (63d) | 17 | 82.4% | +7.56% | -6.51% | +5.08% | +2.5% | +2.58pp | +2.23pp |
| 6M (126d) | 17 | 88.2% | +11.53% | -4.40% | +9.66% | +5.0% | +4.66pp | +3.61pp |
| 9M (189d) | 17 | 100.0% | +13.78% | +0.00% | +13.78% | +7.5% | +6.28pp | +4.51pp |
| 12M (252d) | 17 | 76.5% | +20.93% | -2.77% | +15.36% | +10.0% | +5.36pp | +5.76pp |

**CNH_down_2.5pct** | threshold=-2.5 | direction=DOWN | bullish=True | events n=4

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 4 | 50.0% | +2.88% | -4.36% | -0.74% | +0.5% | -1.24pp | -1.24pp |
| 3M (63d) | 4 | 50.0% | +5.25% | -3.54% | +0.85% | +2.5% | -1.65pp | -1.65pp |
| 6M (126d) | 4 | 75.0% | +9.76% | -0.30% | +7.24% | +5.0% | +2.24pp | +2.24pp |
| 9M (189d) | 4 | 75.0% | +10.01% | -1.48% | +7.14% | +7.5% | -0.36pp | -0.36pp |
| 12M (252d) | 4 | 75.0% | +15.88% | -6.31% | +10.33% | +10.0% | +0.33pp | +0.33pp |

**CNH_down_3.5pct_CURRENT_EXTREME **CURRENT**** | threshold=-3.5 | direction=DOWN | bullish=True | events n=2

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 2 | 50.0% | +3.43% | -5.37% | -0.97% | +0.5% | -1.47pp | -1.47pp |
| 3M (63d) | 2 | 50.0% | +3.81% | -2.10% | +0.86% | +2.5% | -1.64pp | -1.64pp |
| 6M (126d) | 2 | 100.0% | +9.56% | +0.00% | +9.56% | +5.0% | +4.56pp | +4.56pp |
| 9M (189d) | 2 | 100.0% | +9.52% | +0.00% | +9.52% | +7.5% | +2.02pp | +2.02pp |
| 12M (252d) | 2 | 100.0% | +15.34% | +0.00% | +15.34% | +10.0% | +5.34pp | +5.34pp |

**CNH_up_0.5pct** | threshold=0.5 | direction=UP | bullish=False | events n=47

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 47 | 36.2% | -4.48% | +4.36% | +1.16% | +0.5% | +0.66pp | -0.80pp |
| 3M (63d) | 46 | 30.4% | -7.17% | +7.13% | +2.78% | +2.5% | +0.28pp | -2.45pp |
| 6M (126d) | 46 | 17.4% | -6.70% | +9.55% | +6.73% | +5.0% | +1.73pp | -0.98pp |
| 9M (189d) | 46 | 17.4% | -3.44% | +14.30% | +11.22% | +7.5% | +3.72pp | +0.75pp |
| 12M (252d) | 45 | 11.1% | -6.19% | +16.71% | +14.17% | +10.0% | +4.17pp | +1.33pp |

**CNH_up_1.0pct** | threshold=1.0 | direction=UP | bullish=False | events n=27

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 27 | 37.0% | -4.68% | +3.28% | +0.33% | +0.5% | -0.17pp | -0.84pp |
| 3M (63d) | 27 | 25.9% | -4.95% | +5.87% | +3.06% | +2.5% | +0.56pp | -0.24pp |
| 6M (126d) | 27 | 22.2% | -7.55% | +9.02% | +5.34% | +5.0% | +0.34pp | -1.67pp |
| 9M (189d) | 27 | 11.1% | -4.44% | +12.39% | +10.52% | +7.5% | +3.02pp | +1.90pp |
| 12M (252d) | 27 | 11.1% | -5.32% | +16.91% | +14.44% | +10.0% | +4.44pp | +2.75pp |

**CNH_up_1.5pct_CURRENT_RARE **CURRENT**** | threshold=1.5 | direction=UP | bullish=False | events n=22

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 22 | 40.9% | -7.30% | +3.11% | -1.15% | +0.5% | -1.65pp | -1.65pp |
| 3M (63d) | 22 | 18.2% | -6.34% | +5.51% | +3.35% | +2.5% | +0.85pp | +0.84pp |
| 6M (126d) | 22 | 31.8% | -6.00% | +10.62% | +5.33% | +5.0% | +0.33pp | +0.22pp |
| 9M (189d) | 22 | 13.6% | -4.44% | +12.28% | +10.00% | +7.5% | +2.50pp | +2.94pp |
| 12M (252d) | 22 | 9.1% | -3.54% | +18.25% | +16.27% | +10.0% | +6.27pp | +5.34pp |

**CNH_up_2.5pct** | threshold=2.5 | direction=UP | bullish=False | events n=10

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 10 | 20.0% | -8.31% | +2.61% | +0.43% | +0.5% | -0.07pp | -0.01pp |
| 3M (63d) | 10 | 30.0% | -1.68% | +6.38% | +3.96% | +2.5% | +1.46pp | +1.36pp |
| 6M (126d) | 10 | 40.0% | -6.99% | +9.03% | +2.62% | +5.0% | -2.38pp | -3.45pp |
| 9M (189d) | 10 | 20.0% | -1.26% | +10.27% | +7.96% | +7.5% | +0.46pp | +3.26pp |
| 12M (252d) | 10 | 10.0% | -0.30% | +11.97% | +10.74% | +10.0% | +0.74pp | -0.42pp |

**CNH_up_3.5pct_CURRENT_EXTREME **CURRENT**** | threshold=3.5 | direction=UP | bullish=False | events n=3

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 3 | 0.0% | +0.00% | +2.04% | +2.04% | +0.5% | +1.54pp | +1.54pp |
| 3M (63d) | 3 | 33.3% | -0.32% | +4.32% | +2.77% | +2.5% | +0.27pp | +0.27pp |
| 6M (126d) | 3 | 66.7% | -6.60% | +7.70% | -1.83% | +5.0% | -6.83pp | -6.83pp |
| 9M (189d) | 3 | 33.3% | -1.34% | +11.74% | +7.38% | +7.5% | -0.12pp | -0.12pp |
| 12M (252d) | 3 | 33.3% | -0.30% | +11.84% | +7.79% | +10.0% | -2.21pp | -2.21pp |

---

## 13. CPI: full sweep data

**CONFIG RARE:** `{"surprise_pp": 0.2}`

**CONFIG EXTREME:** `{"surprise_pp": 0.4}`

**Primary horizon:** 3M (63d)

| Band | Current? | Threshold | n | Hit @ primary | PW expected | Excess |
|------|----------|-----------|---|---------------|-------------|--------|
| CPI_hot_0.05 |  | 0.05 | 3 | 0.0% | +5.95% | +3.45pp |
| CPI_hot_0.10 |  | 0.1 | 2 | 0.0% | +5.95% | +3.45pp |
| CPI_hot_0.20_CURRENT_RARE | Y | 0.2 | 2 | 0.0% | +5.95% | +3.45pp |
| CPI_hot_0.30 |  | 0.3 | 1 | n/a | n/a | n/a |
| CPI_hot_0.40_CURRENT_EXTREME | Y | 0.4 | 0 | n/a | n/a | n/a |
| CPI_hot_0.60 |  | 0.6 | 0 | n/a | n/a | n/a |

### 13a. CPI: all horizons per band

**CPI_hot_0.05** | threshold=0.05 | direction=UP | bullish=False | events n=3

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 1 | 0.0% | +0.00% | +3.45% | +3.45% | +0.5% | +2.95pp | +2.95pp |
| 3M (63d) | 1 | 0.0% | +0.00% | +5.95% | +5.95% | +2.5% | +3.45pp | +3.45pp |
| 6M (126d) | 1 | 0.0% | +0.00% | +12.04% | +12.04% | +5.0% | +7.04pp | +7.04pp |
| 9M (189d) | 1 | 0.0% | +0.00% | +17.28% | +17.28% | +7.5% | +9.78pp | +9.78pp |
| 12M (252d) | 1 | 0.0% | +0.00% | +22.21% | +22.21% | +10.0% | +12.21pp | +12.21pp |

**CPI_hot_0.10** | threshold=0.1 | direction=UP | bullish=False | events n=2

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 1 | 0.0% | +0.00% | +3.45% | +3.45% | +0.5% | +2.95pp | +2.95pp |
| 3M (63d) | 1 | 0.0% | +0.00% | +5.95% | +5.95% | +2.5% | +3.45pp | +3.45pp |
| 6M (126d) | 1 | 0.0% | +0.00% | +12.04% | +12.04% | +5.0% | +7.04pp | +7.04pp |
| 9M (189d) | 1 | 0.0% | +0.00% | +17.28% | +17.28% | +7.5% | +9.78pp | +9.78pp |
| 12M (252d) | 1 | 0.0% | +0.00% | +22.21% | +22.21% | +10.0% | +12.21pp | +12.21pp |

**CPI_hot_0.20_CURRENT_RARE **CURRENT**** | threshold=0.2 | direction=UP | bullish=False | events n=2

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 1 | 0.0% | +0.00% | +3.45% | +3.45% | +0.5% | +2.95pp | +2.95pp |
| 3M (63d) | 1 | 0.0% | +0.00% | +5.95% | +5.95% | +2.5% | +3.45pp | +3.45pp |
| 6M (126d) | 1 | 0.0% | +0.00% | +12.04% | +12.04% | +5.0% | +7.04pp | +7.04pp |
| 9M (189d) | 1 | 0.0% | +0.00% | +17.28% | +17.28% | +7.5% | +9.78pp | +9.78pp |
| 12M (252d) | 1 | 0.0% | +0.00% | +22.21% | +22.21% | +10.0% | +12.21pp | +12.21pp |

**CPI_hot_0.30** | threshold=0.3 | direction=UP | bullish=False | events n=1

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|

---

## 14. CURVE: full sweep data

**CONFIG RARE:** `{"spread_bps": -30, "steepen_4wk_bps": 15}`

**CONFIG EXTREME:** `{"spread_bps": -80, "steepen_4wk_bps": 40}`

**Primary horizon:** 3M (63d)

| Band | Current? | Threshold | n | Hit @ primary | PW expected | Excess |
|------|----------|-----------|---|---------------|-------------|--------|
| CURVE_invert_10bps |  | -10 | 9 | 22.2% | +2.74% | +0.24pp |
| CURVE_invert_20bps |  | -20 | 7 | 57.1% | +0.84% | -1.66pp |
| CURVE_invert_30bps_CURRENT_RARE | Y | -30 | 10 | 50.0% | -0.60% | -3.10pp |
| CURVE_invert_50bps |  | -50 | 6 | 16.7% | +5.24% | +2.74pp |
| CURVE_invert_80bps_CURRENT_EXTREME | Y | -80 | 2 | 0.0% | +5.01% | +2.51pp |
| CURVE_invert_100bps |  | -100 | 1 | 100.0% | -3.65% | -6.15pp |
| CURVE_steepen_5bps |  | 5 | 26 | 65.4% | +1.75% | -0.75pp |
| CURVE_steepen_10bps |  | 10 | 25 | 64.0% | +1.01% | -1.49pp |
| CURVE_steepen_15bps_CURRENT_RARE | Y | 15 | 29 | 75.9% | +3.53% | +1.03pp |
| CURVE_steepen_25bps |  | 25 | 30 | 53.3% | +0.14% | -2.36pp |
| CURVE_steepen_40bps_CURRENT_EXTREME | Y | 40 | 17 | 70.6% | +3.29% | +0.79pp |

### 14a. CURVE: all horizons per band

**CURVE_invert_10bps** | threshold=-10 | direction=DOWN | bullish=False | events n=9

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 9 | 11.1% | -4.83% | +5.12% | +4.01% | +0.5% | +3.51pp | +3.55pp |
| 3M (63d) | 9 | 22.2% | -3.31% | +4.47% | +2.74% | +2.5% | +0.24pp | -0.20pp |
| 6M (126d) | 9 | 11.1% | -0.02% | +8.02% | +7.13% | +5.0% | +2.13pp | +1.66pp |
| 9M (189d) | 9 | 11.1% | -6.69% | +6.48% | +5.01% | +7.5% | -2.49pp | -3.08pp |
| 12M (252d) | 9 | 33.3% | -7.27% | +11.86% | +5.49% | +10.0% | -4.51pp | -5.26pp |

**CURVE_invert_20bps** | threshold=-20 | direction=DOWN | bullish=False | events n=7

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 7 | 42.9% | -3.39% | +5.31% | +1.58% | +0.5% | +1.08pp | +1.08pp |
| 3M (63d) | 7 | 57.1% | -3.47% | +6.57% | +0.84% | +2.5% | -1.66pp | -1.66pp |
| 6M (126d) | 7 | 28.6% | -9.46% | +8.44% | +3.33% | +5.0% | -1.67pp | -1.67pp |
| 9M (189d) | 7 | 42.9% | -12.23% | +15.87% | +3.83% | +7.5% | -3.67pp | -3.67pp |
| 12M (252d) | 7 | 42.9% | -18.69% | +24.65% | +6.08% | +10.0% | -3.92pp | -3.92pp |

**CURVE_invert_30bps_CURRENT_RARE **CURRENT**** | threshold=-30 | direction=DOWN | bullish=False | events n=10

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 10 | 50.0% | -5.28% | +2.58% | -1.35% | +0.5% | -1.85pp | -1.85pp |
| 3M (63d) | 10 | 50.0% | -5.57% | +4.36% | -0.60% | +2.5% | -3.10pp | -3.10pp |
| 6M (126d) | 10 | 40.0% | -6.32% | +7.14% | +1.76% | +5.0% | -3.24pp | -3.24pp |
| 9M (189d) | 10 | 40.0% | -11.41% | +14.99% | +4.43% | +7.5% | -3.07pp | -3.07pp |
| 12M (252d) | 10 | 30.0% | -19.83% | +15.60% | +4.97% | +10.0% | -5.03pp | -5.03pp |

**CURVE_invert_50bps** | threshold=-50 | direction=DOWN | bullish=False | events n=6

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 6 | 16.7% | -6.87% | +2.20% | +0.69% | +0.5% | +0.19pp | +0.19pp |
| 3M (63d) | 6 | 16.7% | -2.69% | +6.82% | +5.24% | +2.5% | +2.74pp | +2.74pp |
| 6M (126d) | 6 | 16.7% | -7.08% | +7.66% | +5.21% | +5.0% | +0.21pp | +0.21pp |
| 9M (189d) | 6 | 16.7% | -14.54% | +16.69% | +11.48% | +7.5% | +3.98pp | +3.98pp |
| 12M (252d) | 6 | 16.7% | -24.98% | +22.11% | +14.26% | +10.0% | +4.26pp | +4.26pp |

**CURVE_invert_80bps_CURRENT_EXTREME **CURRENT**** | threshold=-80 | direction=DOWN | bullish=False | events n=2

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 2 | 0.0% | +0.00% | +2.01% | +2.01% | +0.5% | +1.51pp | +1.51pp |
| 3M (63d) | 2 | 0.0% | +0.00% | +5.01% | +5.01% | +2.5% | +2.51pp | +2.51pp |
| 6M (126d) | 2 | 0.0% | +0.00% | +9.13% | +9.13% | +5.0% | +4.13pp | +4.13pp |
| 9M (189d) | 2 | 0.0% | +0.00% | +16.72% | +16.72% | +7.5% | +9.22pp | +9.22pp |
| 12M (252d) | 2 | 0.0% | +0.00% | +25.74% | +25.74% | +10.0% | +15.74pp | +15.74pp |

**CURVE_invert_100bps** | threshold=-100 | direction=DOWN | bullish=False | events n=1

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 1 | 0.0% | +0.00% | +2.84% | +2.84% | +0.5% | +2.34pp | +2.34pp |
| 3M (63d) | 1 | 100.0% | -3.65% | +0.00% | -3.65% | +2.5% | -6.15pp | -6.15pp |
| 6M (126d) | 1 | 0.0% | +0.00% | +7.18% | +7.18% | +5.0% | +2.18pp | +2.18pp |
| 9M (189d) | 1 | 0.0% | +0.00% | +16.97% | +16.97% | +7.5% | +9.47pp | +9.47pp |
| 12M (252d) | 1 | 0.0% | +0.00% | +23.79% | +23.79% | +10.0% | +13.79pp | +13.79pp |

**CURVE_steepen_5bps** | threshold=5 | direction=UP | bullish=True | events n=26

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 26 | 57.7% | +4.06% | -4.77% | +0.32% | +0.5% | -0.18pp | +0.03pp |
| 3M (63d) | 26 | 65.4% | +6.38% | -6.99% | +1.75% | +2.5% | -0.75pp | -1.59pp |
| 6M (126d) | 26 | 73.1% | +8.81% | -11.01% | +3.47% | +5.0% | -1.53pp | +0.14pp |
| 9M (189d) | 26 | 65.4% | +13.18% | -7.92% | +5.87% | +7.5% | -1.63pp | -0.62pp |
| 12M (252d) | 26 | 61.5% | +15.88% | -8.77% | +6.40% | +10.0% | -3.60pp | -3.13pp |

**CURVE_steepen_10bps** | threshold=10 | direction=UP | bullish=True | events n=25

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 25 | 56.0% | +3.52% | -5.42% | -0.42% | +0.5% | -0.92pp | -0.98pp |
| 3M (63d) | 25 | 64.0% | +5.88% | -7.65% | +1.01% | +2.5% | -1.49pp | -2.53pp |
| 6M (126d) | 25 | 64.0% | +7.76% | -10.19% | +1.30% | +5.0% | -3.70pp | -1.60pp |
| 9M (189d) | 25 | 64.0% | +11.85% | -9.66% | +4.11% | +7.5% | -3.39pp | -2.61pp |
| 12M (252d) | 25 | 68.0% | +16.16% | -12.29% | +7.06% | +10.0% | -2.94pp | -2.39pp |

**CURVE_steepen_15bps_CURRENT_RARE **CURRENT**** | threshold=15 | direction=UP | bullish=True | events n=29

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 29 | 62.1% | +3.39% | -4.70% | +0.32% | +0.5% | -0.18pp | -0.21pp |
| 3M (63d) | 29 | 75.9% | +6.82% | -6.80% | +3.53% | +2.5% | +1.03pp | +0.14pp |
| 6M (126d) | 29 | 62.1% | +10.97% | -7.06% | +4.13% | +5.0% | -0.87pp | -0.37pp |
| 9M (189d) | 29 | 62.1% | +14.81% | -10.14% | +5.35% | +7.5% | -2.15pp | -1.58pp |
| 12M (252d) | 29 | 69.0% | +19.31% | -12.68% | +9.39% | +10.0% | -0.61pp | -1.45pp |

**CURVE_steepen_25bps** | threshold=25 | direction=UP | bullish=True | events n=30

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 30 | 60.0% | +4.11% | -4.80% | +0.55% | +0.5% | +0.05pp | -0.10pp |
| 3M (63d) | 30 | 53.3% | +7.65% | -8.45% | +0.14% | +2.5% | -2.36pp | -1.33pp |
| 6M (126d) | 30 | 56.7% | +11.61% | -6.76% | +3.65% | +5.0% | -1.35pp | -1.80pp |
| 9M (189d) | 30 | 66.7% | +11.43% | -6.56% | +5.43% | +7.5% | -2.07pp | -4.14pp |
| 12M (252d) | 30 | 76.7% | +14.73% | -11.41% | +8.63% | +10.0% | -1.37pp | -4.40pp |

**CURVE_steepen_40bps_CURRENT_EXTREME **CURRENT**** | threshold=40 | direction=UP | bullish=True | events n=17

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 17 | 76.5% | +4.36% | -3.83% | +2.43% | +0.5% | +1.93pp | +0.79pp |
| 3M (63d) | 17 | 70.6% | +8.19% | -8.48% | +3.29% | +2.5% | +0.79pp | +2.31pp |
| 6M (126d) | 17 | 52.9% | +17.72% | -9.19% | +5.06% | +5.0% | +0.06pp | +1.57pp |
| 9M (189d) | 17 | 64.7% | +20.79% | -11.57% | +9.37% | +7.5% | +1.87pp | +4.60pp |
| 12M (252d) | 17 | 58.8% | +29.11% | -13.20% | +11.69% | +10.0% | +1.69pp | +6.21pp |

---

## 15. GSR: full sweep data

**CONFIG RARE:** `{"pct_4wk": 5.0}`

**CONFIG EXTREME:** `{"pct_4wk": 8.0}`

**Primary horizon:** 3M (63d)

| Band | Current? | Threshold | n | Hit @ primary | PW expected | Excess |
|------|----------|-----------|---|---------------|-------------|--------|
| GSR_up_2pct |  | 2 | 147 | 33.8% | +1.66% | -0.84pp |
| GSR_up_3pct |  | 3 | 135 | 34.6% | +1.53% | -0.97pp |
| GSR_up_4pct |  | 4 | 113 | 27.3% | +2.59% | +0.09pp |
| GSR_up_5pct_CURRENT_RARE | Y | 5 | 93 | 24.4% | +3.30% | +0.80pp |
| GSR_up_6pct |  | 6 | 72 | 24.6% | +2.84% | +0.34pp |
| GSR_up_8pct_CURRENT_EXTREME | Y | 8 | 41 | 23.1% | +2.37% | -0.13pp |
| GSR_up_10pct |  | 10 | 21 | 31.6% | +2.35% | -0.15pp |

### 15a. GSR: all horizons per band

**GSR_up_2pct** | threshold=2 | direction=UP | bullish=False | events n=147

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 146 | 37.7% | -3.73% | +3.43% | +0.73% | +0.5% | +0.23pp | +0.42pp |
| 3M (63d) | 145 | 33.8% | -6.31% | +5.72% | +1.66% | +2.5% | -0.84pp | +0.04pp |
| 6M (126d) | 144 | 31.2% | -8.40% | +9.31% | +3.78% | +5.0% | -1.22pp | +1.50pp |
| 9M (189d) | 143 | 26.6% | -11.91% | +13.24% | +6.55% | +7.5% | -0.95pp | +2.43pp |
| 12M (252d) | 142 | 25.4% | -14.95% | +16.34% | +8.41% | +10.0% | -1.59pp | +2.67pp |

**GSR_up_3pct** | threshold=3 | direction=UP | bullish=False | events n=135

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 134 | 38.1% | -4.32% | +3.31% | +0.40% | +0.5% | -0.10pp | -0.24pp |
| 3M (63d) | 133 | 34.6% | -6.37% | +5.71% | +1.53% | +2.5% | -0.97pp | -0.31pp |
| 6M (126d) | 132 | 27.3% | -7.66% | +9.29% | +4.67% | +5.0% | -0.33pp | +1.26pp |
| 9M (189d) | 131 | 27.5% | -12.09% | +13.72% | +6.63% | +7.5% | -0.87pp | +0.81pp |
| 12M (252d) | 130 | 25.4% | -14.85% | +16.44% | +8.50% | +10.0% | -1.50pp | +2.53pp |

**GSR_up_4pct** | threshold=4 | direction=UP | bullish=False | events n=113

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 111 | 32.4% | -3.66% | +3.72% | +1.32% | +0.5% | +0.82pp | +0.67pp |
| 3M (63d) | 110 | 27.3% | -6.42% | +5.96% | +2.59% | +2.5% | +0.09pp | +0.30pp |
| 6M (126d) | 109 | 26.6% | -6.34% | +9.88% | +5.57% | +5.0% | +0.57pp | +1.99pp |
| 9M (189d) | 108 | 25.0% | -10.56% | +14.21% | +8.02% | +7.5% | +0.52pp | +1.28pp |
| 12M (252d) | 108 | 23.1% | -13.44% | +16.93% | +9.90% | +10.0% | -0.10pp | +1.57pp |

**GSR_up_5pct_CURRENT_RARE **CURRENT**** | threshold=5 | direction=UP | bullish=False | events n=93

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 91 | 26.4% | -4.15% | +3.95% | +1.82% | +0.5% | +1.32pp | +1.60pp |
| 3M (63d) | 90 | 24.4% | -6.18% | +6.37% | +3.30% | +2.5% | +0.80pp | +1.44pp |
| 6M (126d) | 89 | 27.0% | -6.53% | +10.39% | +5.83% | +5.0% | +0.83pp | +2.60pp |
| 9M (189d) | 89 | 22.5% | -11.71% | +14.85% | +8.89% | +7.5% | +1.39pp | +3.78pp |
| 12M (252d) | 89 | 22.5% | -14.30% | +18.00% | +10.74% | +10.0% | +0.74pp | +4.17pp |

**GSR_up_6pct** | threshold=6 | direction=UP | bullish=False | events n=72

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 70 | 30.0% | -3.44% | +3.64% | +1.52% | +0.5% | +1.02pp | +1.03pp |
| 3M (63d) | 69 | 24.6% | -6.92% | +6.03% | +2.84% | +2.5% | +0.34pp | +0.61pp |
| 6M (126d) | 68 | 29.4% | -7.47% | +11.36% | +5.82% | +5.0% | +0.82pp | +2.22pp |
| 9M (189d) | 68 | 19.1% | -13.33% | +14.20% | +8.94% | +7.5% | +1.44pp | +2.51pp |
| 12M (252d) | 68 | 20.6% | -13.25% | +18.35% | +11.84% | +10.0% | +1.84pp | +3.86pp |

**GSR_up_8pct_CURRENT_EXTREME **CURRENT**** | threshold=8 | direction=UP | bullish=False | events n=41

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 40 | 35.0% | -4.32% | +4.91% | +1.68% | +0.5% | +1.18pp | +1.46pp |
| 3M (63d) | 39 | 23.1% | -12.03% | +6.69% | +2.37% | +2.5% | -0.13pp | +1.77pp |
| 6M (126d) | 38 | 28.9% | -12.68% | +12.33% | +5.09% | +5.0% | +0.09pp | +2.98pp |
| 9M (189d) | 38 | 21.1% | -14.62% | +14.25% | +8.17% | +7.5% | +0.67pp | +2.75pp |
| 12M (252d) | 38 | 18.4% | -15.38% | +17.04% | +11.07% | +10.0% | +1.07pp | +4.01pp |

**GSR_up_10pct** | threshold=10 | direction=UP | bullish=False | events n=21

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 20 | 40.0% | -4.79% | +6.44% | +1.95% | +0.5% | +1.45pp | -0.40pp |
| 3M (63d) | 19 | 31.6% | -11.37% | +8.68% | +2.35% | +2.5% | -0.15pp | +1.31pp |
| 6M (126d) | 18 | 38.9% | -14.03% | +16.00% | +4.32% | +5.0% | -0.68pp | +0.84pp |
| 9M (189d) | 18 | 16.7% | -23.61% | +15.09% | +8.64% | +7.5% | +1.14pp | -1.00pp |
| 12M (252d) | 18 | 16.7% | -17.74% | +17.27% | +11.43% | +10.0% | +1.43pp | +0.19pp |

---

## 16. HY: full sweep data

**CONFIG RARE:** `{"abs_bps": 400, "high_pctile": 80}`

**CONFIG EXTREME:** `{"abs_bps": 500, "high_pctile": 95}`

**Primary horizon:** 3M (63d)

| Band | Current? | Threshold | n | Hit @ primary | PW expected | Excess |
|------|----------|-----------|---|---------------|-------------|--------|
| HY_300bps |  | 300 | 73 | 13.6% | +4.24% | +1.74pp |
| HY_350bps |  | 350 | 45 | 17.8% | +4.86% | +2.36pp |
| HY_400bps_CURRENT_RARE | Y | 400 | 42 | 45.2% | +3.32% | +0.82pp |
| HY_450bps |  | 450 | 40 | 25.0% | +3.98% | +1.48pp |
| HY_500bps_CURRENT_EXTREME | Y | 500 | 28 | 35.7% | +1.45% | -1.05pp |
| HY_600bps |  | 600 | 25 | 28.0% | +4.35% | +1.85pp |
| HY_pctile_70plus |  | 70 | 12 | 9.1% | +12.33% | +9.83pp |
| HY_pctile_75plus |  | 75 | 10 | 10.0% | +12.32% | +9.82pp |

### 16a. HY: all horizons per band

**HY_300bps** | threshold=300 | direction=UP | bullish=False | events n=73

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 71 | 33.8% | -2.71% | +2.78% | +0.92% | +0.5% | +0.42pp | +0.63pp |
| 3M (63d) | 66 | 13.6% | -2.41% | +5.29% | +4.24% | +2.5% | +1.74pp | +3.00pp |
| 6M (126d) | 55 | 5.5% | -2.39% | +10.61% | +9.90% | +5.0% | +4.90pp | +6.40pp |
| 9M (189d) | 47 | 2.1% | -9.07% | +13.12% | +12.65% | +7.5% | +5.15pp | +4.35pp |
| 12M (252d) | 38 | 13.2% | -5.17% | +13.51% | +11.05% | +10.0% | +1.05pp | +0.22pp |

**HY_350bps** | threshold=350 | direction=UP | bullish=False | events n=45

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 45 | 31.1% | -3.53% | +3.61% | +1.39% | +0.5% | +0.89pp | +0.39pp |
| 3M (63d) | 45 | 17.8% | -6.38% | +7.29% | +4.86% | +2.5% | +2.36pp | +2.68pp |
| 6M (126d) | 44 | 18.2% | -10.50% | +12.51% | +8.32% | +5.0% | +3.32pp | +5.16pp |
| 9M (189d) | 43 | 23.3% | -11.45% | +15.08% | +8.91% | +7.5% | +1.41pp | +4.57pp |
| 12M (252d) | 41 | 22.0% | -12.49% | +21.49% | +14.03% | +10.0% | +4.03pp | +8.04pp |

**HY_400bps_CURRENT_RARE **CURRENT**** | threshold=400 | direction=UP | bullish=False | events n=42

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 42 | 21.4% | -3.30% | +4.45% | +2.79% | +0.5% | +2.29pp | +2.15pp |
| 3M (63d) | 42 | 45.2% | -4.63% | +9.89% | +3.32% | +2.5% | +0.82pp | +2.84pp |
| 6M (126d) | 42 | 23.8% | -3.39% | +12.88% | +9.01% | +5.0% | +4.01pp | +6.02pp |
| 9M (189d) | 42 | 11.9% | -7.03% | +16.25% | +13.48% | +7.5% | +5.98pp | +9.47pp |
| 12M (252d) | 42 | 19.0% | -10.61% | +22.62% | +16.29% | +10.0% | +6.29pp | +12.33pp |

**HY_450bps** | threshold=450 | direction=UP | bullish=False | events n=40

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 40 | 25.0% | -3.76% | +4.10% | +2.14% | +0.5% | +1.64pp | +2.78pp |
| 3M (63d) | 40 | 25.0% | -4.46% | +6.80% | +3.98% | +2.5% | +1.48pp | +2.27pp |
| 6M (126d) | 40 | 30.0% | -4.52% | +10.17% | +5.76% | +5.0% | +0.76pp | +2.54pp |
| 9M (189d) | 40 | 17.5% | -8.97% | +13.60% | +9.65% | +7.5% | +2.15pp | +4.82pp |
| 12M (252d) | 40 | 25.0% | -13.99% | +15.96% | +8.47% | +10.0% | -1.53pp | +0.64pp |

**HY_500bps_CURRENT_EXTREME **CURRENT**** | threshold=500 | direction=UP | bullish=False | events n=28

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 28 | 42.9% | -4.97% | +2.54% | -0.68% | +0.5% | -1.18pp | -1.05pp |
| 3M (63d) | 28 | 35.7% | -7.78% | +6.57% | +1.45% | +2.5% | -1.05pp | -3.95pp |
| 6M (126d) | 28 | 46.4% | -11.89% | +10.20% | -0.06% | +5.0% | -5.06pp | -11.53pp |
| 9M (189d) | 28 | 60.7% | -10.28% | +14.43% | -0.57% | +7.5% | -8.07pp | -13.07pp |
| 12M (252d) | 28 | 50.0% | -20.82% | +15.32% | -2.75% | +10.0% | -12.75pp | -24.56pp |

**HY_600bps** | threshold=600 | direction=UP | bullish=False | events n=25

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 25 | 36.0% | -3.62% | +4.87% | +1.82% | +0.5% | +1.32pp | n/a |
| 3M (63d) | 25 | 28.0% | -5.75% | +8.28% | +4.35% | +2.5% | +1.85pp | n/a |
| 6M (126d) | 25 | 48.0% | -14.87% | +14.84% | +0.58% | +5.0% | -4.42pp | n/a |
| 9M (189d) | 25 | 48.0% | -19.63% | +17.45% | -0.34% | +7.5% | -7.84pp | n/a |
| 12M (252d) | 25 | 40.0% | -21.62% | +14.93% | +0.31% | +10.0% | -9.69pp | n/a |

**HY_pctile_70plus** | threshold=70 | direction=UP | bullish=False | events n=12

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 12 | 8.3% | -3.13% | +7.35% | +6.48% | +0.5% | +5.98pp | +3.41pp |
| 3M (63d) | 11 | 9.1% | -0.65% | +13.63% | +12.33% | +2.5% | +9.83pp | +7.68pp |
| 6M (126d) | 11 | 9.1% | -1.70% | +19.96% | +17.99% | +5.0% | +12.99pp | +11.45pp |
| 9M (189d) | 11 | 0.0% | +0.00% | +25.81% | +25.81% | +7.5% | +18.31pp | +17.70pp |
| 12M (252d) | 11 | 0.0% | +0.00% | +30.22% | +30.22% | +10.0% | +20.22pp | +20.57pp |

**HY_pctile_75plus** | threshold=75 | direction=UP | bullish=False | events n=10

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 10 | 10.0% | -3.13% | +7.21% | +6.18% | +0.5% | +5.68pp | +3.41pp |
| 3M (63d) | 10 | 10.0% | -0.65% | +13.77% | +12.32% | +2.5% | +9.82pp | +7.32pp |
| 6M (126d) | 10 | 10.0% | -1.70% | +20.31% | +18.11% | +5.0% | +13.11pp | +11.40pp |
| 9M (189d) | 10 | 0.0% | +0.00% | +26.33% | +26.33% | +7.5% | +18.83pp | +18.47pp |
| 12M (252d) | 10 | 0.0% | +0.00% | +30.13% | +30.13% | +10.0% | +20.13pp | +20.49pp |

---

## 17. NFCI: full sweep data

**CONFIG RARE:** `{"high_pctile": 80, "low_pctile": 20, "high_sd": 0.3, "low_sd": -0.3}`

**CONFIG EXTREME:** `{"high_pctile": 95, "low_pctile": 5, "high_sd": 0.8, "low_sd": -0.8}`

**Primary horizon:** 3M (63d)

| Band | Current? | Threshold | n | Hit @ primary | PW expected | Excess |
|------|----------|-----------|---|---------------|-------------|--------|
| NFCI_easy_0.1 |  | -0.1 | 11 | 72.7% | +2.48% | -0.02pp |
| NFCI_easy_0.2 |  | -0.2 | 13 | 53.8% | +1.59% | -0.91pp |
| NFCI_easy_0.3_CURRENT | Y | -0.3 | 12 | 75.0% | +4.42% | +1.92pp |
| NFCI_easy_0.5 |  | -0.5 | 17 | 66.7% | +2.90% | +0.40pp |
| NFCI_easy_0.8 |  | -0.8 | 6 | 66.7% | +0.65% | -1.85pp |
| NFCI_tight_0.3_CURRENT | Y | 0.3 | 8 | 37.5% | +4.42% | +1.92pp |
| NFCI_tight_0.5 |  | 0.5 | 7 | 42.9% | -0.01% | -2.51pp |
| NFCI_tight_0.8 |  | 0.8 | 4 | 50.0% | -5.60% | -8.10pp |

### 17a. NFCI: all horizons per band

**NFCI_easy_0.1** | threshold=-0.1 | direction=DOWN | bullish=True | events n=11

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 11 | 72.7% | +5.12% | -2.69% | +2.99% | +0.5% | +2.49pp | +3.77pp |
| 3M (63d) | 11 | 72.7% | +7.05% | -9.71% | +2.48% | +2.5% | -0.02pp | -3.30pp |
| 6M (126d) | 11 | 63.6% | +11.47% | -5.84% | +5.17% | +5.0% | +0.17pp | -3.10pp |
| 9M (189d) | 11 | 81.8% | +12.50% | -13.74% | +7.73% | +7.5% | +0.23pp | -11.01pp |
| 12M (252d) | 11 | 81.8% | +16.12% | -13.47% | +10.74% | +10.0% | +0.74pp | -16.97pp |

**NFCI_easy_0.2** | threshold=-0.2 | direction=DOWN | bullish=True | events n=13

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 13 | 61.5% | +4.27% | -5.19% | +0.63% | +0.5% | +0.13pp | -1.49pp |
| 3M (63d) | 13 | 53.8% | +7.63% | -5.45% | +1.59% | +2.5% | -0.91pp | -5.24pp |
| 6M (126d) | 13 | 69.2% | +9.03% | -9.32% | +3.39% | +5.0% | -1.61pp | -5.87pp |
| 9M (189d) | 13 | 76.9% | +12.65% | -13.68% | +6.57% | +7.5% | -0.93pp | -8.44pp |
| 12M (252d) | 13 | 76.9% | +20.31% | -16.50% | +11.81% | +10.0% | +1.81pp | -7.41pp |

**NFCI_easy_0.3_CURRENT **CURRENT**** | threshold=-0.3 | direction=DOWN | bullish=True | events n=12

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 12 | 75.0% | +4.89% | -1.35% | +3.33% | +0.5% | +2.83pp | +2.01pp |
| 3M (63d) | 12 | 75.0% | +7.04% | -3.43% | +4.42% | +2.5% | +1.92pp | +1.73pp |
| 6M (126d) | 12 | 83.3% | +12.04% | -8.11% | +8.68% | +5.0% | +3.68pp | +9.04pp |
| 9M (189d) | 12 | 91.7% | +12.37% | -8.83% | +10.61% | +7.5% | +3.11pp | +4.95pp |
| 12M (252d) | 12 | 91.7% | +19.59% | -13.41% | +16.84% | +10.0% | +6.84pp | +12.19pp |

**NFCI_easy_0.5** | threshold=-0.5 | direction=DOWN | bullish=True | events n=17

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 16 | 68.8% | +3.77% | -4.32% | +1.24% | +0.5% | +0.74pp | +2.57pp |
| 3M (63d) | 15 | 66.7% | +8.27% | -7.84% | +2.90% | +2.5% | +0.40pp | +4.85pp |
| 6M (126d) | 15 | 86.7% | +12.38% | -18.81% | +8.22% | +5.0% | +3.22pp | +8.01pp |
| 9M (189d) | 15 | 73.3% | +16.01% | -12.24% | +8.48% | +7.5% | +0.98pp | +5.79pp |
| 12M (252d) | 14 | 78.6% | +22.36% | -17.09% | +13.91% | +10.0% | +3.91pp | +9.03pp |

**NFCI_easy_0.8** | threshold=-0.8 | direction=DOWN | bullish=True | events n=6

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 6 | 66.7% | +3.55% | -1.66% | +1.81% | +0.5% | +1.31pp | +0.71pp |
| 3M (63d) | 6 | 66.7% | +2.53% | -3.11% | +0.65% | +2.5% | -1.85pp | -1.97pp |
| 6M (126d) | 6 | 83.3% | +4.03% | -5.80% | +2.39% | +5.0% | -2.61pp | -0.77pp |
| 9M (189d) | 6 | 100.0% | +8.34% | +0.00% | +8.34% | +7.5% | +0.84pp | +6.27pp |
| 12M (252d) | 6 | 100.0% | +13.37% | +0.00% | +13.37% | +10.0% | +3.37pp | +10.17pp |

**NFCI_tight_0.3_CURRENT **CURRENT**** | threshold=0.3 | direction=UP | bullish=False | events n=8

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 8 | 25.0% | -1.30% | +4.47% | +3.03% | +0.5% | +2.53pp | +0.60pp |
| 3M (63d) | 8 | 37.5% | -1.56% | +8.01% | +4.42% | +2.5% | +1.92pp | -0.86pp |
| 6M (126d) | 8 | 12.5% | -3.84% | +10.43% | +8.65% | +5.0% | +3.65pp | -2.26pp |
| 9M (189d) | 8 | 25.0% | -6.08% | +15.49% | +10.10% | +7.5% | +2.60pp | -5.78pp |
| 12M (252d) | 8 | 12.5% | -44.47% | +16.79% | +9.13% | +10.0% | -0.87pp | -7.86pp |

**NFCI_tight_0.5** | threshold=0.5 | direction=UP | bullish=False | events n=7

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 7 | 71.4% | -3.55% | +3.24% | -1.61% | +0.5% | -2.11pp | +1.60pp |
| 3M (63d) | 7 | 42.9% | -6.60% | +4.93% | -0.01% | +2.5% | -2.51pp | -1.52pp |
| 6M (126d) | 7 | 42.9% | -16.32% | +5.55% | -3.82% | +5.0% | -8.82pp | -2.37pp |
| 9M (189d) | 7 | 57.1% | -25.17% | +10.03% | -10.08% | +7.5% | -17.58pp | -7.58pp |
| 12M (252d) | 7 | 42.9% | -35.62% | +9.29% | -9.96% | +10.0% | -19.96pp | -7.31pp |

**NFCI_tight_0.8** | threshold=0.8 | direction=UP | bullish=False | events n=4

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 4 | 50.0% | -5.31% | +4.98% | -0.17% | +0.5% | -0.67pp | n/a |
| 3M (63d) | 4 | 50.0% | -15.29% | +4.09% | -5.60% | +2.5% | -8.10pp | n/a |
| 6M (126d) | 4 | 50.0% | -24.83% | +3.89% | -10.47% | +5.0% | -15.47pp | n/a |
| 9M (189d) | 4 | 50.0% | -30.50% | +6.89% | -11.81% | +7.5% | -19.31pp | n/a |
| 12M (252d) | 4 | 50.0% | -34.07% | +8.90% | -12.58% | +10.0% | -22.58pp | n/a |

---

## 18. VIX: full sweep data

**CONFIG RARE:** `{"abs_level": 25, "high_pctile": 80}`

**CONFIG EXTREME:** `{"abs_level": 35, "high_pctile": 95}`

**Primary horizon:** 3M (63d)

| Band | Current? | Threshold | n | Hit @ primary | PW expected | Excess |
|------|----------|-----------|---|---------------|-------------|--------|
| VIX_15plus |  | 15 | 79 | 29.1% | +3.04% | +0.54pp |
| VIX_18plus |  | 18 | 78 | 28.2% | +3.24% | +0.74pp |
| VIX_20plus |  | 20 | 78 | 28.2% | +3.43% | +0.93pp |
| VIX_25plus_CURRENT_RARE | Y | 25 | 72 | 26.4% | +3.87% | +1.37pp |
| VIX_28plus |  | 28 | 54 | 22.6% | +5.01% | +2.51pp |
| VIX_30plus |  | 30 | 39 | 13.2% | +6.09% | +3.59pp |
| VIX_35plus_CURRENT_EXTREME | Y | 35 | 19 | 10.5% | +7.91% | +5.41pp |
| VIX_40plus |  | 40 | 12 | 25.0% | +7.37% | +4.87pp |
| VIX_pctile_65_79 |  | 65 | 143 | 33.6% | +2.27% | -0.23pp |

### 18a. VIX: all horizons per band

**VIX_15plus** | threshold=15 | direction=UP | bullish=False | events n=79

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 79 | 39.2% | -5.12% | +4.06% | +0.46% | +0.5% | -0.04pp | +0.80pp |
| 3M (63d) | 79 | 29.1% | -7.59% | +7.41% | +3.04% | +2.5% | +0.54pp | +1.27pp |
| 6M (126d) | 78 | 32.1% | -8.28% | +11.13% | +4.91% | +5.0% | -0.09pp | +1.23pp |
| 9M (189d) | 78 | 29.5% | -15.24% | +15.47% | +6.41% | +7.5% | -1.09pp | +2.41pp |
| 12M (252d) | 78 | 26.9% | -18.89% | +18.30% | +8.29% | +10.0% | -1.71pp | +2.55pp |

**VIX_18plus** | threshold=18 | direction=UP | bullish=False | events n=78

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 78 | 39.7% | -5.12% | +4.12% | +0.45% | +0.5% | -0.05pp | +0.80pp |
| 3M (63d) | 78 | 28.2% | -7.36% | +7.41% | +3.24% | +2.5% | +0.74pp | +1.27pp |
| 6M (126d) | 77 | 31.2% | -8.24% | +11.13% | +5.09% | +5.0% | +0.09pp | +1.23pp |
| 9M (189d) | 77 | 29.9% | -15.24% | +15.70% | +6.46% | +7.5% | -1.04pp | +2.41pp |
| 12M (252d) | 77 | 27.3% | -18.89% | +18.53% | +8.32% | +10.0% | -1.68pp | +2.55pp |

**VIX_20plus** | threshold=20 | direction=UP | bullish=False | events n=78

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 78 | 39.7% | -4.98% | +4.24% | +0.57% | +0.5% | +0.07pp | +0.85pp |
| 3M (63d) | 78 | 28.2% | -7.36% | +7.66% | +3.43% | +2.5% | +0.93pp | +1.48pp |
| 6M (126d) | 77 | 31.2% | -8.24% | +11.64% | +5.44% | +5.0% | +0.44pp | +1.38pp |
| 9M (189d) | 77 | 29.9% | -15.24% | +15.77% | +6.51% | +7.5% | -0.99pp | +2.06pp |
| 12M (252d) | 77 | 27.3% | -18.89% | +18.88% | +8.58% | +10.0% | -1.42pp | +2.73pp |

**VIX_25plus_CURRENT_RARE **CURRENT**** | threshold=25 | direction=UP | bullish=False | events n=72

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 72 | 36.1% | -5.22% | +5.01% | +1.31% | +0.5% | +0.81pp | +1.57pp |
| 3M (63d) | 72 | 26.4% | -8.00% | +8.13% | +3.87% | +2.5% | +1.37pp | +2.86pp |
| 6M (126d) | 71 | 31.0% | -8.95% | +12.49% | +5.85% | +5.0% | +0.85pp | +1.66pp |
| 9M (189d) | 71 | 31.0% | -14.72% | +14.11% | +5.18% | +7.5% | -2.32pp | -1.51pp |
| 12M (252d) | 71 | 29.6% | -18.69% | +17.58% | +6.85% | +10.0% | -3.15pp | -1.92pp |

**VIX_28plus** | threshold=28 | direction=UP | bullish=False | events n=54

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 54 | 33.3% | -4.01% | +5.92% | +2.61% | +0.5% | +2.11pp | +4.14pp |
| 3M (63d) | 53 | 22.6% | -9.35% | +9.21% | +5.01% | +2.5% | +2.51pp | +6.80pp |
| 6M (126d) | 52 | 28.8% | -8.75% | +15.68% | +8.63% | +5.0% | +3.63pp | +6.18pp |
| 9M (189d) | 52 | 30.8% | -13.89% | +18.64% | +8.63% | +7.5% | +1.13pp | +4.64pp |
| 12M (252d) | 52 | 28.8% | -17.94% | +23.22% | +11.35% | +10.0% | +1.35pp | +6.53pp |

**VIX_30plus** | threshold=30 | direction=UP | bullish=False | events n=39

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 39 | 30.8% | -5.42% | +6.89% | +3.10% | +0.5% | +2.60pp | +4.60pp |
| 3M (63d) | 38 | 13.2% | -11.01% | +8.68% | +6.09% | +2.5% | +3.59pp | +5.85pp |
| 6M (126d) | 38 | 23.7% | -9.83% | +16.43% | +10.21% | +5.0% | +5.21pp | +5.73pp |
| 9M (189d) | 38 | 23.7% | -13.15% | +19.93% | +12.10% | +7.5% | +4.60pp | +5.02pp |
| 12M (252d) | 38 | 23.7% | -13.96% | +24.60% | +15.46% | +10.0% | +5.46pp | +5.27pp |

**VIX_35plus_CURRENT_EXTREME **CURRENT**** | threshold=35 | direction=UP | bullish=False | events n=19

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 19 | 31.6% | -7.28% | +7.23% | +2.65% | +0.5% | +2.15pp | +5.91pp |
| 3M (63d) | 19 | 10.5% | -8.55% | +9.85% | +7.91% | +2.5% | +5.41pp | +13.69pp |
| 6M (126d) | 19 | 10.5% | -16.83% | +18.67% | +14.93% | +5.0% | +9.93pp | +19.24pp |
| 9M (189d) | 19 | 10.5% | -18.66% | +21.12% | +16.93% | +7.5% | +9.43pp | +19.73pp |
| 12M (252d) | 19 | 15.8% | -13.98% | +27.16% | +20.66% | +10.0% | +10.66pp | +16.85pp |

**VIX_40plus** | threshold=40 | direction=UP | bullish=False | events n=12

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 12 | 33.3% | -8.67% | +6.87% | +1.69% | +0.5% | +1.19pp | +5.49pp |
| 3M (63d) | 12 | 25.0% | -6.88% | +12.13% | +7.37% | +2.5% | +4.87pp | +19.16pp |
| 6M (126d) | 12 | 16.7% | -12.22% | +19.79% | +14.45% | +5.0% | +9.45pp | +26.43pp |
| 9M (189d) | 12 | 8.3% | -19.85% | +21.64% | +18.18% | +7.5% | +10.68pp | +29.36pp |
| 12M (252d) | 12 | 16.7% | -9.51% | +27.47% | +21.31% | +10.0% | +11.31pp | +24.39pp |

**VIX_pctile_65_79** | threshold=65 | direction=UP | bullish=False | events n=143

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 141 | 33.3% | -4.06% | +4.03% | +1.33% | +0.5% | +0.83pp | +1.13pp |
| 3M (63d) | 140 | 33.6% | -8.12% | +7.53% | +2.27% | +2.5% | -0.23pp | +0.31pp |
| 6M (126d) | 139 | 30.9% | -11.05% | +10.51% | +3.84% | +5.0% | -1.16pp | +0.90pp |
| 9M (189d) | 137 | 28.5% | -16.00% | +13.89% | +5.38% | +7.5% | -2.12pp | +1.38pp |
| 12M (252d) | 136 | 30.9% | -17.41% | +18.30% | +7.27% | +10.0% | -2.73pp | +2.38pp |

---

## 19. VXTS: full sweep data

**CONFIG RARE:** `{"low_ratio": 0.95, "high_ratio": 1.1}`

**CONFIG EXTREME:** `{"low_ratio": 0.85, "high_ratio": 1.2}`

**Primary horizon:** 3M (63d)

| Band | Current? | Threshold | n | Hit @ primary | PW expected | Excess |
|------|----------|-----------|---|---------------|-------------|--------|
| VXTS_backward_1.02 |  | 1.02 | 66 | 27.0% | +2.52% | +0.02pp |
| VXTS_backward_1.05 |  | 1.05 | 87 | 28.2% | +2.37% | -0.13pp |
| VXTS_backward_1.10_CURRENT_RARE | Y | 1.1 | 106 | 26.0% | +2.21% | -0.29pp |
| VXTS_backward_1.15 |  | 1.15 | 118 | 26.1% | +2.76% | +0.26pp |
| VXTS_backward_1.20_CURRENT_EXTREME | Y | 1.2 | 88 | 34.9% | +1.61% | -0.89pp |
| VXTS_contango_0.95_CURRENT_RARE | Y | 0.95 | 27 | 76.9% | +4.34% | +1.84pp |
| VXTS_contango_0.90 |  | 0.9 | 12 | 83.3% | +4.59% | +2.09pp |
| VXTS_contango_0.85_CURRENT_EXTREME | Y | 0.85 | 4 | 75.0% | +3.93% | +1.43pp |
| VXTS_contango_0.80 |  | 0.8 | 2 | 50.0% | -0.09% | -2.59pp |

### 19a. VXTS: all horizons per band

**VXTS_backward_1.02** | threshold=1.02 | direction=UP | bullish=False | events n=66

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 65 | 26.2% | -4.38% | +3.47% | +1.42% | +0.5% | +0.92pp | +0.20pp |
| 3M (63d) | 63 | 27.0% | -6.93% | +6.01% | +2.52% | +2.5% | +0.02pp | +1.01pp |
| 6M (126d) | 62 | 25.8% | -8.50% | +9.50% | +4.85% | +5.0% | -0.15pp | +0.25pp |
| 9M (189d) | 62 | 32.3% | -12.46% | +12.84% | +4.68% | +7.5% | -2.82pp | -2.90pp |
| 12M (252d) | 62 | 25.8% | -20.12% | +16.62% | +7.14% | +10.0% | -2.86pp | -3.28pp |

**VXTS_backward_1.05** | threshold=1.05 | direction=UP | bullish=False | events n=87

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 86 | 29.1% | -5.20% | +3.22% | +0.78% | +0.5% | +0.28pp | +0.65pp |
| 3M (63d) | 85 | 28.2% | -7.13% | +6.11% | +2.37% | +2.5% | -0.13pp | +1.63pp |
| 6M (126d) | 84 | 28.6% | -10.88% | +10.24% | +4.20% | +5.0% | -0.80pp | +0.66pp |
| 9M (189d) | 83 | 27.7% | -13.01% | +13.20% | +5.94% | +7.5% | -1.56pp | -1.97pp |
| 12M (252d) | 82 | 22.0% | -17.90% | +16.84% | +9.22% | +10.0% | -0.78pp | +0.86pp |

**VXTS_backward_1.10_CURRENT_RARE **CURRENT**** | threshold=1.1 | direction=UP | bullish=False | events n=106

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 105 | 32.4% | -4.07% | +3.28% | +0.90% | +0.5% | +0.40pp | -0.06pp |
| 3M (63d) | 104 | 26.0% | -8.20% | +5.85% | +2.21% | +2.5% | -0.29pp | +0.23pp |
| 6M (126d) | 103 | 27.2% | -8.17% | +9.58% | +4.76% | +5.0% | -0.24pp | +0.74pp |
| 9M (189d) | 101 | 21.8% | -9.81% | +12.38% | +7.54% | +7.5% | +0.04pp | +0.50pp |
| 12M (252d) | 99 | 16.2% | -13.45% | +15.24% | +10.60% | +10.0% | +0.60pp | +1.33pp |

**VXTS_backward_1.15** | threshold=1.15 | direction=UP | bullish=False | events n=118

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 117 | 39.3% | -3.77% | +3.13% | +0.42% | +0.5% | -0.08pp | -0.34pp |
| 3M (63d) | 115 | 26.1% | -5.27% | +5.59% | +2.76% | +2.5% | +0.26pp | +0.37pp |
| 6M (126d) | 115 | 25.2% | -7.48% | +9.41% | +5.15% | +5.0% | +0.15pp | +1.49pp |
| 9M (189d) | 113 | 20.4% | -8.52% | +11.99% | +7.81% | +7.5% | +0.31pp | +1.05pp |
| 12M (252d) | 111 | 15.3% | -11.61% | +14.17% | +10.22% | +10.0% | +0.22pp | +2.25pp |

**VXTS_backward_1.20_CURRENT_EXTREME **CURRENT**** | threshold=1.2 | direction=UP | bullish=False | events n=88

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 86 | 39.5% | -3.12% | +2.38% | +0.20% | +0.5% | -0.30pp | -0.82pp |
| 3M (63d) | 86 | 34.9% | -4.82% | +5.06% | +1.61% | +2.5% | -0.89pp | -0.76pp |
| 6M (126d) | 86 | 29.1% | -6.56% | +7.65% | +3.52% | +5.0% | -1.48pp | -0.48pp |
| 9M (189d) | 84 | 22.6% | -6.87% | +11.27% | +7.17% | +7.5% | -0.33pp | +1.20pp |
| 12M (252d) | 81 | 21.0% | -7.05% | +13.16% | +8.92% | +10.0% | -1.08pp | +1.64pp |

**VXTS_contango_0.95_CURRENT_RARE **CURRENT**** | threshold=0.95 | direction=DOWN | bullish=True | events n=27

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 27 | 74.1% | +6.34% | -6.87% | +2.91% | +0.5% | +2.41pp | +3.15pp |
| 3M (63d) | 26 | 76.9% | +9.19% | -11.83% | +4.34% | +2.5% | +1.84pp | +2.80pp |
| 6M (126d) | 25 | 68.0% | +15.31% | -12.06% | +6.55% | +5.0% | +1.55pp | +4.48pp |
| 9M (189d) | 25 | 68.0% | +19.30% | -19.00% | +7.05% | +7.5% | -0.45pp | +1.57pp |
| 12M (252d) | 25 | 68.0% | +22.56% | -23.76% | +7.74% | +10.0% | -2.26pp | +2.27pp |

**VXTS_contango_0.90** | threshold=0.9 | direction=DOWN | bullish=True | events n=12

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 12 | 66.7% | +6.61% | -9.60% | +1.21% | +0.5% | +0.71pp | +4.65pp |
| 3M (63d) | 12 | 83.3% | +9.43% | -19.59% | +4.59% | +2.5% | +2.09pp | +5.69pp |
| 6M (126d) | 12 | 75.0% | +16.63% | -14.72% | +8.80% | +5.0% | +3.80pp | +2.23pp |
| 9M (189d) | 12 | 83.3% | +19.37% | -16.57% | +13.38% | +7.5% | +5.88pp | +1.04pp |
| 12M (252d) | 12 | 75.0% | +27.20% | -11.53% | +17.52% | +10.0% | +7.52pp | -2.40pp |

**VXTS_contango_0.85_CURRENT_EXTREME **CURRENT**** | threshold=0.85 | direction=DOWN | bullish=True | events n=4

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 4 | 25.0% | +10.50% | -8.20% | -3.53% | +0.5% | -4.03pp | n/a |
| 3M (63d) | 4 | 75.0% | +10.45% | -15.63% | +3.93% | +2.5% | +1.43pp | n/a |
| 6M (126d) | 4 | 50.0% | +25.39% | -13.26% | +6.07% | +5.0% | +1.07pp | n/a |
| 9M (189d) | 4 | 75.0% | +21.22% | -19.85% | +10.95% | +7.5% | +3.45pp | n/a |
| 12M (252d) | 4 | 75.0% | +25.50% | -5.35% | +17.79% | +10.0% | +7.79pp | n/a |

**VXTS_contango_0.80** | threshold=0.8 | direction=DOWN | bullish=True | events n=2

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 2 | 50.0% | +2.22% | -11.09% | -4.43% | +0.5% | -4.93pp | n/a |
| 3M (63d) | 2 | 50.0% | +3.05% | -3.22% | -0.09% | +2.5% | -2.59pp | n/a |
| 6M (126d) | 2 | 50.0% | +17.95% | -6.42% | +5.77% | +5.0% | +0.77pp | n/a |
| 9M (189d) | 2 | 100.0% | +11.80% | +0.00% | +11.80% | +7.5% | +4.30pp | n/a |
| 12M (252d) | 2 | 100.0% | +25.88% | +0.00% | +25.88% | +10.0% | +15.88pp | n/a |

---

## 20. WALCL: full sweep data

**CONFIG RARE:** `{"mom_pct": 0.8}`

**CONFIG EXTREME:** `{"mom_pct": 2.0}`

**Primary horizon:** 3M (63d)

| Band | Current? | Threshold | n | Hit @ primary | PW expected | Excess |
|------|----------|-----------|---|---------------|-------------|--------|
| WALCL_expand_0.3 |  | 0.3 | 95 | 70.2% | +2.78% | +0.28pp |
| WALCL_expand_0.5 |  | 0.5 | 86 | 67.1% | +3.04% | +0.54pp |
| WALCL_expand_0.8_CURRENT_RARE | Y | 0.8 | 76 | 68.4% | +2.12% | -0.38pp |
| WALCL_expand_1.5 |  | 1.5 | 52 | 71.2% | +1.99% | -0.51pp |
| WALCL_expand_2.0_CURRENT_EXTREME | Y | 2.0 | 43 | 81.4% | +3.56% | +1.06pp |
| WALCL_expand_3.0 |  | 3.0 | 22 | 68.2% | +2.87% | +0.37pp |
| WALCL_contract_0.3 |  | -0.3 | 89 | 25.8% | +2.86% | +0.36pp |
| WALCL_contract_0.5 |  | -0.5 | 85 | 27.1% | +2.50% | +0.00pp |
| WALCL_contract_0.8_CURRENT_RARE | Y | -0.8 | 66 | 30.3% | +2.49% | -0.01pp |
| WALCL_contract_1.5 |  | -1.5 | 24 | 29.2% | +3.20% | +0.70pp |
| WALCL_contract_2.0_CURRENT_EXTREME | Y | -2.0 | 11 | 27.3% | +2.97% | +0.47pp |

### 20a. WALCL: all horizons per band

**WALCL_expand_0.3** | threshold=0.3 | direction=UP | bullish=True | events n=95

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 94 | 61.7% | +3.19% | -4.16% | +0.38% | +0.5% | -0.12pp | +0.38pp |
| 3M (63d) | 94 | 70.2% | +6.51% | -6.00% | +2.78% | +2.5% | +0.28pp | +0.57pp |
| 6M (126d) | 92 | 73.9% | +9.25% | -11.10% | +3.94% | +5.0% | -1.06pp | +0.65pp |
| 9M (189d) | 92 | 77.2% | +12.21% | -17.01% | +5.54% | +7.5% | -1.96pp | +0.11pp |
| 12M (252d) | 92 | 78.3% | +14.49% | -20.80% | +6.82% | +10.0% | -3.18pp | -0.31pp |

**WALCL_expand_0.5** | threshold=0.5 | direction=UP | bullish=True | events n=86

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 86 | 66.3% | +3.43% | -4.51% | +0.76% | +0.5% | +0.26pp | +0.90pp |
| 3M (63d) | 85 | 67.1% | +7.25% | -5.52% | +3.04% | +2.5% | +0.54pp | +0.43pp |
| 6M (126d) | 83 | 69.9% | +9.41% | -11.43% | +3.13% | +5.0% | -1.87pp | -0.32pp |
| 9M (189d) | 83 | 72.3% | +12.30% | -16.68% | +4.27% | +7.5% | -3.23pp | -1.64pp |
| 12M (252d) | 83 | 72.3% | +14.60% | -19.56% | +5.13% | +10.0% | -4.87pp | -3.13pp |

**WALCL_expand_0.8_CURRENT_RARE **CURRENT**** | threshold=0.8 | direction=UP | bullish=True | events n=76

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 76 | 67.1% | +3.23% | -4.05% | +0.84% | +0.5% | +0.34pp | +1.29pp |
| 3M (63d) | 76 | 68.4% | +6.48% | -7.33% | +2.12% | +2.5% | -0.38pp | +0.53pp |
| 6M (126d) | 75 | 70.7% | +9.24% | -14.15% | +2.38% | +5.0% | -2.62pp | +0.64pp |
| 9M (189d) | 75 | 72.0% | +11.62% | -17.23% | +3.54% | +7.5% | -3.96pp | +0.17pp |
| 12M (252d) | 75 | 73.3% | +14.31% | -20.88% | +4.92% | +10.0% | -5.08pp | -1.40pp |

**WALCL_expand_1.5** | threshold=1.5 | direction=UP | bullish=True | events n=52

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 52 | 65.4% | +3.53% | -4.13% | +0.88% | +0.5% | +0.38pp | +1.86pp |
| 3M (63d) | 52 | 71.2% | +6.18% | -8.35% | +1.99% | +2.5% | -0.51pp | +3.45pp |
| 6M (126d) | 51 | 64.7% | +9.39% | -12.65% | +1.61% | +5.0% | -3.39pp | +2.33pp |
| 9M (189d) | 51 | 66.7% | +11.79% | -15.27% | +2.77% | +7.5% | -4.73pp | +1.56pp |
| 12M (252d) | 51 | 70.6% | +14.32% | -21.20% | +3.87% | +10.0% | -6.13pp | -0.41pp |

**WALCL_expand_2.0_CURRENT_EXTREME **CURRENT**** | threshold=2.0 | direction=UP | bullish=True | events n=43

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 43 | 69.8% | +3.90% | -4.37% | +1.40% | +0.5% | +0.90pp | +2.07pp |
| 3M (63d) | 43 | 81.4% | +6.77% | -10.47% | +3.56% | +2.5% | +1.06pp | +5.73pp |
| 6M (126d) | 43 | 69.8% | +10.53% | -10.61% | +4.14% | +5.0% | -0.86pp | +2.24pp |
| 9M (189d) | 43 | 76.7% | +13.59% | -10.56% | +7.97% | +7.5% | +0.47pp | +1.56pp |
| 12M (252d) | 43 | 79.1% | +17.49% | -16.64% | +10.35% | +10.0% | +0.35pp | +3.37pp |

**WALCL_expand_3.0** | threshold=3.0 | direction=UP | bullish=True | events n=22

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 22 | 72.7% | +3.49% | -6.71% | +0.71% | +0.5% | +0.21pp | +5.58pp |
| 3M (63d) | 22 | 68.2% | +8.19% | -8.52% | +2.87% | +2.5% | +0.37pp | +10.09pp |
| 6M (126d) | 22 | 68.2% | +10.15% | -15.30% | +2.05% | +5.0% | -2.95pp | +8.71pp |
| 9M (189d) | 22 | 63.6% | +17.28% | -10.99% | +7.00% | +7.5% | -0.50pp | +12.99pp |
| 12M (252d) | 22 | 86.4% | +16.71% | -18.66% | +11.89% | +10.0% | +1.89pp | +22.22pp |

**WALCL_contract_0.3** | threshold=-0.3 | direction=DOWN | bullish=False | events n=89

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 89 | 31.5% | -3.18% | +3.34% | +1.29% | +0.5% | +0.79pp | +1.04pp |
| 3M (63d) | 89 | 25.8% | -6.72% | +6.20% | +2.86% | +2.5% | +0.36pp | +0.52pp |
| 6M (126d) | 88 | 22.7% | -10.52% | +8.88% | +4.47% | +5.0% | -0.53pp | -0.20pp |
| 9M (189d) | 87 | 24.1% | -13.27% | +12.47% | +6.26% | +7.5% | -1.24pp | -0.85pp |
| 12M (252d) | 84 | 20.2% | -21.10% | +15.05% | +7.73% | +10.0% | -2.27pp | -2.16pp |

**WALCL_contract_0.5** | threshold=-0.5 | direction=DOWN | bullish=False | events n=85

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 85 | 29.4% | -3.85% | +3.16% | +1.10% | +0.5% | +0.60pp | +0.67pp |
| 3M (63d) | 85 | 27.1% | -6.67% | +5.91% | +2.50% | +2.5% | +0.00pp | +0.46pp |
| 6M (126d) | 84 | 23.8% | -9.04% | +8.25% | +4.13% | +5.0% | -0.87pp | -0.06pp |
| 9M (189d) | 83 | 25.3% | -12.17% | +11.75% | +5.70% | +7.5% | -1.80pp | -1.85pp |
| 12M (252d) | 82 | 20.7% | -19.68% | +15.30% | +8.05% | +10.0% | -1.95pp | -0.93pp |

**WALCL_contract_0.8_CURRENT_RARE **CURRENT**** | threshold=-0.8 | direction=DOWN | bullish=False | events n=66

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 66 | 36.4% | -3.35% | +3.43% | +0.96% | +0.5% | +0.46pp | +0.60pp |
| 3M (63d) | 66 | 30.3% | -6.40% | +6.35% | +2.49% | +2.5% | -0.01pp | +0.71pp |
| 6M (126d) | 66 | 25.8% | -10.51% | +8.23% | +3.41% | +5.0% | -1.59pp | +0.24pp |
| 9M (189d) | 66 | 21.2% | -15.71% | +11.56% | +5.78% | +7.5% | -1.72pp | -0.25pp |
| 12M (252d) | 66 | 21.2% | -19.37% | +15.33% | +7.97% | +10.0% | -2.03pp | -0.49pp |

**WALCL_contract_1.5** | threshold=-1.5 | direction=DOWN | bullish=False | events n=24

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 24 | 41.7% | -2.99% | +2.92% | +0.46% | +0.5% | -0.04pp | +0.00pp |
| 3M (63d) | 24 | 29.2% | -3.58% | +6.00% | +3.20% | +2.5% | +0.70pp | +2.18pp |
| 6M (126d) | 24 | 25.0% | -2.89% | +8.43% | +5.60% | +5.0% | +0.60pp | +2.08pp |
| 9M (189d) | 24 | 16.7% | -11.32% | +15.04% | +10.65% | +7.5% | +3.15pp | +6.04pp |
| 12M (252d) | 24 | 12.5% | -17.24% | +18.70% | +14.21% | +10.0% | +4.21pp | +6.07pp |

**WALCL_contract_2.0_CURRENT_EXTREME **CURRENT**** | threshold=-2.0 | direction=DOWN | bullish=False | events n=11

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 11 | 63.6% | -3.76% | +3.35% | -1.18% | +0.5% | -1.68pp | -1.43pp |
| 3M (63d) | 11 | 27.3% | -3.49% | +5.40% | +2.97% | +2.5% | +0.47pp | +1.07pp |
| 6M (126d) | 11 | 36.4% | -4.06% | +9.23% | +4.40% | +5.0% | -0.60pp | -3.91pp |
| 9M (189d) | 11 | 27.3% | -10.60% | +15.73% | +8.55% | +7.5% | +1.05pp | -0.15pp |
| 12M (252d) | 11 | 18.2% | -22.82% | +17.02% | +9.78% | +10.0% | -0.22pp | -6.75pp |

---

## 21. WTI: full sweep data

**CONFIG RARE:** `{"pct_4wk": 6.0}`

**CONFIG EXTREME:** `{"pct_4wk": 10.0}`

**Primary horizon:** 6M (126d)

| Band | Current? | Threshold | n | Hit @ primary | PW expected | Excess |
|------|----------|-----------|---|---------------|-------------|--------|
| WTI_down_3pct |  | -3 | 139 | 72.4% | +4.66% | -0.34pp |
| WTI_down_5pct |  | -5 | 121 | 67.8% | +4.28% | -0.72pp |
| WTI_down_6pct_CURRENT_RARE | Y | -6 | 116 | 67.9% | +4.35% | -0.65pp |
| WTI_down_8pct |  | -8 | 90 | 68.6% | +3.34% | -1.66pp |
| WTI_down_10pct_CURRENT_EXTREME | Y | -10 | 73 | 68.6% | +3.52% | -1.48pp |
| WTI_down_15pct |  | -15 | 31 | 73.3% | +5.16% | +0.16pp |
| WTI_up_5pct |  | 5 | 142 | 30.9% | +3.22% | -1.78pp |
| WTI_up_6pct_CURRENT_RARE | Y | 6 | 134 | 31.5% | +3.01% | -1.99pp |
| WTI_up_8pct |  | 8 | 119 | 27.8% | +3.47% | -1.53pp |
| WTI_up_10pct_CURRENT_EXTREME | Y | 10 | 96 | 33.3% | +1.87% | -3.13pp |
| WTI_up_15pct |  | 15 | 42 | 37.5% | +2.81% | -2.19pp |

### 21a. WTI: all horizons per band

**WTI_down_3pct** | threshold=-3 | direction=DOWN | bullish=True | events n=139

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 137 | 66.4% | +3.76% | -3.87% | +1.20% | +0.5% | +0.70pp | +1.03pp |
| 3M (63d) | 136 | 71.3% | +6.42% | -6.84% | +2.62% | +2.5% | +0.12pp | +0.70pp |
| 6M (126d) | 134 | 72.4% | +10.04% | -9.44% | +4.66% | +5.0% | -0.34pp | +1.32pp |
| 9M (189d) | 132 | 78.8% | +13.05% | -11.61% | +7.82% | +7.5% | +0.32pp | +1.71pp |
| 12M (252d) | 129 | 80.6% | +15.66% | -16.12% | +9.50% | +10.0% | -0.50pp | +2.04pp |

**WTI_down_5pct** | threshold=-5 | direction=DOWN | bullish=True | events n=121

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 119 | 63.9% | +3.64% | -4.61% | +0.66% | +0.5% | +0.16pp | +0.30pp |
| 3M (63d) | 118 | 68.6% | +6.59% | -6.45% | +2.50% | +2.5% | +0.00pp | -0.22pp |
| 6M (126d) | 118 | 67.8% | +10.39% | -8.59% | +4.28% | +5.0% | -0.72pp | -0.38pp |
| 9M (189d) | 116 | 79.3% | +12.95% | -13.57% | +7.46% | +7.5% | -0.04pp | +0.77pp |
| 12M (252d) | 114 | 79.8% | +15.57% | -17.32% | +8.94% | +10.0% | -1.06pp | +0.87pp |

**WTI_down_6pct_CURRENT_RARE **CURRENT**** | threshold=-6 | direction=DOWN | bullish=True | events n=116

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 114 | 65.8% | +3.59% | -4.11% | +0.96% | +0.5% | +0.46pp | +0.43pp |
| 3M (63d) | 112 | 71.4% | +6.39% | -6.84% | +2.61% | +2.5% | +0.11pp | -0.82pp |
| 6M (126d) | 112 | 67.9% | +10.37% | -8.35% | +4.35% | +5.0% | -0.65pp | -0.98pp |
| 9M (189d) | 111 | 77.5% | +13.16% | -13.25% | +7.21% | +7.5% | -0.29pp | -0.14pp |
| 12M (252d) | 109 | 78.9% | +15.70% | -17.18% | +8.76% | +10.0% | -1.24pp | -0.30pp |

**WTI_down_8pct** | threshold=-8 | direction=DOWN | bullish=True | events n=90

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 88 | 64.8% | +3.70% | -5.41% | +0.49% | +0.5% | -0.01pp | +0.80pp |
| 3M (63d) | 86 | 68.6% | +6.53% | -8.59% | +1.78% | +2.5% | -0.72pp | -0.21pp |
| 6M (126d) | 86 | 68.6% | +10.02% | -11.26% | +3.34% | +5.0% | -1.66pp | -0.92pp |
| 9M (189d) | 85 | 72.9% | +13.67% | -15.47% | +5.79% | +7.5% | -1.71pp | +0.59pp |
| 12M (252d) | 84 | 73.8% | +16.63% | -15.61% | +8.19% | +10.0% | -1.81pp | +1.45pp |

**WTI_down_10pct_CURRENT_EXTREME **CURRENT**** | threshold=-10 | direction=DOWN | bullish=True | events n=73

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 71 | 63.4% | +3.56% | -5.47% | +0.25% | +0.5% | -0.25pp | +0.85pp |
| 3M (63d) | 70 | 65.7% | +6.58% | -9.53% | +1.06% | +2.5% | -1.44pp | +0.16pp |
| 6M (126d) | 70 | 68.6% | +9.73% | -10.01% | +3.52% | +5.0% | -1.48pp | +0.40pp |
| 9M (189d) | 70 | 75.7% | +13.85% | -13.38% | +7.24% | +7.5% | -0.26pp | +1.61pp |
| 12M (252d) | 69 | 76.8% | +16.74% | -11.04% | +10.30% | +10.0% | +0.30pp | +2.73pp |

**WTI_down_15pct** | threshold=-15 | direction=DOWN | bullish=True | events n=31

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 30 | 76.7% | +3.40% | -6.07% | +1.19% | +0.5% | +0.69pp | +0.63pp |
| 3M (63d) | 30 | 63.3% | +7.11% | -7.44% | +1.78% | +2.5% | -0.72pp | -1.15pp |
| 6M (126d) | 30 | 73.3% | +10.56% | -9.67% | +5.16% | +5.0% | +0.16pp | +1.15pp |
| 9M (189d) | 30 | 70.0% | +14.84% | -13.03% | +6.48% | +7.5% | -1.02pp | -1.64pp |
| 12M (252d) | 30 | 73.3% | +17.60% | -14.11% | +9.14% | +10.0% | -0.86pp | +0.45pp |

**WTI_up_5pct** | threshold=5 | direction=UP | bullish=False | events n=142

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 141 | 36.9% | -3.77% | +2.87% | +0.42% | +0.5% | -0.08pp | +0.44pp |
| 3M (63d) | 141 | 30.5% | -5.35% | +5.46% | +2.16% | +2.5% | -0.34pp | +0.42pp |
| 6M (126d) | 139 | 30.9% | -9.32% | +8.84% | +3.22% | +5.0% | -1.78pp | +0.86pp |
| 9M (189d) | 139 | 25.2% | -13.24% | +11.66% | +5.39% | +7.5% | -2.11pp | -0.32pp |
| 12M (252d) | 139 | 24.5% | -14.01% | +15.06% | +7.95% | +10.0% | -2.05pp | -1.05pp |

**WTI_up_6pct_CURRENT_RARE **CURRENT**** | threshold=6 | direction=UP | bullish=False | events n=134

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 133 | 37.6% | -4.19% | +2.76% | +0.15% | +0.5% | -0.35pp | +0.24pp |
| 3M (63d) | 133 | 31.6% | -5.48% | +5.39% | +1.95% | +2.5% | -0.55pp | +0.59pp |
| 6M (126d) | 130 | 31.5% | -9.98% | +9.00% | +3.01% | +5.0% | -1.99pp | +1.14pp |
| 9M (189d) | 130 | 25.4% | -14.17% | +11.56% | +5.03% | +7.5% | -2.47pp | +0.04pp |
| 12M (252d) | 129 | 25.6% | -14.96% | +14.93% | +7.28% | +10.0% | -2.72pp | -0.30pp |

**WTI_up_8pct** | threshold=8 | direction=UP | bullish=False | events n=119

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 118 | 42.4% | -3.81% | +3.10% | +0.17% | +0.5% | -0.33pp | -0.32pp |
| 3M (63d) | 118 | 30.5% | -5.54% | +5.65% | +2.24% | +2.5% | -0.26pp | +0.58pp |
| 6M (126d) | 115 | 27.8% | -10.33% | +8.79% | +3.47% | +5.0% | -1.53pp | +0.55pp |
| 9M (189d) | 115 | 27.0% | -13.85% | +11.86% | +4.93% | +7.5% | -2.57pp | -0.29pp |
| 12M (252d) | 114 | 25.4% | -16.16% | +14.99% | +7.07% | +10.0% | -2.93pp | -0.39pp |

**WTI_up_10pct_CURRENT_EXTREME **CURRENT**** | threshold=10 | direction=UP | bullish=False | events n=96

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 95 | 43.2% | -3.60% | +3.12% | +0.22% | +0.5% | -0.28pp | -0.56pp |
| 3M (63d) | 95 | 35.8% | -5.79% | +5.93% | +1.73% | +2.5% | -0.77pp | +0.70pp |
| 6M (126d) | 93 | 33.3% | -12.42% | +9.01% | +1.87% | +5.0% | -3.13pp | +0.02pp |
| 9M (189d) | 93 | 29.0% | -17.49% | +11.96% | +3.41% | +7.5% | -4.09pp | -0.31pp |
| 12M (252d) | 92 | 30.4% | -19.13% | +15.55% | +4.99% | +10.0% | -5.01pp | -1.13pp |

**WTI_up_15pct** | threshold=15 | direction=UP | bullish=False | events n=42

| Horizon | n | Hit rate | Avg win | Avg loss | PW expected | Benchmark | Excess | Hostile excess |
|---------|---|----------|---------|----------|-------------|-----------|--------|----------------|
| 1M (21d) | 41 | 39.0% | -4.10% | +3.07% | +0.27% | +0.5% | -0.23pp | -0.12pp |
| 3M (63d) | 41 | 31.7% | -7.45% | +6.74% | +2.24% | +2.5% | -0.26pp | +0.19pp |
| 6M (126d) | 40 | 37.5% | -10.91% | +11.04% | +2.81% | +5.0% | -2.19pp | -1.42pp |
| 9M (189d) | 40 | 32.5% | -17.24% | +14.71% | +4.33% | +7.5% | -3.17pp | +0.50pp |
| 12M (252d) | 39 | 30.8% | -19.41% | +17.79% | +6.35% | +10.0% | -3.65pp | +2.87pp |

---
## 22. Combo B (Capitulation): gate sweep detail

**Combo:** `B`
**Validated Horizon:** `spx_3m`
**Direction:** `bullish`
**Current Gates:** `{'all_required': ['VIX', 'HY', 'CFTC'], 'vix_min': 25, 'hy_bps_min': 400, 'cftc_max_pctile': 15}`
**Note:** `Leg replay on daily_readings (0 ACTIVE in combo_fires; 89 WATCH)`
**Run Date:** `2026-06-15`

**Validated horizon:** 3M (63d) | **Benchmark:** +2.5%

| Test ID | Parameter | Value | Legs req | n | Hit rate | Avg win | Avg loss | PW expected | Excess |
|---------|-----------|-------|----------|---|----------|---------|----------|-------------|--------|
| CB_VIX_20 | vix_min | 20 | 3 | 0 | n/a | n/a | n/a | n/a | n/a |
| CB_VIX_25 | vix_min | 25 | 3 | 0 | n/a | n/a | n/a | n/a | n/a |
| CB_VIX_30 | vix_min | 30 | 3 | 0 | n/a | n/a | n/a | n/a | n/a |
| CB_HY_350 | hy_bps_min | 350 | 3 | 0 | n/a | n/a | n/a | n/a | n/a |
| CB_HY_400 | hy_bps_min | 400 | 3 | 0 | n/a | n/a | n/a | n/a | n/a |
| CB_HY_450 | hy_bps_min | 450 | 3 | 0 | n/a | n/a | n/a | n/a | n/a |
| CB_CFTC_10 | cftc_max_pctile | 10 | 3 | 0 | n/a | n/a | n/a | n/a | n/a |
| CB_CFTC_15 | cftc_max_pctile | 15 | 3 | 0 | n/a | n/a | n/a | n/a | n/a |
| CB_CFTC_20 | cftc_max_pctile | 20 | 3 | 0 | n/a | n/a | n/a | n/a | n/a |
| CB_2of3_legs | legs_required | 2 | 2 | 12 | 75.0% | +10.41% | -0.99% | +7.56% | +5.06pp |

---
## 23. Combo F (Recovery): SPX threshold sweep detail

**Combo:** `F`
**Validated Horizon:** `spx_6m`
**Direction:** `bullish`
**Current Gates:** `{'spx_50wma_reclaim_weekly_pct': 3.0, 'cftc_max_pctile': 50, 'active_weeks': 26}`
**Run Date:** `2026-06-15`

**Validated horizon:** 6M (126d) | **Benchmark:** +5.0%

| Test ID | Parameter | Value | Legs req | n | Hit rate | Avg win | Avg loss | PW expected | Excess |
|---------|-----------|-------|----------|---|----------|---------|----------|-------------|--------|
| CF_SPX_1pct | spx_50wma_reclaim_weekly_pct | 1.0 | ? | 46 | 80.0% | +10.53% | -5.05% | +7.41% | +2.41pp |
| CF_SPX_2pct | spx_50wma_reclaim_weekly_pct | 2.0 | ? | 46 | 82.2% | +10.11% | -5.87% | +7.27% | +2.27pp |
| CF_SPX_3pct | spx_50wma_reclaim_weekly_pct | 3.0 | ? | 43 | 85.7% | +10.22% | -4.25% | +8.15% | +3.15pp |
| CF_SPX_5pct | spx_50wma_reclaim_weekly_pct | 5.0 | ? | 42 | 85.4% | +10.53% | -3.35% | +8.50% | +3.50pp |

---
## 24. Combo E (Valuation Extreme): gate sweep detail

**Combo:** `E`
**Validated Horizon:** `spx_12m`
**Direction:** `bearish`
**Current Gates:** `{'min_of_three': 2, 'cape_min': 28, 'nfci_easy_max': -0.3, 'cftc_min_pctile': 80}`
**Run Date:** `2026-06-15`

**Validated horizon:** 12M (252d) | **Benchmark:** +10.0%

| Test ID | Parameter | Value | Legs req | n | Hit rate | Avg win | Avg loss | PW expected | Excess |
|---------|-----------|-------|----------|---|----------|---------|----------|-------------|--------|
| CE_CAPE_25 | cape_min | 25 | ? | 18 | 5.6% | -1.07% | +18.61% | +17.51% | +7.51pp |
| CE_CAPE_28 | cape_min | 28 | ? | 22 | 9.1% | -2.37% | +17.79% | +15.96% | +5.96pp |
| CE_CAPE_30 | cape_min | 30 | ? | 31 | 9.7% | -4.22% | +16.77% | +14.74% | +4.74pp |
| CE_CAPE_32 | cape_min | 32 | ? | 30 | 6.7% | -2.37% | +15.53% | +14.33% | +4.33pp |
| CE_NFCI_-0.2 | nfci_easy_max | -0.2 | ? | 23 | 8.7% | -2.37% | +16.99% | +15.31% | +5.31pp |
| CE_NFCI_-0.3 | nfci_easy_max | -0.3 | ? | 22 | 9.1% | -2.37% | +17.79% | +15.96% | +5.96pp |
| CE_NFCI_-0.4 | nfci_easy_max | -0.4 | ? | 21 | 9.5% | -1.98% | +17.35% | +15.51% | +5.51pp |
| CE_CFTC_75 | cftc_min_pctile | 75 | ? | 27 | 11.1% | -2.05% | +17.22% | +15.07% | +5.07pp |
| CE_CFTC_80 | cftc_min_pctile | 80 | ? | 22 | 9.1% | -2.37% | +17.79% | +15.96% | +5.96pp |
| CE_CFTC_85 | cftc_min_pctile | 85 | ? | 19 | 10.5% | -1.51% | +16.69% | +14.78% | +4.78pp |

---
## 25. Combo D (FOMO Top): gate sweep detail

**Combo:** `D`
**Validated Horizon:** `spx_5d`
**Direction:** `bearish`
**Current Gates:** `{'vxts_min': 1.1, 'cftc_min_pctile': 85, 'vix_max': 18}`
**Run Date:** `2026-06-15`

**Validated horizon:** 5D (5d) | **Benchmark:** +0.5%

| Test ID | Parameter | Value | Legs req | n | Hit rate | Avg win | Avg loss | PW expected | Excess |
|---------|-----------|-------|----------|---|----------|---------|----------|-------------|--------|
| CD_VXTS_1.05 | vxts_min | 1.05 | 3 | 32 | 37.5% | -1.25% | +1.18% | +0.27% | -0.23pp |
| CD_VXTS_1.1 | vxts_min | 1.1 | 3 | 31 | 41.9% | -1.18% | +1.23% | +0.22% | -0.28pp |
| CD_VXTS_1.15 | vxts_min | 1.15 | 3 | 25 | 40.0% | -1.39% | +0.96% | +0.02% | -0.48pp |
| CD_CFTC_80 | cftc_min_pctile | 80 | 3 | 33 | 39.4% | -0.95% | +1.26% | +0.39% | -0.11pp |
| CD_CFTC_85 | cftc_min_pctile | 85 | 3 | 31 | 41.9% | -1.18% | +1.23% | +0.22% | -0.28pp |
| CD_CFTC_90 | cftc_min_pctile | 90 | 3 | 25 | 40.0% | -1.43% | +1.23% | +0.17% | -0.33pp |
| CD_VIX_15 | vix_max | 15 | 3 | 24 | 45.8% | -1.32% | +1.17% | +0.03% | -0.47pp |
| CD_VIX_18 | vix_max | 18 | 3 | 31 | 41.9% | -1.18% | +1.23% | +0.22% | -0.28pp |
| CD_VIX_20 | vix_max | 20 | 3 | 38 | 42.1% | -1.56% | +1.40% | +0.16% | -0.34pp |
| CD_2of3_legs | legs_required | 2 | 2 | 87 | 33.7% | -1.76% | +1.30% | +0.27% | -0.23pp |

---
