# All Combos Threshold Study — Analysis

Generated: 2026-07-03 11:40 UTC

Method: first-crossing episodes, 5-day cooldown, aligned `daily_readings` panel (Friday-only for Combo F).
Hit rate = % episodes where SPX moved in combo direction (bullish: up, bearish: down).

## 1. CONFIG vs product spec

| Combo | Spec hit % | Spec horizon | CONFIG n | CONFIG primary hit % | Delta vs spec |
|-------|------------|--------------|----------|----------------------|---------------|
| A Liquidity | 78.0% | 6M | 77 | 78.95% | +0.9pp |
| B Capitulation | 87.5% | 3M | 9 | 77.78% | -9.7pp |
| C Stagflation | 83.0% | 6M | 1 | None% | n/a |
| D FOMO Top | 78.0% | 1W | 31 | 41.94% | -36.1pp |
| E Valuation Extreme | 73.0% | 12M | 22 | 9.09% | -63.9pp |
| F Recovery | 78.0% | 6M | 43 | 85.71% | +7.7pp |
| G Hidden Stress | 75.0% | 3W | 0 | None% | n/a |

## 2. Top thresholds by horizon (from sweep data)

Ranked by primary horizon hit rate. Values are measured from first-crossing episodes (5-day cooldown).
Combo C/G include extended sweeps where base grid had n<3.

### Combo A — Liquidity (top 5 by 6M, n≥3 or all available)

| Rank | n | Gate | 1M | 2M | 3M | 6M | Mean | Primary |
|---|---|---|---|---|---|---|---|---|
| 1 | 30 | ≥3 of 4 rare: NFCI/CNH pctile>=85 or <=15; HY>=450bps or pctile>=85; WALCL >=0.8% | 80% | 80% | 83.33% | 86.67% | 82.50% | **86.67%** |
| 2 | 37 | ≥3 of 4 rare: NFCI/CNH pctile>=85 or <=15; HY>=400bps or pctile>=85; WALCL >=0.8% | 83.78% | 83.78% | 86.49% | 86.49% | 85.14% | **86.49%** |
| 3 | 50 | ≥3 of 4 rare: NFCI/CNH pctile>=85 or <=15; HY>=350bps or pctile>=85; WALCL >=0.8% | 82% | 80% | 84% | 86% | 83% | **86%** |
| 4 | 77 | ≥2 of 4 rare: NFCI/CNH pctile>=85 or <=15; HY>=450bps or pctile>=85; WALCL >=0.8% | 75.32% | 75.32% | 80.52% | 84.21% | 78.84% | **84.21%** |
| 5 | 44 | ≥3 of 4 rare: NFCI/CNH pctile>=75 or <=25; HY>=450bps or pctile>=75; WALCL >=0.8% | 81.82% | 77.27% | 79.55% | 84.09% | 80.68% | **84.09%** |

### Combo B — Capitulation (top 5 by 3M, n≥3 or all available)

| Rank | n | Gate | 2W | 1M | 6W | 2M | 3M | Mean | Primary |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 8 | VIX>=28 & VIX pctile>=80; HY>=400bps OR HY pctile>=80; CFTC<=15; 3-of-3 | 62.50% | 75% | 87.50% | 100% | 87.50% | 82.50% | **87.50%** |
| 2 | 8 | VIX>=28 & VIX pctile>=80; HY>=375bps OR HY pctile>=80; CFTC<=15; 3-of-3 | 62.50% | 75% | 87.50% | 100% | 87.50% | 82.50% | **87.50%** |
| 3 | 8 | VIX>=28 & VIX pctile>=80; HY>=400bps OR HY pctile>=80; CFTC<=18; 3-of-3 | 50% | 75% | 87.50% | 100% | 87.50% | 80% | **87.50%** |
| 4 | 8 | VIX>=28 & VIX pctile>=80; HY>=375bps OR HY pctile>=80; CFTC<=18; 3-of-3 | 50% | 75% | 87.50% | 100% | 87.50% | 80% | **87.50%** |
| 5 | 7 | VIX>=28 & VIX pctile>=80; HY>=400bps OR HY pctile>=80; CFTC<=12; 3-of-3 | 57.14% | 71.43% | 85.71% | 100% | 85.71% | 80% | **85.71%** |

### Combo C — Stagflation (top 5 by 6M, n≥3 or all available)

| Rank | n | Gate | 1M | 2M | 3M | 6M | Mean | Primary |
|---|---|---|---|---|---|---|---|---|
| 1 | 5 | WTI 4wk>=5%; CPI surprise>=0.2; WALCL MoM <1.0%; 2-of-3 | 0% | 25% | 0% | 0% | 6.25% | **0%** |
| 2 | 5 | WTI 4wk>=6%; CPI surprise>=0.2; WALCL MoM <1.0%; 2-of-3 | 0% | 25% | 0% | 0% | 6.25% | **0%** |
| 3 | 5 | WTI 4wk>=7%; CPI surprise>=0.2; WALCL MoM <1.0%; 2-of-3 | 0% | 25% | 0% | 0% | 6.25% | **0%** |
| 4 | 6 | WTI 4wk>=8%; CPI surprise>=0.05; WALCL MoM <1.2%; 2-of-3 | 0% | 25% | 0% | 0% | 6.25% | **0%** |
| 5 | 5 | WTI 4wk>=8%; CPI surprise>=0.2; WALCL MoM <1.0%; 2-of-3 | 0% | 25% | 0% | 0% | 6.25% | **0%** |

### Combo D — FOMO Top (top 5 by 1W, n≥3 or all available)

| Rank | n | Gate | 1W | 2W | 3W | 4W | 1M | Mean | Primary |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 78 | VXTS>=1.18; CFTC>=90; VIX<=16; 2-of-3 | 57.69% | 38.46% | 44.87% | 46.15% | 44.87% | 46.41% | **57.69%** |
| 2 | 78 | VXTS>=1.18; CFTC>=92; VIX<=16; 2-of-3 | 57.69% | 38.46% | 46.15% | 46.15% | 44.87% | 46.66% | **57.69%** |
| 3 | 78 | VXTS>=1.18; CFTC>=95; VIX<=16; 2-of-3 | 57.69% | 39.74% | 44.87% | 43.59% | 42.31% | 45.64% | **57.69%** |
| 4 | 81 | VXTS>=1.18; CFTC>=88; VIX<=16; 2-of-3 | 56.79% | 38.27% | 44.44% | 45.68% | 44.44% | 45.92% | **56.79%** |
| 5 | 42 | VXTS>=1.25; CFTC>=95; VIX<=16; 2-of-3 | 54.76% | 38.10% | 30.95% | 38.10% | 35.71% | 39.52% | **54.76%** |

### Combo E — Valuation Extreme (top 5 by 12M, n≥3 or all available)

| Rank | n | Gate | 3M | 6M | 9M | 12M | 15M | 18M | Mean | Primary |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 9 | CAPE>=32; NFCI<=-0.25; CFTC>=92; 3-of-3 | 75% | 75% | 87.50% | 87.50% | 50% | 37.50% | 68.75% | **87.50%** |
| 2 | 9 | CAPE>=32; NFCI<=-0.3; CFTC>=92; 3-of-3 | 75% | 75% | 87.50% | 87.50% | 50% | 37.50% | 68.75% | **87.50%** |
| 3 | 9 | CAPE>=32; NFCI<=-0.2; CFTC>=92; 3-of-3 | 75% | 75% | 87.50% | 87.50% | 50% | 37.50% | 68.75% | **87.50%** |
| 4 | 10 | CAPE>=32; NFCI<=-0.2; CFTC>=85; 3-of-3 | 66.67% | 66.67% | 66.67% | 66.67% | 44.44% | 44.44% | 59.26% | **66.67%** |
| 5 | 10 | CAPE>=32; NFCI<=-0.3; CFTC>=85; 3-of-3 | 66.67% | 66.67% | 66.67% | 66.67% | 44.44% | 44.44% | 59.26% | **66.67%** |

### Combo F — Recovery (top 5 by 6M, n≥3 or all available)

| Rank | n | Gate | 1M | 2M | 3M | 6M | 9M | Mean | Primary |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 43 | SPX above 50WMA AND (reclaim OR close>=4.0% above WMA); CFTC<=60 | 74.42% | 74.42% | 85.71% | 92.86% | 90.48% | 83.58% | **92.86%** |
| 2 | 42 | SPX above 50WMA AND (reclaim OR close>=4.0% above WMA); CFTC<=50 | 71.43% | 76.19% | 87.80% | 90.24% | 92.68% | 83.67% | **90.24%** |
| 3 | 42 | SPX above 50WMA AND (reclaim OR close>=6.0% above WMA); CFTC<=50 | 73.81% | 71.43% | 80.49% | 87.80% | 92.68% | 81.24% | **87.80%** |
| 4 | 41 | SPX above 50WMA AND (reclaim OR close>=3.0% above WMA); CFTC<=40 | 73.17% | 73.17% | 85% | 87.50% | 95% | 82.77% | **87.50%** |
| 5 | 40 | SPX above 50WMA AND (reclaim OR close>=4.0% above WMA); CFTC<=40 | 70% | 72.50% | 84.62% | 87.18% | 94.87% | 81.83% | **87.18%** |

### Combo G — Hidden Stress (top 5 by 3W, n≥3 or all available)

| Rank | n | Gate | 1W | 2W | 3W | 4W | 6W | Mean | Primary |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | VXTS<1.12; VIX<=20; HY 4wk widen>=30bps; 3-of-3 | 66.67% | 100% | 100% | 66.67% | 33.33% | 73.33% | **100%** |
| 2 | 3 | VXTS<1.2; VIX<=20; HY 4wk widen>=30bps; 3-of-3 | 66.67% | 100% | 100% | 66.67% | 33.33% | 73.33% | **100%** |
| 3 | 3 | VXTS<1.1; VIX<=20; HY 4wk widen>=30bps; 3-of-3 | 66.67% | 100% | 100% | 66.67% | 33.33% | 73.33% | **100%** |
| 4 | 3 | VXTS<1.15; VIX<=20; HY 4wk widen>=30bps; 3-of-3 | 66.67% | 100% | 100% | 66.67% | 33.33% | 73.33% | **100%** |
| 5 | 4 | VXTS<1.08; VIX<=20; HY 4wk widen>=15bps; 3-of-3 | 50% | 50% | 75% | 75% | 50% | 60% | **75%** |

## 3. Recommended full gate per combo (best primary hit, prefer n≥5)

| Combo | n | Primary hit | Spec | Gate | Key thresholds |
|---|---:|---:|---:|---|---|
| **A** | 30 | 86.67% @ 6M | 78.0% | ≥3 of 4 rare: NFCI/CNH pctile>=85 or <=15; HY>=450bps or pctile>=85; WALCL >=0.8% | min_of_four=3, rare_pctile_high=85, rare_pctile_low=15, hy_bps_rare=450, walcl_mom_rare_pct=0.80 |
| **B** | 8 | 87.50% @ 3M | 87.5% | VIX>=28 & VIX pctile>=80; HY>=400bps OR HY pctile>=80; CFTC<=15; 3-of-3 | vix_min=28, hy_bps_min=400, cftc_max_pctile=15, legs_required=3 |
| **C** | 5 | 0% @ 6M | 83.0% | WTI 4wk>=5%; CPI surprise>=0.2; WALCL MoM <1.0%; 2-of-3 | wti_4wk_min_pct=5, cpi_surprise_min=0.20, walcl_flat_max_pct=1, legs_required=2 |
| **D** | 78 | 57.69% @ 1W | 78.0% | VXTS>=1.18; CFTC>=90; VIX<=16; 2-of-3 | vxts_min=1.18, cftc_min_pctile=90, vix_max=16, legs_required=2 |
| **E** | 9 | 87.50% @ 12M | 73.0% | CAPE>=32; NFCI<=-0.2; CFTC>=92; 3-of-3 | cape_min=32, nfci_easy_max=-0.20, cftc_min_pctile=92, legs_required=3 |
| **F** | 43 | 92.86% @ 6M | 78.0% | SPX above 50WMA AND (reclaim OR close>=4.0% above WMA); CFTC<=60 | spx_50wma_reclaim_pct=4, cftc_max_pctile=60 |
| **G** | 3 | 100% @ 3W | 75.0% | VXTS<1.1; VIX<=20; HY 4wk widen>=30bps; 3-of-3 | vxts_max=1.10, vix_max=20, hy_widen_4wk_bps_min=30 |

## 4. Master variable threshold table (best value per variable, measured)

| Combo | Variable | Best threshold | n | Primary horizon | Primary hit % | Mean hit all H | Experiment |
|---|---|---|---:|---|---:|---:|---|
| A | hy_bps_rare | ≥ 350 | 50 | 6M | 86 | 83 | A_min3_p85_15_hy350_w0.8 |
| A | hy_bps_rare | ≥ 400 | 37 | 6M | 86.49 | 85.14 | A_min3_p85_15_hy400_w0.8 |
| A | hy_bps_rare | ≥ 450 | 30 | 6M | 86.67 | 82.50 | A_min3_p85_15_hy450_w0.8 |
| A | min_of_four | ≥ 2 | 77 | 6M | 84.21 | 78.84 | A_min2_p85_15_hy450_w0.8 |
| A | min_of_four | ≥ 3 | 30 | 6M | 86.67 | 82.50 | A_min3_p85_15_hy450_w0.8 |
| A | rare_pctile_high | ≥ 75 | 44 | 6M | 84.09 | 80.68 | A_min3_p75_25_hy450_w0.8 |
| A | rare_pctile_high | ≥ 80 | 50 | 6M | 84 | 80.50 | A_min3_p80_20_hy400_w0.8 |
| A | rare_pctile_high | ≥ 85 | 30 | 6M | 86.67 | 82.50 | A_min3_p85_15_hy450_w0.8 |
| A | rare_pctile_low | ≤ 15 | 30 | 6M | 86.67 | 82.50 | A_min3_p85_15_hy450_w0.8 |
| A | rare_pctile_low | ≤ 20 | 50 | 6M | 84 | 80.50 | A_min3_p80_20_hy400_w0.8 |
| A | rare_pctile_low | ≤ 25 | 44 | 6M | 84.09 | 80.68 | A_min3_p75_25_hy450_w0.8 |
| A | walcl_mom_rare_pct | ≥ abs 0.60 | 79 | 6M | 74.67 | 70.47 | A_min2_p80_20_hy400_w0.6 |
| A | walcl_mom_rare_pct | ≥ abs 0.80 | 30 | 6M | 86.67 | 82.50 | A_min3_p85_15_hy450_w0.8 |
| A | walcl_mom_rare_pct | ≥ abs 1 | 72 | 6M | 80.28 | 74.58 | A_min2_p80_20_hy400_w1.0 |
| B | cftc_max_pctile | ≤ 10 | 7 | 3M | 71.43 | 65.71 | B_vix25_hy400_cftc10_l3 |
| B | cftc_max_pctile | ≤ 12 | 7 | 3M | 85.71 | 80 | B_vix28_hy375_cftc12_l3 |
| B | cftc_max_pctile | ≤ 15 | 8 | 3M | 87.50 | 82.50 | B_vix28_hy400_cftc15_l3 |
| B | cftc_max_pctile | ≤ 18 | 8 | 3M | 87.50 | 80 | B_vix28_hy375_cftc18_l3 |
| B | cftc_max_pctile | ≤ 20 | 10 | 3M | 70 | 70 | B_vix25_hy400_cftc20_l3 |
| B | hy_bps_min | ≥ 350 | 9 | 3M | 77.78 | 73.34 | B_vix25_hy350_cftc15_l3 |
| B | hy_bps_min | ≥ 375 | 8 | 3M | 87.50 | 80 | B_vix28_hy375_cftc18_l3 |
| B | hy_bps_min | ≥ 400 | 8 | 3M | 87.50 | 82.50 | B_vix28_hy400_cftc15_l3 |
| B | hy_bps_min | ≥ 425 | 7 | 3M | 85.71 | 80 | B_vix28_hy425_cftc18_l3 |
| B | hy_bps_min | ≥ 450 | 7 | 3M | 85.71 | 82.86 | B_vix25_hy450_cftc15_l3 |
| B | legs_required | = 2 | 38 | 3M | 76.32 | 67.90 | B_vix25_hy375_cftc12_l2 |
| B | legs_required | = 3 | 8 | 3M | 87.50 | 82.50 | B_vix28_hy400_cftc15_l3 |
| B | vix_min | ≥ 20 | 10 | 3M | 70 | 74 | B_vix20_hy400_cftc15_l3 |
| B | vix_min | ≥ 22 | 36 | 3M | 75 | 67.78 | B_vix22_hy375_cftc12_l2 |
| B | vix_min | ≥ 25 | 7 | 3M | 85.71 | 82.86 | B_vix25_hy450_cftc15_l3 |
| B | vix_min | ≥ 28 | 8 | 3M | 87.50 | 82.50 | B_vix28_hy400_cftc15_l3 |
| B | vix_min | ≥ 30 | 7 | 3M | 85.71 | 82.86 | B_vix30_hy400_cftc15_l3 |
| C | cpi_surprise_min | ≥ 0 | 4 | 6M | 0 | 6.25 | C_ext_w8_cpi0.0_wcl1.2_l2 |
| C | cpi_surprise_min | ≥ 0.05 | 6 | 6M | 0 | 6.25 | C_ext_w8_cpi0.05_wcl1.2_l2 |
| C | cpi_surprise_min | ≥ 0.10 | 5 | 6M | 0 | 6.25 | C_ext_w8_cpi0.1_wcl1.2_l2 |
| C | cpi_surprise_min | ≥ 0.15 | 5 | 6M | 0 | 6.25 | C_ext_w8_cpi0.15_wcl1.2_l2 |
| C | cpi_surprise_min | ≥ 0.20 | 5 | 6M | 0 | 6.25 | C_ext_w5_cpi0.2_wcl1.0_l2 |
| C | cpi_surprise_min | ≥ 0.25 | 4 | 6M | 0 | 8.33 | C_ext_w8_cpi0.25_wcl1.2_l2 |
| C | legs_required | = 2 | 5 | 6M | 0 | 6.25 | C_ext_w5_cpi0.2_wcl1.0_l2 |
| C | legs_required | = 3 | 3 | 6M | 0 | 8.33 | C_ext_w5_cpi0.2_wcl1.0_l3 |
| C | walcl_flat_max_pct | < abs 0.80 | 5 | 6M | 0 | 6.25 | C_ext_w8_cpi0.15_wcl0.8_l2 |
| C | walcl_flat_max_pct | < abs 1 | 5 | 6M | 0 | 6.25 | C_ext_w5_cpi0.2_wcl1.0_l2 |
| C | walcl_flat_max_pct | < abs 1.20 | 4 | 6M | 0 | 6.25 | C_ext_w8_cpi0.0_wcl1.2_l2 |
| C | walcl_flat_max_pct | < abs 1.50 | 3 | 6M | 0 | 0 | C_ext_w8_cpi0.15_wcl1.5_l2 |
| C | walcl_flat_max_pct | < abs 2 | 3 | 6M | 0 | 0 | C_ext_w8_cpi0.15_wcl2.0_l2 |
| C | walcl_flat_max_pct | < abs 2.50 | 3 | 6M | 0 | 0 | C_ext_w8_cpi0.15_wcl2.5_l2 |
| C | wti_4wk_min_pct | ≥ 5 | 5 | 6M | 0 | 6.25 | C_ext_w5_cpi0.2_wcl1.0_l2 |
| C | wti_4wk_min_pct | ≥ 6 | 5 | 6M | 0 | 6.25 | C_ext_w6_cpi0.2_wcl1.0_l2 |
| C | wti_4wk_min_pct | ≥ 7 | 5 | 6M | 0 | 6.25 | C_ext_w7_cpi0.2_wcl1.0_l2 |
| C | wti_4wk_min_pct | ≥ 8 | 5 | 6M | 0 | 6.25 | C_ext_w8_cpi0.2_wcl1.0_l2 |
| C | wti_4wk_min_pct | ≥ 10 | 4 | 6M | 0 | 8.33 | C_ext_w10_cpi0.2_wcl1.0_l2 |
| C | wti_4wk_min_pct | ≥ 12 | 4 | 6M | 0 | 8.33 | C_ext_w12_cpi0.2_wcl1.0_l2 |
| C | wti_4wk_min_pct | ≥ 15 | 4 | 6M | 0 | 8.33 | C_ext_w15_cpi0.2_wcl1.0_l2 |
| D | cftc_min_pctile | ≥ 80 | 33 | 1W | 39.39 | 30.91 | D_v1.10_c80_x18_l3 |
| D | cftc_min_pctile | ≥ 85 | 24 | 1W | 50 | 39.17 | D_v1.10_c85_x16_l3 |
| D | cftc_min_pctile | ≥ 88 | 81 | 1W | 56.79 | 45.92 | D_v1.18_c88_x16_l2 |
| D | cftc_min_pctile | ≥ 90 | 78 | 1W | 57.69 | 46.41 | D_v1.18_c90_x16_l2 |
| D | cftc_min_pctile | ≥ 92 | 78 | 1W | 57.69 | 46.66 | D_v1.18_c92_x16_l2 |
| D | cftc_min_pctile | ≥ 95 | 78 | 1W | 57.69 | 45.64 | D_v1.18_c95_x16_l2 |
| D | legs_required | = 2 | 78 | 1W | 57.69 | 46.66 | D_v1.18_c92_x16_l2 |
| D | legs_required | = 3 | 24 | 1W | 50 | 39.17 | D_v1.10_c85_x16_l3 |
| D | vix_max | ≤ 14 | 57 | 1W | 54.39 | 45.61 | D_v1.18_c95_x14_l2 |
| D | vix_max | ≤ 16 | 78 | 1W | 57.69 | 46.66 | D_v1.18_c92_x16_l2 |
| D | vix_max | ≤ 18 | 90 | 1W | 46.67 | 42.14 | D_v1.18_c88_x18_l2 |
| D | vix_max | ≤ 20 | 38 | 1W | 42.11 | 35.26 | D_v1.10_c85_x20_l3 |
| D | vxts_min | ≥ 1.10 | 24 | 1W | 50 | 39.17 | D_v1.10_c85_x16_l3 |
| D | vxts_min | ≥ 1.15 | 84 | 1W | 51.19 | 41.19 | D_v1.15_c90_x16_l2 |
| D | vxts_min | ≥ 1.18 | 78 | 1W | 57.69 | 46.41 | D_v1.18_c90_x16_l2 |
| D | vxts_min | ≥ 1.20 | 24 | 1W | 41.67 | 35 | D_v1.20_c85_x18_l3 |
| D | vxts_min | ≥ 1.22 | 45 | 1W | 51.11 | 39.11 | D_v1.22_c95_x14_l2 |
| D | vxts_min | ≥ 1.25 | 42 | 1W | 54.76 | 39.52 | D_v1.25_c95_x16_l2 |
| E | cape_min | ≥ 26 | 21 | 12M | 4.76 | 6.35 | E_cape26_nfci-0.30_cftc80_l2 |
| E | cape_min | ≥ 28 | 20 | 12M | 36.84 | 33.34 | E_cape28_nfci-0.25_cftc92_l3 |
| E | cape_min | ≥ 30 | 11 | 12M | 50 | 36.67 | E_cape30_nfci-0.25_cftc80_l3 |
| E | cape_min | ≥ 32 | 9 | 12M | 87.50 | 68.75 | E_cape32_nfci-0.25_cftc92_l3 |
| E | cape_min | ≥ 35 | 33 | 12M | 12.12 | 10.62 | E_cape35_nfci-0.30_cftc80_l2 |
| E | cftc_min_pctile | ≥ 75 | 27 | 12M | 11.11 | 8.64 | E_cape28_nfci-0.30_cftc75_l2 |
| E | cftc_min_pctile | ≥ 80 | 9 | 12M | 62.50 | 47.92 | E_cape32_nfci-0.20_cftc80_l3 |
| E | cftc_min_pctile | ≥ 85 | 10 | 12M | 66.67 | 59.26 | E_cape32_nfci-0.30_cftc85_l3 |
| E | cftc_min_pctile | ≥ 88 | 18 | 12M | 11.11 | 8.34 | E_cape28_nfci-0.30_cftc88_l2 |
| E | cftc_min_pctile | ≥ 92 | 9 | 12M | 87.50 | 68.75 | E_cape32_nfci-0.30_cftc92_l3 |
| E | cftc_min_pctile | ≥ 95 | 15 | 12M | 6.67 | 3.33 | E_cape28_nfci-0.30_cftc95_l2 |
| E | legs_required | = 2 | 33 | 12M | 12.12 | 10.62 | E_cape35_nfci-0.30_cftc80_l2 |
| E | legs_required | = 3 | 9 | 12M | 87.50 | 68.75 | E_cape32_nfci-0.20_cftc92_l3 |
| E | nfci_easy_max | ≤ -0.35 | 19 | 12M | 10.53 | 8.77 | E_cape28_nfci-0.35_cftc80_l2 |
| E | nfci_easy_max | ≤ -0.30 | 9 | 12M | 87.50 | 68.75 | E_cape32_nfci-0.30_cftc92_l3 |
| E | nfci_easy_max | ≤ -0.25 | 9 | 12M | 87.50 | 68.75 | E_cape32_nfci-0.25_cftc92_l3 |
| E | nfci_easy_max | ≤ -0.20 | 9 | 12M | 87.50 | 68.75 | E_cape32_nfci-0.20_cftc92_l3 |
| E | nfci_easy_max | ≤ -0.15 | 22 | 12M | 9.09 | 7.58 | E_cape28_nfci-0.15_cftc80_l2 |
| F | cftc_max_pctile | ≤ 40 | 41 | 6M | 87.50 | 82.77 | F_spx3.0_cftc40 |
| F | cftc_max_pctile | ≤ 45 | 43 | 6M | 80.95 | 78.38 | F_spx3.0_cftc45 |
| F | cftc_max_pctile | ≤ 50 | 42 | 6M | 90.24 | 83.67 | F_spx4.0_cftc50 |
| F | cftc_max_pctile | ≤ 55 | 46 | 6M | 86.67 | 74.55 | F_spx3.0_cftc55 |
| F | cftc_max_pctile | ≤ 60 | 43 | 6M | 92.86 | 83.58 | F_spx4.0_cftc60 |
| F | spx_50wma_reclaim_pct | ≥ 1 | 46 | 6M | 80 | 75.85 | F_spx1.0_cftc50 |
| F | spx_50wma_reclaim_pct | ≥ 2 | 44 | 6M | 83.72 | 79.34 | F_spx2.0_cftc40 |
| F | spx_50wma_reclaim_pct | ≥ 3 | 41 | 6M | 87.50 | 82.77 | F_spx3.0_cftc40 |
| F | spx_50wma_reclaim_pct | ≥ 4 | 43 | 6M | 92.86 | 83.58 | F_spx4.0_cftc60 |
| F | spx_50wma_reclaim_pct | ≥ 5 | 44 | 6M | 86.05 | 82.56 | F_spx5.0_cftc60 |
| F | spx_50wma_reclaim_pct | ≥ 6 | 42 | 6M | 87.80 | 81.24 | F_spx6.0_cftc50 |
| G | hy_widen_4wk_bps_min | ≥ 10 | 12 | 3W | 45.45 | 40 | G_ext_vxts1.1_vix22_hy10 |
| G | hy_widen_4wk_bps_min | ≥ 15 | 4 | 3W | 75 | 60 | G_ext_vxts1.08_vix20_hy15 |
| G | hy_widen_4wk_bps_min | ≥ 20 | 3 | 3W | 66.67 | 46.67 | G_ext_vxts1.08_vix20_hy20 |
| G | hy_widen_4wk_bps_min | ≥ 25 | 3 | 3W | 66.67 | 46.67 | G_ext_vxts1.08_vix20_hy25 |
| G | hy_widen_4wk_bps_min | ≥ 30 | 3 | 3W | 100 | 73.33 | G_ext_vxts1.1_vix20_hy30 |
| G | hy_widen_4wk_bps_min | ≥ 35 | 3 | 3W | 66.67 | 40 | G_ext_vxts1.1_vix22_hy35 |
| G | hy_widen_4wk_bps_min | ≥ 40 | 3 | 3W | 66.67 | 60 | G_vxts1.05_vix22_hy40 |
| G | hy_widen_4wk_bps_min | ≥ 50 | 3 | 3W | 66.67 | 66.67 | G_ext_vxts1.1_vix22_hy50 |
| G | vix_max | ≤ 18 | 1 | 3W | 100 | 40 | G_ext_vxts1.1_vix18_hy30 |
| G | vix_max | ≤ 20 | 3 | 3W | 100 | 73.33 | G_ext_vxts1.1_vix20_hy30 |
| G | vix_max | ≤ 22 | 3 | 3W | 66.67 | 60 | G_vxts1.05_vix22_hy40 |
| G | vix_max | ≤ 24 | 8 | 3W | 50 | 37.50 | G_ext_vxts1.1_vix24_hy30 |
| G | vix_max | ≤ 25 | 8 | 3W | 50 | 37.50 | G_ext_vxts1.1_vix25_hy30 |
| G | vix_max | ≤ 28 | 9 | 3W | 55.56 | 40 | G_ext_vxts1.1_vix28_hy30 |
| G | vxts_max | < 1.05 | 3 | 3W | 66.67 | 60 | G_ext_vxts1.05_vix22_hy35 |
| G | vxts_max | < 1.08 | 4 | 3W | 75 | 60 | G_ext_vxts1.08_vix20_hy15 |
| G | vxts_max | < 1.10 | 3 | 3W | 100 | 73.33 | G_ext_vxts1.1_vix20_hy30 |
| G | vxts_max | < 1.12 | 3 | 3W | 100 | 73.33 | G_ext_vxts1.12_vix20_hy30 |
| G | vxts_max | < 1.15 | 3 | 3W | 100 | 73.33 | G_ext_vxts1.15_vix20_hy30 |
| G | vxts_max | < 1.20 | 3 | 3W | 100 | 73.33 | G_ext_vxts1.2_vix20_hy30 |

## 5. Best threshold value per variable (detail by combo)

### Combo A — Liquidity

| Variable | Best value | n | Primary hit | Mean hit all horizons | Experiment |
|---|---|---:|---:|---:|---|
| hy_bps_rare | 450 | 30 | 86.67% | 82.50% | A_min3_p85_15_hy450_w0.8 |
| min_of_four | 3 | 30 | 86.67% | 82.50% | A_min3_p85_15_hy450_w0.8 |
| rare_pctile_high | 85 | 30 | 86.67% | 82.50% | A_min3_p85_15_hy450_w0.8 |
| rare_pctile_low | 15 | 30 | 86.67% | 82.50% | A_min3_p85_15_hy450_w0.8 |
| walcl_mom_rare_pct | 0.80 | 30 | 86.67% | 82.50% | A_min3_p85_15_hy450_w0.8 |

### Combo B — Capitulation

| Variable | Best value | n | Primary hit | Mean hit all horizons | Experiment |
|---|---|---:|---:|---:|---|
| cftc_max_pctile | 15 | 8 | 87.50% | 82.50% | B_vix28_hy400_cftc15_l3 |
| hy_bps_min | 375 | 8 | 87.50% | 80% | B_vix28_hy375_cftc18_l3 |
| legs_required | 3 | 8 | 87.50% | 82.50% | B_vix28_hy400_cftc15_l3 |
| vix_min | 28 | 8 | 87.50% | 82.50% | B_vix28_hy400_cftc15_l3 |

### Combo C — Stagflation

| Variable | Best value | n | Primary hit | Mean hit all horizons | Experiment |
|---|---|---:|---:|---:|---|
| cpi_surprise_min | 0 | 4 | 0% | 6.25% | C_ext_w8_cpi0.0_wcl1.2_l2 |
| legs_required | 2 | 5 | 0% | 6.25% | C_ext_w5_cpi0.2_wcl1.0_l2 |
| walcl_flat_max_pct | 0.80 | 5 | 0% | 6.25% | C_ext_w8_cpi0.15_wcl0.8_l2 |
| wti_4wk_min_pct | 5 | 5 | 0% | 6.25% | C_ext_w5_cpi0.2_wcl1.0_l2 |

### Combo D — FOMO Top

| Variable | Best value | n | Primary hit | Mean hit all horizons | Experiment |
|---|---|---:|---:|---:|---|
| cftc_min_pctile | 92 | 78 | 57.69% | 46.66% | D_v1.18_c92_x16_l2 |
| legs_required | 2 | 78 | 57.69% | 46.66% | D_v1.18_c92_x16_l2 |
| vix_max | 16 | 78 | 57.69% | 46.66% | D_v1.18_c92_x16_l2 |
| vxts_min | 1.18 | 78 | 57.69% | 46.41% | D_v1.18_c90_x16_l2 |

### Combo E — Valuation Extreme

| Variable | Best value | n | Primary hit | Mean hit all horizons | Experiment |
|---|---|---:|---:|---:|---|
| cape_min | 32 | 9 | 87.50% | 68.75% | E_cape32_nfci-0.25_cftc92_l3 |
| cftc_min_pctile | 92 | 9 | 87.50% | 68.75% | E_cape32_nfci-0.30_cftc92_l3 |
| legs_required | 3 | 9 | 87.50% | 68.75% | E_cape32_nfci-0.20_cftc92_l3 |
| nfci_easy_max | -0.30 | 9 | 87.50% | 68.75% | E_cape32_nfci-0.30_cftc92_l3 |

### Combo F — Recovery

| Variable | Best value | n | Primary hit | Mean hit all horizons | Experiment |
|---|---|---:|---:|---:|---|
| cftc_max_pctile | 60 | 43 | 92.86% | 83.58% | F_spx4.0_cftc60 |
| spx_50wma_reclaim_pct | 4 | 43 | 92.86% | 83.58% | F_spx4.0_cftc60 |

### Combo G — Hidden Stress

| Variable | Best value | n | Primary hit | Mean hit all horizons | Experiment |
|---|---|---:|---:|---:|---|
| hy_widen_4wk_bps_min | 30 | 3 | 100% | 73.33% | G_ext_vxts1.1_vix20_hy30 |
| vix_max | 18 | 1 | 100% | 40% | G_ext_vxts1.1_vix18_hy30 |
| vxts_max | 1.12 | 3 | 100% | 73.33% | G_ext_vxts1.12_vix20_hy30 |

## 6. Interpretation notes

- **A:** Proxy rare legs via pctile bands; production uses variable-engine RARE/EXTREME tiers.
- **B:** VIX≥28 on strict 3-of-3 matches spec 87.5% @3M (n=8) in replay.
- **C:** Extended sweep (79 experiments, max n=6): **no configuration reached spec 83% @6M** on episode replay; best 6M bear hit = 0%.
- **G:** Extended sweep (107 experiments) required — CONFIG VXTS<1.0 yields n=0. Best n≥5: 66.7% @3W (spec 75%); n=3 configs show 100% @3W but not robust.
- **D/E:** CONFIG far below spec; tightened gates in section 3.
- **F:** CONFIG and sweep agree — strong bullish 6M.

CSV exports: `all_combos_recommended_full_config.csv`, `all_combos_best_threshold_per_variable.csv`, `combo_*_variable_best_by_value.csv`, `combo_C_extended_sweep_summary.csv`, `combo_G_extended_sweep_summary.csv`.
