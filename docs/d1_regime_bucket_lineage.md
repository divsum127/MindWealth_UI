# D1 regime bucket series — lineage

**Written 2026-08-17** per Rohit's 6 Aug instruction: *"D1 is documented as a derived product with its lineage stated — which table, which combo definitions, which priority order, which run date."*

## What D1 is, and what it is not

D1 is a **3-state daily bucket** — `BENIGN` / `ADVERSE` / `MIXED` — derived from named-combo fires via the dominance priority.

It is **not** an alternative view of the 5-dimension macro regime grid. The grid (fed cycle, curve, valuation, geo, liquidity) is a different object, stored in `macro_regime_log_v2` and served by `/macro/regime/history` and `regime_feed_export.py`. D1 sits **downstream** of combo detection, so "pick one of the three" was the wrong framing — there are two objects and one of them has two transports.

## Lineage

| Element | Value |
|---|---|
| **Generator** | `testing/macro_th_exp/run_d1_regime_bucket_feed.py` |
| **Series version** | `D1_regime_bucket_v1.2_2026-08-17` |
| **Run date** | 2026-08-17 |
| **Coverage** | 2018-01-01 → 2026-08-14, 2,258 daily rows, 450 Friday evaluations |
| **Source table** | `combo_fires` (via live detection re-run per Friday), with inputs from `daily_readings` |
| **Combo definitions** | `macro_intelligence/CONFIG.yaml` `named_combos`, with the D5-recalibrated D and E gates (`RECALIBRATED_GATES` in the generator: D = VXTS≥1.18 / CFTC≥95 / VIX≤13, 2-of-3; E = CAPE≥32 / NFCI≤−0.15 / CFTC≥85, 3-of-3) |
| **Priority order** | `dominant.PRIORITY` in `CONFIG.yaml` — **B(100) > C(90) > F(80) > E(70) > D(60) > G(50) > A(40)** |
| **Priority rule tag** | `CONFIG_PRIORITY_v2_B_ABOVE_C_LOW_N_DEMOTED` |
| **Low-n rule** | any combo with fewer than `min_matured_episodes` (5) matured episodes ranks below every validated combo. Live counts: A=174, B=274, **C=3**, D=455, E=508, F=704 |
| **Outputs** | `D1_regime_bucket_daily_2026-08-17.csv`, `..._fridays_...csv`, `..._feed_...json`, `..._feed_...md` |

## Version history

| Version | Change |
|---|---|
| v1.0 | Initial daily bucket series |
| v1.1 (2026-07-17) | Fixed the Combo C "always on" live-flag leak (a **state** problem) and WATCH→MIXED over-classification |
| **v1.2 (2026-08-17)** | Applies Rohit's 6 Aug sign-off: B above C, plus the low-n demotion rule. `dominant_rule` tag changed so consumers can detect the shift |

## v1.1 → v1.2 diff

| Measure | Value |
|---|---|
| Overlapping days compared | 2,149 |
| Days whose bucket changed | **35 (1.63%)** — 30 BENIGN→MIXED, 5 BENIGN→ADVERSE |
| Range of changed days | 2019-08-16 → 2022-10-06 |
| Bucket distribution v1.1 | BENIGN 1,617 · MIXED 294 · ADVERSE 238 |
| Bucket distribution v1.2 | BENIGN 1,648 · MIXED 358 · ADVERSE 252 |

**Attribution matters here:**

- **B above C changed nothing historically** — B and C **never co-fired** in the 2018–2026 window (0 days). The change is prospective.
- **The low-n rule is what moved days.** On days when C and F are both active, F is now dominant: of 106 C-active days, C stays dominant on 10 and F takes 96.

## Point-in-time status — state yes, data no

| Dimension | Point-in-time? |
|---|---|
| **Signal state** | **Yes.** Each Friday re-runs named-combo detection on `daily_readings` as-of that date. Combo C persistence is replayed sequentially (`ComboCReplay`) rather than read from the live `combo_c_cancel` flag — that was the v1.1 fix. |
| **Underlying data** | **No.** It reads whatever `daily_readings` holds at run time. NFCI, CAPE and CFTC are all revised after first print, so a Friday in 2019 is evaluated against today's revised values for those inputs. |

**So D1 must be described as "point-in-time on signal state, not on data"** — not "point-in-time" unqualified. Rebuilding it as data-point-in-time would need a vintaged `daily_readings` (first-print values retained alongside revisions), which does not exist today.

## Known limits

- Daily rows between Fridays are **forward-filled** (`is_forward_filled=True` Mon–Thu). No lookahead is introduced, but a mid-week regime change is not visible until the next Friday.
- Bucket mapping treats WATCH-only bearish legs as BENIGN — caution without a dominant adverse signal. Changing that changes the series.
- Combo G has **no matured episodes**, so it is demoted by the low-n rule and never becomes dominant in this series.
- The series inherits every input caveat from `daily_readings`, including the HY OAS and CNN F&G history changes listed in `docs/ssi_validation/STALE_BACKTESTS_AFTER_CNN_HY_FIXES.md`.
