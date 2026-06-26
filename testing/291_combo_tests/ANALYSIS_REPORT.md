# 298-Combo Discovery Analysis — Promotion Shortlist & Economic Rationale

**Date:** 2026-06-25  
**Task:** Item 15 — AUTO-DISCOVERED COMBOS + ECONOMIC RATIONALE  
**Source run:** `macro_intelligence/analysis/combo_discovery/combo_discovery_20260606.json` (Part H, 2026-06-06)  
**Spec:** 9-step pipeline in `testing/macro_th_exp/understanding_and_research/Macro_Regime_System_v2_Understanding.md` §10  

---

## 1. Executive summary

The engine enumerates **298 signatures** (12 singles + 66 pairs + 220 triples from 12 macro variables). After the full gate funnel:

| Stage | Gate | Count |
|-------|------|------:|
| Enumerated | — | 298 |
| With ≥1 fire | detection | 225 |
| Surfaced | ≥3 fires, ≥60% 3m hit | 187 |
| Survivors | beta + directionality (Steps 5–6) | 132 |
| **Promotion candidates** | **≥5 fires, ≥80% 3m hit** | **62** |

**Key findings:**

1. **All 62 promotion candidates are bullish** (inferred SPX-up direction). There are **zero bearish** auto-discovered combos above the 80% gate at 3m. This is consistent with equity drift dominating 3m windows and with the macro extreme engine mostly flagging washout / liquidity / reflation episodes that resolve higher.

2. **Heavy redundancy:** 62 signatures collapse to **52 unique fire-date clusters**. Many combos share identical fire calendars (e.g. five `CPI+*+WALCL` variants fire on the same three Fridays in Feb–Mar 2024). **Subset combos** (e.g. `CPI+WTI` vs `CAPE+CPI+WTI`) often have the same hit rate — the extra leg adds no information.

3. **Step 7 (economic story) was never run** (`use_claude=False`). Every candidate shows `story_status=SKIPPED`. Per spec, incoherent stories would demote candidates; we must supply rationale manually before any naming.

4. **Overlap with named combos A–G is high** for the best statistical performers:
   - `CFTC+VIX+VXTS` → superset of **Combo D** (VXTS+VIX+CFTC) and **Combo G** (VIX+VXTS)
   - `CNH+GSR+WTI` → superset of **Combo F** (GSR+WTI+CNH)
   - `CNH+VIX+WALCL` → partial **Combo C** legs (CNH+WALCL; missing NFCI)

5. **Recommended action:** Promote **6–8 distinct economic themes** (not 62 signatures) to Rohit review. Defer naming until v2 regime re-tag and Step 7 Claude review on the shortlist.

---

## 2. Pipeline gates (what “80%” means)

Per Part H spec:

- **Primary horizon:** `spx_3m` (63 trading days)
- **Promotion gate (Step 8):** ≥5 fires **and** ≥80% hit rate at 3m **and** beta filter pass **and** directionality pass (≥2 of 5 regime dims ≥50% hit)
- **Beta filter (Step 5):** In hostile regimes (HIKING_EARLY, HIKING_LATE, TIGHTENING, INVERTED curve), hit rate ≥55%; combo avg return must beat unconditional, single-variable, and regime-base averages
- **Story gate (Step 7):** Claude narrative; `story_coherent=false` removes promotion flag (not applied in this run)

**Caveat:** Fires are tagged with **legacy** regime JSON, not shadow v2 labels. Beta hostile slices should be re-run before production promotion.

---

## 3. Variable frequency across 62 candidates

| Variable | Appears in # of 62 | Role |
|----------|-------------------:|------|
| CURVE | 26 | Yield-curve stress / inversion unwind |
| CAPE | 19 | Valuation extreme (slow-burn) |
| WALCL | 19 | Fed balance sheet / liquidity |
| CPI | 19 | Inflation surprise |
| CNH | 19 | EM FX stress (offshore USD) |
| GSR | 15 | Gold/silver ratio (risk-off bid) |
| VIX | 13 | Equity vol |
| VXTS | 13 | Term structure complacency |
| CFTC | 12 | Positioning (fund manager percentile) |
| WTI | 11 | Energy / reflation |
| HY | 2 | Credit stress |
| NFCI | 2 | Financial conditions |

**Absent from promotion set:** standalone NFCI/HY-heavy combos (those map to named **Combo A/B** territory with different leg logic).

---

## 4. Thematic clusters (deduplicated)

### Tier 1 — Strong mechanism + multi-cycle history (prioritize for Step 7)

| ID | Representative signature | n | 3m HR | Unique dates | Era spread | Economic rationale |
|----|--------------------------|--:|------:|-------------:|------------|-------------------|
| **T1-A** | `CFTC+VIX+VXTS` | 13 | 100% | 13 | 2008–2020 | **Complacent positioning + low realized vol.** Extreme CFTC net long (crowded risk-on) while VIX is suppressed and VXTS in contango signals near-term complacency. Historically resolves with a **vol shock rally** (washout then Fed response) — 2010, 2018 Q4, Mar–Jul 2020. **Overlaps Combo D/G** — treat as generic echo, not a new name. |
| **T1-B** | `CNH+VIX` | 26 | 88.5% | 26 | 2015–2022 | **EM dollar stress + equity fear.** CNH weakness (offshore RMB pressure) coincident with elevated VIX marks global risk-off that historically preceded **policy response and SPX recovery** (2015 China scare, 2016, 2018, 2020, 2022). Distinct from Combo B (needs HY+CFTC washout). |
| **T1-C** | `CURVE+WALCL` | 73 | 84.9% | 69 | 2022–2024 | **Curve dislocation + expanding liquidity.** Inverted or stressed curve alongside expanding Fed balance sheet (QE / BTFP / liquidity facilities) = classic **“Fed puts curve”** reflation. Dense 2022–24 sample; high n makes this the most statistically robust survivor. |
| **T1-D** | `CNH+GSR+WTI` | 15 | 93.3% | 15 | 2016–2023 | **Commodity reflation after stress.** GSR elevated (gold bid), oil active, CNH stress = **Combo F** generic superset. Episodes: 2016 post-oil crash, 2020 reopening, 2022 energy shock. Mechanism: real-asset bid + EM stabilization → risk-on. |
| **T1-E** | `CAPE+VIX+VXTS` | 23 | 87.0% | 23 | 2008–2026 | **High valuation + vol complacency.** CAPE extreme with low VIX and steep VXTS = **melt-up / bubble phase** where corrections are bought. 2008–09 fires are post-crash recovery (selection bias risk); 2018/2020/2025 cluster is more representative. |

### Tier 2 — Credible but regime- or sample-dependent

| ID | Representative | n | 3m HR | Concern | Rationale |
|----|--------------|--:|------:|---------|-----------|
| **T2-A** | `CNH+CURVE+WALCL` | 23 | 87.0% | 2022–23 heavy | EM stress + curve + liquidity injection → **policy pivot trades** (similar to T1-C with CNH overlay). |
| **T2-B** | `CURVE+GSR+WALCL` | 27 | 85.2% | 2022–24 only | Safe-haven bid (GSR) + curve stress + Fed liquidity = **stagflation scare → easing** pattern. |
| **T2-C** | `CAPE+NFCI+VXTS` | 21 | 85.7% | 2008 + 2021 dual cluster | Tight financial conditions resolving (NFCI) from valuation extremes; 2021 cluster is **post-COVID liquidity** — may not generalize. |
| **T2-D** | `CAPE+HY` | 8 | 87.5% | Oct 2023 + Apr 2025 only | Credit stress at valuation extremes → **relief rallies** when spreads stabilize. Small n, recent-only. |

### Tier 3 — Defer (overfit / subset redundancy)

| Pattern | Example | Issue |
|---------|---------|-------|
| **2024 CPI batch** | `CPI+WALCL`, `CPI+CURVE+WALCL`, +3 variants | Only **3 unique Fridays** (Feb–Mar 2024). Six raw fires from duplicate direction rows. 100% hit is **one macro episode** (disinflation pivot). |
| **2026 forward cluster** | `CPI+GSR`, `CPI+WTI`, `CAPE+CPI+*` | Fires in Mar–Jun **2026** dominate; many combos share 4–7 dates. Too early to validate; overlaps Tier 3 inflation-reflation narrative. |
| **Pure subsets** | `CPI+WTI` ≡ `CAPE+CPI+WTI` fires | Identical calendar — keep **one** representative per cluster. |
| **Near-miss 80%** | `CFTC+CURVE` (76%, n=76) | Large n but below promotion gate — watch list only. |

---

## 5. Overlap with named combos A–G

| Named | Legs | Auto-discovered supersets / echoes |
|-------|------|----------------------------------|
| **A** | NFCI, WALCL | None in promo set (NFCI only 2×) |
| **B** | VIX, HY, CFTC | No exact match; `CFTC+VIX+VXTS` is **different** (no HY, adds VXTS) |
| **C** | NFCI, WALCL, CNH | Partial: `CNH+VIX+WALCL` (missing NFCI) |
| **D** | VXTS, VIX, CFTC | **Exact variable set:** `CFTC+VIX+VXTS` (bullish generic vs bearish D) |
| **E** | CAPE, NFCI, CPI | Partial: `CAPE+CFTC+CPI`, `CAPE+CPI` (missing NFCI or different 3rd leg) |
| **F** | GSR, WTI, CNH | **Exact set:** `CNH+GSR+WTI` |
| **G** | VIX, VXTS | Subset of `CFTC+VIX+VXTS`, `CNH+VIX+VXTS`, `CAPE+VIX+VXTS` |

**Implication:** Most “new” high-hit combos are **not novel structure** — they are generic co-firing of legs already encoded in A–G, often with **opposite directional inference** (generic engine infers bullish from leg directions; Combo D is explicitly bearish).

---

## 6. Recommended shortlist for Rohit (8 themes → 8 signatures)

Use **one canonical signature per theme** for Step 7 Claude review and v2 regime re-tag:

| Priority | Signature | Tier | Proposed working name | Action |
|---------:|-----------|------|----------------------|--------|
| 1 | `CURVE+WALCL` | T1-C | Liquidity-Curve Put | Highest n, clearest Fed mechanism |
| 2 | `CNH+VIX` | T1-B | EM-Fear Washout | Multi-cycle, distinct from Combo B |
| 3 | `CNH+GSR+WTI` | T1-D | Commodity Reflation (F-echo) | Align with Combo F framing |
| 4 | `CFTC+VIX+VXTS` | T1-A | Complacency Pop (D/G-echo) | Document as generic D/G, not new combo |
| 5 | `CAPE+VIX+VXTS` | T1-E | Valuation Melt-Up | CAPE-conditional sizing note |
| 6 | `CURVE+GSR+WALCL` | T2-B | Stagflation Scare → Ease | 2022–24 heavy |
| 7 | `CNH+CURVE+WALCL` | T2-A | EM + Curve Liquidity | |
| 8 | `CAPE+HY` | T2-D | Credit-Valuation Relief | Low n — watch only |

**Do not shortlist** the 2024 CPI-only variants or 2026-forward CPI clusters until ≥2 independent episodes validate.

---

## 7. Next steps (per spec)

1. **Re-tag fires** with shadow v2 regime labels; re-run beta hostile filter on the 8-signature shortlist.
2. **Run Step 7:** `scripts/run_combo_discovery_pipeline.py --use-claude --write-report` on shortlist only (or manual Claude review using fire dates + headlines).
3. **Rohit decision:** 55% vs 60% hostile hit bar; whether generic echoes of D/F/G should enter `generic_combo_watch` JSON or stay research-only.
4. **No production naming** until story_coherent=true and mechanism approved.

---

## 8. Output files in this directory

| File | Description |
|------|-------------|
| `promotion_candidates_62.csv` | Full 62 candidates with fire dates (from pipeline JSON) |
| `shortlist_tiered.csv` | 8-theme shortlist + tier + rationale columns |
| `cluster_redundancy.csv` | Fire-date clusters with member signatures |
| `funnel_summary.json` | Machine-readable funnel counts |

---

*Generated from Part H `combo_discovery_20260606.json`. Step 7 narratives pending.*
