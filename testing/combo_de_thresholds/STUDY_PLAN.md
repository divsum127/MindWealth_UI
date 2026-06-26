# Combo D & E Threshold Study — Plan

**Goal:** Tighten Combo D (FOMO Top) and Combo E (Valuation Extreme) gates so instances are rare (~20–40 total, comparable to B≈8 and F≈16) while maximizing **bearish** hit rate at each combo’s natural horizon.

**Output directory:** `testing/combo_de_thresholds/output_files/`

---

## 1. Problem statement

| Combo | Current backfill | Bear hit (loose gates) | Issue |
|-------|------------------|------------------------|-------|
| **D** | 435 Fridays (2010–2026) | 1W 39.6% … 2M 31.7% | Fires ~every 2–3 weeks; mostly bullish SPX drift |
| **E** | 484 Fridays | 1M 30.4% … 12M 20.5% | Same — structural flag, not a timer |

Plan target: **80%+ bear hit** at D tactical (1–4W) and E structural (6–12M) with **20–40 episode-style events**.

---

## 2. Methodology

### 2.1 Event definition (episode-style, not weekly persistence)

Production `combo_fires` logs **every Friday** while partial legs hold → inflated n.

This study uses **first Friday crossing** into a gate state (5-day cooldown), on **Fridays only**, aligned with B/F rarity counting.

### 2.2 Variables & gates

| Combo | Variables | Config today |
|-------|-----------|--------------|
| **D** | VXTS ≥ min, CFTC pctile ≥ min, VIX ≤ max | 1.10 / 85 / 18, 3 legs for ACTIVE |
| **E** | CAPE ≥ min, NFCI ≤ max (easy), CFTC pctile ≥ min | 28 / −0.3 / 80, 2-of-3 |

Sweeps vary one or all parameters; factorial grid on tightened ranges.

### 2.3 Horizons measured

| Combo | Horizons (NYSE trading days) |
|-------|------------------------------|
| **D** | 1W(5), 2W(10), 3W(15), 4W(20) |
| **E** | 6M(126), 9M(189), 12M(252) |

Bear hit = % episodes where SPX return **< 0**.

### 2.4 Selection criteria

1. Prefer **n_events ∈ [15, 50]** (target 20–40).
2. Maximize **primary bear hit** (D: 1W; E: 12M).
3. Secondary: avg 1W–4W bear hit (D), avg 6M–12M bear hit (E).
4. Prefer **negative avg SPX** at primary horizon.

### 2.5 Combined tests

- **D alone** — best gate sets from sweep.
- **E alone** — best gate sets from sweep.
- **D + E sync** — same Friday both fire; bear hit at D 1W and E 12M on intersection dates.
- **Yield curve overlay** — slice events by `curve_regime_v2` from `macro_regime_log_v2` (STEEPENING vs NORMAL vs INVERTED).

---

## 3. Deliverables

| File | Description |
|------|-------------|
| `combo_d_sweep_results.csv` | All D experiments × horizons |
| `combo_e_sweep_results.csv` | All E experiments × horizons |
| `combo_de_sync_analysis.csv` | D+E simultaneous episodes |
| `combo_de_regime_overlay.csv` | Hit rates by curve regime |
| `combo_de_recommended_thresholds.csv` | Best configs + CONFIG baseline comparison |
| `combo_de_analysis_master.csv` | Unified ranking table |
| `study_meta.json` | Run metadata |

---

## 4. Execution

```bash
python3 testing/combo_de_thresholds/run_combo_de_study.py
```

---

## 5. Interpretation notes

- **80% bear hit** may be **unreachable** on full historical sample without n&lt;10; report best achievable trade-off honestly.
- Cheatsheet ~70%+ used curated instances / bullish framing — not comparable to this bearish backtest.
- Any CONFIG change requires `combo_detector.py` + backfill replay before production.
