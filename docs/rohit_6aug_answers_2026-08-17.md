# Answers to Rohit's 6 Aug email — verified from code and data

**Date:** 2026-08-17
**Source email:** "Re: regime doubts — answers on all three, plus portfolio/regime handoff (Ahil cc'd)", 6 Aug 2026
**Scope:** the questions in that email that can be answered from our own code and data. Items needing Rohit's or Ahil's decision are listed at the end as still open.

Every number below was queried today, not recalled.

---

## 1. Regime source of truth — what the stored table actually is

**The stored table is `macro_regime_log_v2`** (SQLite, `regime_json` column): 1,901 Friday evaluations, 1990-01-05 to 2026-06-05.

**Do the interfaces recompute?** Partly, and this is the honest answer to "no interface ever recomputes":

| Thing | Stored or recomputed |
|---|---|
| The 5 dimension **states** (fed cycle, curve, valuation, geo, liquidity) | **Stored** in `regime_json` |
| The per-dimension **multipliers** and `gross_mult` | **Recomputed on every read** from module constants in `regime_feed_export.py` |
| Daily rows between Fridays | Forward-filled on read, flagged `is_forward_filled` |

So `/macro/regime/history` and `regime_feed_export.py` do **not** each re-implement the logic — the API delegates to `regime_feed_as_records()`, one code path (`api/routers/macro.py:_load_regime_history_rows`). But the multipliers are derived at read time, so changing a constant silently changes every historical row ever served. That is the part worth fixing if you want "the stored table is the source of truth" to be literally true.

**The 20-date test you asked for now exists** — `tests/test_regime_source_of_truth.py`, 20 fixed dates (fixed, not drawn per run, so a failure reproduces), pulled through the API, the export module, and a direct table read. All three agree field-for-field. It also asserts the multipliers are reproducible from the stored states, which is the property that matters while they are computed on read.

**`D1_regime_bucket_daily.csv` is downstream, not an alternative.** It is a 3-state BENIGN/ADVERSE/MIXED bucket derived from combo fires via the dominance priority — a different object from the 5-dimension grid. Lineage is now documented (see §3).

---

## 2. Axiom 2 — the axioms bind, and the ×1.20 terms have never done anything

Your example: low-vol cap 85% × 1.20 VIX × 1.20 SSI = 104%, which violates Axiom 2.

**Answer: the axioms bind.** Two independent clamps in `portfolio_service._compute_ceiling`:

1. The SSI term is `min(1.0, ssi_multiplier)` — an SSI of 1.20 enters the chain as 1.00.
2. The final ceiling is `min(100.0, raw_ceiling)`.

So the live chain **cannot** produce 104%. Both ×1.20 terms are dead on the upside today. `portfolio_service` cannot produce an allocation the axioms forbid.

**Consequence for the U-shaped ladder:** the re-expansion leg is the whole value of your proposal (you narrowed it yourself — the de-lever leg is known not to help, 1.185 vs 1.221 in Block G). But re-expansion above 1.00 is currently a no-op. **It needs an explicit axiom exemption before it can do anything**, and that is your call, not something to discover in a backtest. This is the one thing blocking me from building the ladder.

Proof is pinned in `tests/test_api_portfolio.py::TestAxiom2CeilingBounds` — four tests asserting the ceiling stays ≤100% at SSI 1.0/1.2/5.0, that an SSI below 1.0 still cuts, and that the capped and raw terms are labelled separately.

---

## 3. `SSI ≥ 2` — it is a count, not a score

Nothing we emit is on that scale, which is why the comparison looked broken (SSI level has run 0.0849–0.4387, multiplier 1.20×).

**The answer is in your own Jun 18 document.** The bypass comment there reads: *"Combo F (Recovery Window) is active AND SSI confirms (>=2 of 4 signals)"*. So `SSI ≥ 2` means **at least 2 confirming Layer 2 signals** — a count of gates, not a value of the index.

Today's field is `layer2_confirmed_count`, now out of **6** gates rather than the original 4, with `min_confirmed = 2` in `SSI_CONFIG.yaml`. Modern reading: `layer2_confirmed_count >= 2 of 6`.

---

## 4. The two bypass rules — reconciled in code, decision still yours

| Source | Trigger | Target |
|---|---|---|
| Jun 18 spec | Combo B confirmed **OR** (Combo F active AND SSI ≥ 2) | the VIX level multiplier |
| Addendum A6 | Combo B **ACTIVE only** | `size_mult` in the C++ model |

Different trigger and different target — you were right that they conflict. Combo F has been active, so the Jun 18 clause fired while A6 did not. **That is exactly why the flag was on with Combo B inactive.**

Resolved 2026-08-07 in favour of the stricter A6 reading (`vix_bypass.py`, plus an assertion in `build_payload` and a runtime guard in the API). Which rule *should* govern is still yours to decide; the code follows A6 meanwhile.

**⚠️ This fix is on dev only. Prod still publishes `vix_bypass: true` with B inactive, and the C++ model reads the JSON from disk — so prod has been forcing `size_mult` to 1.0 and discarding the SSI multiplier every ordinary day since 7 Aug.** Merge + nightly rerun + API restart is the fix; it is the top item on the migration checklist.

---

## 5. "Equity ceiling" vs "ceiling scalar" — defined

| Term | Definition | Units |
|---|---|---|
| **Equity ceiling** | Maximum share of NAV deployable into equities in total, after every overlay. Portfolio-level cap. | % of NAV (e.g. 72%) |
| **Ceiling scalar** | Multiplier applied to an individual position inside `size = (NAV ÷ N) × conviction% × scalar`. | dimensionless (e.g. 0.90) |

Both are now written into `instruction_docs/portfolio_page/portfolio_sizer_v2_18June.md`.

---

## 6. The SSI multiplier row, and why the page showed 1.00× and 1.20×

The missing fifth row is now in the spec. Both panel values were correct for different terms:

- **SSI size multiplier (uncapped): 1.20×** — used for position sizing.
- **SSI ceiling term (capped at 1.00): 1.00×** — what the ceiling chain reads.

One number was carrying two meanings. Both are now labelled explicitly in the API response (`ssi_multiplier_raw`, `ssi_ceiling_term`, and a labelled ceiling step), so the two panels no longer look like a contradiction.

---

## 7. The 200-day vs 50-week MA divergence — real, now documented

The sizing overlay uses the **200-day** MA; Combo F's fire condition uses the **50-week** MA (~250 trading days). They will disagree at turning points: SPX can be above its 50-week MA while below its 200-day MA, so the detector can call a recovery active on a day the overlay is still applying a haircut. Documented in the spec; standardising is an open decision.

Also done per your instruction: **SPX below 200d MA is now ×0.90 in the spec**, matching the code.

---

## 8. VXTS feed check — the formula is right, but there is a name collision that would invert your ladder

Ran the check you asked for (`scripts/verify_vxts_feed.py`, 225 trading days, recomputed from Yahoo closes):

- On **225 of 225** dates the stored series matches **VIX3M / VIX** exactly (deviation 0.00000 on all but four).
- **Zero** dates where the stored value and the recomputation fall on opposite sides of 1.0.
- **Four stale dates** (2026-07-13 to 07-16) where a carried-forward 1.2355 diverges from the real ratio by up to 0.091. That is a staleness bug, not a formula bug.

**The thing worth your attention:** there are two reciprocal conventions in the codebase, both deliberate inside their own module, both called VXTS.

| Path | Formula | >1 means |
|---|---|---|
| Macro (`yahoo_pull.vix_term_structure`, `daily_readings.VXTS`, Combo D ≥1.18, Combo G ≤0.95) | **VIX3M / VIX** | contango (calm) |
| SSI (`yahoo_inputs.vix_ratio_series`) | **VIX / VIX3M** | backwardation (stress) |

Your ladder spec says *"VXTS below 1.0 (backwardation)"* — that is the **SSI** convention. Combo D reads the **macro** one. A ladder built on the wrong series inverts the trigger: it would re-expand in calm markets instead of at a washout. **Pin one convention before I build the ladder.** This is exactly the class of error your hedge-fund feed story was about, so I would rather raise it than assume.

---

## 9. CFTC percentile — reproduced, and it did not move

Queried `daily_readings` and `cftc_positioning` for 3–6 Aug:

| Date | Raw (Lev Money net) | 3yr percentile | Tier |
|---|---|---|---|
| 2026-08-03 | −302,372 | 67.31 | NORMAL |
| 2026-08-04 | −302,372 | 67.31 | NORMAL |
| 2026-08-05 | −302,372 | 67.31 | NORMAL |
| 2026-08-06 | −302,372 | 67.31 | NORMAL |
| 2026-08-07 | −333,099 | 52.23 | NORMAL |

**The macro store never moved 26 points.** It sat at 67.31 for four days on a static raw value and only changed on 7 Aug when the raw value changed. (In `cftc_positioning` the same field drifts 67.31 → 67.10 on 5 Aug — that is the 156-week window rolling by one observation, worth 0.2pt, exactly as you'd expect.)

**So where did the 93rd come from?** The SSI **Layer 3** FM percentile, a different series on a different window (the 2 Aug investigation recorded "RM=28th, FM=93rd" for the same period). The page was showing two different CFTC percentiles under one label. That is a display fault, not a computation fault.

**Your COMPUTE/NOTE/value question, answered:** the value displayed is **Leveraged Money net** alone, ranked over a **rolling 3-year (156-week)** window. A4b's "2006-present" is the **source history span**, not the ranking window — both are true and were being read as contradictory. The variable row now carries `series_percentiled`, `pctile_window`, and `pctile_source_history_start` explicitly so the three descriptions cannot drift apart again.

One caveat: prod is on 2 Aug code, so prod and dev can legitimately disagree on this field until the merge.

---

## 10. Cancel probability — why it read 2% and pointed the wrong way

Four separate defects, all confirmed in code:

1. **The spot price was a percentage.** `readings["WTI"]` is the **4-week % change** (`variables.WTI` paradigm `ROC`) — it was passed straight in as `current_wti`. So the model simulated a spot of about −0.13 against a strike of −0.13/1.05. This alone made the output meaningless.
2. **Sigma was a hardcoded constant.** `vol_annual: float = 0.35` — so the answer to "realised vol, or implied from CL options?" was **neither**. It was a literal.
3. **Banked Fridays never reduced the barrier count.** Every run rebuilt all four strikes from today's spot, so 1 of 4 banked simulated the same four barriers as 0 of 4. The number could not rise as the legs banked.
4. **The barrier was the wrong quantity.** The rule is "WTI 4-week return < +5%", but the model asked whether the price stayed below today × 1.05 for the whole run — a far harsher condition, which is why a tape sitting flat after a past rally scored as near-impossible while the real leg was comfortably passing.

Plus `cpi_not_hot_rate=0.52` hardcoded at the call site and squared regardless of how long the cancel had left — CPI releases monthly, so a cancel three Fridays out faces **one** print, not two.

**All fixed.** Sigma now comes from **OVX** (CBOE Crude Oil VIX, the implied vol of WTI options — the market's own probability, as you asked), falling back to trailing 60-day realised, with `sigma_source` and `sigma_as_of` in the payload and on the page. Today: OVX gives **σ = 0.495**, trailing realised **0.533** — the old 0.35 understated both. Banked Fridays now remove barriers, and the barrier is the trailing 4-week ROC.

Effect on the live reading (WTI spot ~82.4, current 4wk ROC **−7.7%**, 1 of 4 banked):

| | WTI leg |
|---|---|
| Old model | 8.3% |
| Fixed model, 0 banked | 41.8% |
| **Fixed model, 1 banked (today)** | **45.8%** |
| Fixed model, 3 banked | 87.4% |

It now rises as Fridays bank, which is the behaviour you described.

**One thing to note:** `combo_c_cancel.last_check_date` is **2026-05-22**, so the Friday counter has not advanced in nearly three months. The probability model is fixed; whether the counter itself is being advanced by the nightly job is a separate question I am still checking.

---

## 11. Analog tables — one wrong column name explained every symptom

The DB query behind the per-combo analog table referenced `cf.macro_regime_json`. **That column does not exist** (it is `cf.macro_regime`), so the query raised on every call, the exception was swallowed, and the endpoint fell back to the nightly JSON's `analog_details` block — which is written for the **dominant combo only**. Hence all seven combos serving Combo C's three fire dates.

The rest followed from the same fallback: `find_analog_details` wrote the combo's **primary horizon** return into the `spx_3m_pct` field (C's primary is 6M — hence "6M identical to 3M in every row"), and the block has no 9M field at all (hence "9M reads TBD"). CONTEXT / MAX DD / BOTTOM TIMING were never computed anywhere.

Fixed: per-combo DB read always, every horizon reported on its own, and MAX DD (peak-to-trough) / BOTTOM TIMING / CONTEXT computed. Two more queries had the same wrong column name and were also silently failing (`_db_combo_fire_detail`, `build_historical_analogs_block` — the AI Analyst's analog block never populated).

Real per-combo history now serving, matured episodes only:

| Combo | Matured episodes | Most recent |
|---|---|---|
| A | 6+ | 2024-11-29 |
| B | 6+ | 2020-09-04 |
| **C** | **3** (flagged insufficient) | 2025-04-14 |
| D | 6+ | 2021-12-24 |
| E | 6+ | 2025-08-15 |
| F | 6+ | 2026-02-13 |
| **G** | **0** — returns empty, not a fabricated row | — |

The 2008-06-16 Combo C fire now shows what the tab exists for: **−44.68% max drawdown, trough 157 days in**.

A related data-quality finding: `forward_returns` stores **0.0, not NULL**, for horizons that have not elapsed — so an unmatured 9M read as a realised 0.00% return. Each horizon is now nulled on its own maturity date.

**You asked me to pull the tab from the nav until rebuilt. I rebuilt it instead** — the data was already there and the fix was one column name. Say the word if you still want it hidden.

---

## 12. Combo priority — B above C, applied, with the historical effect measured

Applied in `CONFIG.yaml` (`B: 100, C: 90`) and in the live `resolve_dominant` path, plus your general rule as `low_n_demotion` / `min_matured_episodes: 5`. Episode counts reuse the existing hit-rate path, so the ranking and the briefing's "insufficient episodes" wording can never disagree.

Live counts confirm your numbers: **C n=3**, B n=274, A n=174, D n=455, E n=508, F n=704.

**Two consequences you should know about before this reaches prod:**

1. **B above C changes nothing historically.** In the D1 window (2018–2026) **B and C never co-fired** — 0 days. Your oil-shock scenario is prospective, not historical. The fix is still right; it just has no backtest footprint.
2. **The low-n rule is what actually moves days.** C is demoted below every validated combo, so on days when C and F are both active, **F is now dominant**. Of 106 C-active days in the regenerated series, C stays dominant on 10 and F takes 96. That is a bigger behavioural change than the B/C swap, and it follows from your rule rather than from a C-specific decision — flagging it because the posture on those days flips from bearish to bullish.

D1 regenerated as **v1.2** (`dominant_rule: CONFIG_PRIORITY_v2_B_ABOVE_C_LOW_N_DEMOTED`), 2,258 daily rows. Diff against v1.1: **35 of 2,149 overlapping days changed bucket (1.63%)** — 30 BENIGN→MIXED, 5 BENIGN→ADVERSE, all between 2019-08 and 2022-10.

The priority order is now emitted in the nightly payload (`combo_priority_order`) so it can be shown on the page — you were right that it appeared on no tab.

---

## 13. D1 lineage and point-in-time

See `docs/d1_regime_bucket_lineage.md` for the full statement. Summary:

- **Table:** derived from `combo_fires` via the CONFIG dominance priority, not from the 5-dimension grid.
- **Point-in-time on signal state:** yes — each Friday re-runs detection on `daily_readings` as-of that date, with Combo C replayed sequentially rather than read from the live flag (the v1.1 fix).
- **Point-in-time on data:** **no.** It reads whatever `daily_readings` holds today, and NFCI, CAPE and CFTC are all revised after first print. So D1 is point-in-time on state but **not** on data, and should be described that way rather than "point-in-time" flat out — your instinct was right.

---

## 14. Replay floors, variable by variable

From actual coverage in `daily_readings` (no proxy extension):

| Variable | Real history starts | Notes |
|---|---|---|
| NFCI | 1973 | earliest series we hold |
| HY OAS | **1996-12-31** | now real ICE back to Dec 1996; only **7** proxy dates remain (the bond holidays) |
| CAPE | long | Shiller series |
| WTI | 2000-08 | |
| VIX | long | |
| VXTS | 2007 | ^VIX3M inception |
| WALCL | 2002 | **caps the 5-dimension grid** |
| CFTC | **2006** | **caps the 5-dimension grid** |

**So the macro regime grid caps around 2006** — your estimate was right. SSI cannot go back 25 years and never will (NAAIM 2006, CNN F&G 2011 with a 2011–12 hole, DBMF 2019). Conviction is uneven by geography: 18 US tickers have 25–32 years via SEC EDGAR, Canada about 8, India and NZ blocked.

**Survivorship — the thing to solve first, and we have not solved it.** Our ~195 tickers are today's universe, i.e. today's survivors. No point-in-time universe exists anywhere in the repo, and there is no delisted-names source wired in. Running the current list back 25 years would produce exactly the magnificent false result you described. Until a point-in-time universe exists, **the honest window caps at wherever the current universe was formed** — I am not going to present a 25-year number off a survivor list.

---

## 15. Multiplier stacking — you were right, and it is worse than 0.64

Ran the check (`scripts/check_regime_multiplier_stacking.py`, 1,901 Friday evaluations):

- TIGHTENING: 763 Fridays (40.1%)
- INVERTED: 85 Fridays (4.5%)
- **Both: 74 Fridays (3.9%) — 2.17× more often than independence implies.** So not a rare combination, as you said.
- Stacked TIGHTENING × INVERTED = **0.6396**, a 36.0% cut.
- **With all five dimensions on those days, `gross_mult` runs 0.5165–0.6396, median 0.5590** — a 44% cut, worse than the 36% from the two terms alone.
- Co-occurrences cluster in 2000 (18), 2006 (16), 2007 (6), 2022 (18), 2023 (16).
- Across all 1,901 Fridays, `gross_mult` reaches the 1.00 ceiling on just **4** days.

That last number is the clearest statement of the asymmetry: the regime overlay is cutting almost always and can never add.

**Geo dropped to 1.00** per your instruction (was CRISIS 0.70 / ELEVATED_RISK 0.85), tagged `v1_illustrative_unsigned_geo_off` so any consumer comparing feeds sees the switch.

**The clip question, answered but not changed:** `MIN_MULT/MAX_MULT = 0.40/1.00` means regime can only shrink while VIX and SSI reach 1.20. It was not deliberate — it fell out of where the clip was set. **Left unchanged pending your call**, since making it two-sided runs into the same Axiom 2 problem as §2.

**The file is renamed** — `multiplier_spec.md` → `regime_dimension_multipliers_v1_unsigned.md`, named after what it does rather than after a person, with the "Illustrative for Michele demo" status line removed.

**"Dimensions" is now qualified everywhere** it appears: 5 = macro regime grid (fed, curve, valuation, geo, liquidity); 4 = signal axes (asset, function, interval, direction).

---

## 16. HY OAS bands — re-derived from the real series (proposal, not applied)

Ran `scripts/derive_hy_oas_bands.py` on 7,730 real ICE observations, 1996-12-31 to 2026-08-14 (7 proxy dates excluded — the bond holidays you accepted).

Distribution: min 241bps, **median 450bps**, max 2,182bps. Percentiles: p80 663, p90 805, **p95 917**, p99 1,674.

Coverage of the current bands:

| Band | Share of history |
|---|---|
| <300bps | 10.97% |
| 300–500bps | 49.64% |
| 500–700bps | 21.97% |
| **>700bps ("crisis")** | **17.43%** |

**That is the problem with the current edges:** they put 17.4% of history in the crisis bucket. A crisis that happens 17% of the time is not a crisis. The empirical p95 is 917bps, not 700.

Percentile-anchored alternative, for your sign-off (**nothing changed in code**): benign <450, mild 450–660, stress 660–920, crisis >920 — giving each band a known 50/30/15/5 share of history. 70.3% of days would sit in a different band than today, so this is a real recalibration, not a tweak. Today's live ceiling only reads today's value, so there is no immediate live behaviour change either way.

---

## Still open — needs you or Ahil

| Item | Blocked on |
|---|---|
| VIX ladder U-shape | **You** — whether the re-expansion leg gets an explicit Axiom 2 exemption (§2). Without it the ×1.20 terms stay no-ops and the ladder cannot work. Also which VXTS convention to build on (§8). |
| HY band final numbers | **You** — sign off the proposal in §16 or send different edges. |
| `gross_mult` clip one-sided | **You** — deliberate or to be changed (§15). |
| Michele exercise provenance | **You** — who asked, what the deliverable is, who sees the output. I renamed the file; I cannot answer what the exercise is. |
| Proportional vs conviction-first ceiling cut | **Ahil** — being passed to him with the brief, per your instruction. |
| Stress / low-vol cluster budgets | **Ahil** — realised cluster correlations in the five stress windows, passed back with the correlation brief. |
| P3 point-in-time harness scope | **Ahil** — no `P3_scoping.md` exists in the repo yet. |
| A1 real SSI-ceiling + conviction-tier feed date | **Me**, after the prod merge lands — the SSI-ceiling series is exportable today, the conviction archive only starts 2026-05-15. |
| Composite-score 401 | **Out of band** — missing `X-API-Key` against `api/dependencies.py::require_api_key`. Needs a key handed to Ahil over a secure channel, not a code change. |
| Composite v4 PROXY BASIS (`avg_hold_days`, `avg_loss_return` N/A) | **Me** — not yet re-run on real data; will confirm separately. |
| Prod `vix_bypass` merge | **Human/ops** — prod clone is deploy-only (§4). Top of the migration checklist. |

## Environments

**8514 and 8512 are not the same build.** 8514 is dev Nuxt on `chatbot-dev`; 8512 is prod Nuxt on the prod branch at `64e17ca26` (2 Aug). Dev is **22 commits ahead** of `origin/chatbot-prod`. That is why the two environments disagree about whether Combo C is firing, and it does make day-over-day comparisons across them ambiguous. No merge date is set — that is a release decision.
