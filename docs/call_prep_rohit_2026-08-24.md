# Call prep — Rohit's 6 points, 2026-08-24

Every number below was queried today from the live trees, the sheet, and the run artefacts. Nothing recalled.

---

## 1. Dev vs prod — why "fixed on dev" keeps failing your test on :8512

### There are two prod surfaces, and only one of them is mine

| Surface | Path | Branch / repo | State today |
|---|---|---|---|
| **API** `:8506` | `/home/ubuntu/uiv2/prod/MindWealth_UI` | `chatbot-prod` | Merged + deployed **2026-08-20** @ `59e351294` (74 commits, zero conflicts). **8 dev commits behind** as of today. |
| **Public website** `:8512` = `www.mindwealth.co` | `/home/ubuntu/MindwealthUI_Vue_prod` | `ui-dev` in **Parth's repo** (`D-ParthChauhan/MindwealthUI_Vue`) | Checkout `ba2bcfd`, **23 commits behind** `ui-dev` head `c17c5c6`. Running bundle built **18 Aug 07:23 UTC**. |

**This is the whole disagreement.** You test `:8512`. That box is not deployed by my `prod-pull-and-restart.sh` — it is a separate repo on Parth's deploy path, and it has not been rebuilt since 18 Aug.

**Hard proof, run today:**

- `/home/ubuntu/MindwealthUI_Vue_prod` has **no `components/sentiment/` directory at all** — so none of the Sentiment page work exists in the public build.
- Prod mapper still prints `NH/NL Ratio`. Dev prints `NH Share (NH/(NH+NL))`. That is your own label item, fixed on dev on 17 Aug, still wrong on the site.
- `components/portfolio/PortfolioOverviewView.vue` — present on dev, **absent on prod**.

### So what is actually where

| Bucket | Where it is | Count |
|---|---|---|
| Backend/API fixes | **On prod** since 20 Aug | Most SSI resilience, coverage gating, regime feed, AI Analyst, chatbot router guardrail |
| Backend fixes newer than 20 Aug | Dev only | 8 commits — CFTC 2006 history restore, FOMC calendar fix, flag placeholder cuts, CNN crypto-row repair, multiplier persistence |
| **Anything you look at on a page** | **Dev only** — blocked on Parth's Nuxt rebuild | Sentiment page in full, Layer 2 confirm-driver rows, AAII Weekly label, NH share label, z-score/weight rows, freshness annotations, UTC-safe signal dates |

Of the 16 "fixed on dev" replies, the large majority are in the third bucket. They are done, tested, and invisible to you until the Nuxt prod tree is rebuilt.

### The merge date — what I'll commit to on the call

Proposed: **Tuesday 26 Aug**, one window, both halves:

1. `chatbot-dev` → `chatbot-prod`, deploy API `:8506`.
2. **Rebuild `positioning.json` and restart `mindwealth-api.service`** — mandatory, not cosmetic (see warning below).
3. Parth rebuilds `/home/ubuntu/MindwealthUI_Vue_prod` from `ui-dev` and restarts `mindwealth-ui.service`. **I cannot do this step** — different repo, his deploy.

**⚠️ Warning you need before you approve the date.** Two of the 8 pending commits are data-correctness fixes that **change numbers on prod**:

- CFTC history goes **2017-01-03 → 2006-06-13** (483 → 1034 analysis weeks). Every FM/RM percentile on prod is currently ranked against a short window and will move.
- Flag firing changes: squeeze **181 → 169** weeks, liquidity exit **162 → 214** weeks over the full sample.
- Consequence: **any SSI or CFTC backtest run on prod before this deploy sits on the truncated sample.** That is the stale-backtest list you asked for.

**One URL after that: `https://www.mindwealth.co`.** Nothing else. If it is not on that URL, treat it as not done, and that is a fair rule.

---

## 2. The 31 rows — reconciliation, and the 6 decisions

### Count doesn't match, worth 60 seconds on the call

Rows where my reply is filled and your feedback column is empty: **44**, not 31. Your 31 is probably a narrower filter (you may be excluding the ones you have since answered in mail rather than in-sheet). The 13 extra are rows 7, 8, 11, 12, 13, 15, 20, 23, 67–72 — mostly early verification rows.

### Your 6 "need decisions" — one correction first

**Row 151 does not exist.** The sheet ends at **row 142**. NAAIM is **row 142**. Your copy is offset by 9 — likely a filter or a hidden-row view. Worth fixing so we stop mis-citing rows at each other.

**Row 27 is not a decision either** — it is `Completed`, CBOE Skew gate votes wired, answer already in column G. It needs your eyes, not your call. That leaves **five real decisions: 42, 45, 53, 54, 142.**

| Row | Item | Decision you owe |
|---|---|---|
| 42 | Contrarian inversion validation | Whether RM goes back on **LIQUIDITY EXIT** only (evidence says yes — see below) |
| 45 | COT indexing / sample start | Now superseded by the 2003 GO — becomes an execution item, not a decision |
| 53 | FM long-gate cutoff | Pick a percentile — table below |
| 54 | Layer 2 gate z × count | Keep defaults / tighten / demote Layer 2 to sizing-overlay-only |
| 142 | NAAIM feed dead | (a) pay, (b) manual weekly, (c) re-spec Layer 1 to 3 signals |

---

## Row 53 — FM long-gate sweep, one line per threshold

`LONG_RULES['cot_fast_money_max_pct']`, sweep 15th→45th. Run 2026-08-07, gate crossings from 2010.

| FM cut | n | 1m avg | 1m win | 3m avg | 3m win | 6m avg | 6m win | 12m avg |
|---|---|---|---|---|---|---|---|---|
| < 15 | 159 | 0.83% | 61.6% | 2.83% | 72.7% | 7.96% | 84.9% | 20.55% |
| **< 20** | **203** | **0.94%** | **62.6%** | **3.13%** | **73.7%** | **8.35%** | **87.7%** | **19.62%** |
| < 25 | 234 | 0.90% | 65.0% | 2.99% | 73.7% | 7.69% | 86.0% | 18.69% |
| < 30 *(live default)* | 274 | 0.89% | 65.3% | 2.78% | 72.8% | 7.48% | 85.0% | 17.81% |
| < 35 | 308 | 0.95% | 66.2% | 2.80% | 74.4% | 7.22% | 83.6% | 17.34% |
| < 40 | 343 | 0.99% | 66.7% | 2.85% | 74.2% | 7.12% | 83.0% | 17.30% |
| < 45 | 388 | 1.05% | 67.7% | 2.97% | 74.9% | 6.95% | 82.1% | 16.81% |

**My recommendation: 20.** Best 3m avg (3.13%), best 6m (8.35% / 87.7% win), and the return profile decays monotonically as you loosen past it — which is what a real edge looks like rather than noise. 15 is sharper on 12m but on 22% fewer events.

**Caveat I must state before you pick:** this ran on **2026-08-07**, before the 20 Aug date-parse fix. The FM percentiles it ranks against came from the truncated 2017+ sample. **The shape will hold, the levels may shift.** I would rather re-run it on the 2006 (soon 2003) sample and give you the same table again before you lock CONFIG — 1 day of work.

---

## Row 54 — Layer 2 joint grid, one line per cell

`gate_z_min` × `min_confirmed`, 6-gate production logic, from 2015. Long gate = SSI 5y pctile ≤ 20. Production today is **z ≥ 0.5, min 2 of 6**.

| z ≥ | min of 6 | n signal | freq % | n long+gate | 3m hit % | 3m FP win % | 3m avg | 6m avg | 12m avg |
|---|---|---|---|---|---|---|---|---|---|
| 0.00 | 1 | 359 | 9.3% | 11 | 18.2% | 76.3% | −3.68% | −7.29% | 0.60% |
| 0.00 | 2 | 1600 | 41.3% | 88 | 38.6% | 75.5% | −2.10% | −1.95% | 5.78% |
| 0.00 | 3 | 2332 | 60.2% | 183 | 36.6% | 77.3% | −1.09% | 1.47% | 12.01% |
| 0.00 | 4 | 1154 | 29.8% | 60 | 38.3% | 80.7% | −0.77% | 0.97% | 12.24% |
| 0.25 | 1 | 574 | 14.8% | 17 | 29.4% | 77.5% | −1.16% | −5.82% | 5.50% |
| 0.25 | 2 | 1988 | 51.3% | 138 | 38.4% | 75.6% | −1.65% | −1.47% | 6.48% |
| 0.25 | 3 | 1927 | 49.8% | 145 | 38.6% | 79.1% | −0.95% | 2.04% | 12.99% |
| 0.25 | 4 | 703 | 18.2% | 38 | 29.0% | 81.6% | −1.44% | −0.06% | 11.35% |
| 0.50 | 1 | 890 | 23.0% | 40 | 40.0% | 77.9% | −0.45% | −5.84% | 3.23% |
| **0.50** | **2** *(live)* | **1945** | **50.2%** | **160** | **41.3%** | **77.5%** | **−1.20%** | **−0.12%** | **8.21%** |
| **0.50** | **3** | **1387** | **35.8%** | **107** | **37.4%** | **80.6%** | **−0.23%** | **2.80%** | **14.49%** |
| 0.50 | 4 | 351 | 9.1% | 20 | 20.0% | 85.9% | −2.74% | −1.06% | 10.92% |
| 0.75 | 1 | 1271 | 32.8% | 74 | 36.5% | 78.4% | −2.36% | −6.89% | 2.71% |
| 0.75 | 2 | 1268 | 32.8% | 134 | 38.8% | 81.2% | −1.68% | 0.52% | 9.94% |
| 0.75 | 3 | 296 | 7.6% | 51 | 25.5% | 86.8% | −2.96% | 0.43% | 9.16% |
| 0.75 | 4 | 10 | 0.3% | 0 | n/a | 100% | n/a | n/a | n/a |
| 1.00 | 1 | 1657 | 42.8% | 108 | 35.2% | 79.6% | −3.33% | −6.15% | 2.03% |
| 1.00 | 2 | 827 | 21.4% | 109 | 38.5% | 82.9% | −1.78% | 0.48% | 9.63% |
| 1.00 | 3 | 122 | 3.2% | 32 | 28.1% | 82.2% | −2.03% | 0.72% | 9.41% |
| 1.00 | 4 | 0 | 0.0% | 0 | n/a | n/a | n/a | n/a | n/a |

**The uncomfortable read: every single cell has a negative 3m average, and in every cell the "false positives" beat the gated signals.** The current default (0.5 / 2) is the best of a bad set on 3m hit rate (41.3%), and 0.5 / 3 is the best on 6m/12m. Nothing here proves the gate adds value as a **long entry condition**.

**My recommendation: option (c) — demote Layer 2 from a long-entry gate to a sizing overlay**, and if you want to keep it as a gate for now, move to **0.5 / 3** (better 6m/12m, 29% fewer signals). z ≥ 0.75 with min 4 is dead (10 signals, 0 gated) — that corner of your grid is unusable, which is itself a finding.

**Same caveat:** run 2026-08-11, before the McClellan and %>200DMA CSV repairs landed. Those are Layer 2 inputs. Re-run recommended before CONFIG changes.

---

## 3. Row 142 / NAAIM — the options, costed

**What happened.** The NAAIM Exposure Index public feed is gone. Verified 18 Aug and re-verified 20 Aug: the WordPress page 301s, `index.naaim.org` is a sign-in wall, both public iframes still load but are **frozen at 2026-05-13 / 2026-05-06** (older than our own cache), Wayback has no snapshot after 31 May, the WP REST API exposes newsletters only, `index.naaim.org/api/exposure` 404s, `api.naaim.org` does not resolve, FRED carries no NAAIM series.

**Our last print: 2026-07-29 at 79.7.** That is 26 days stale today. NAAIM is the **largest Layer 1 weight (0.35** of AAII 30 / NAAIM 35 / Put-Call 20 / CNN 15). Without it Layer 1 renormalises to AAII 46.2 / Put-Call 30.8 / CNN 23.1.

**Also worth knowing:** the "NAAIM 79.7%" quoted back in rows 37 and 48 is this same frozen value. It was already the final print when those rows were written — it just sat inside the staleness cap, so nothing flagged it.

### The three options

| | Option | Cost | Time to restore | Risk |
|---|---|---|---|---|
| **(a)** | **NAAIM membership** | **~$300/yr** per individual, **~$600/yr** per firm (up to 5 people), or **$750** group rate for up to 5. Exposure Index access is listed as **included** in all member tiers. | Days — application needs Board approval for "Special Member"; Regular Member is the fast path | Membership terms may restrict redistribution. We display a derived z-score, not the raw series, which helps, but I would want that in writing before we publish it |
| **(b)** | **Manual weekly entry** of the Wednesday print | ~2 min/week of someone's time. Zero cash. | Immediate | Needs a member (or a public quote) to *have* the number — if the index is now members-only, (b) collapses into (a). A missed week silently ages the input |
| **(c)** | **Re-spec Layer 1 to three signals** with new weights | Zero cash, ~half a day of work + a backtest re-run | Immediate | **Changes the definition of the score.** Every historical Layer 1 value becomes non-comparable to the new one unless we rebuild history. Needs your sign-off, and needs disclosure on the page |

**My recommendation: (a), and (b) as the bridge.** $300–600/yr is noise against the cost of the largest Layer 1 input being permanently dead, and (a) is the only option that keeps the score definition intact. Take (c) only if you want Layer 1 to be a three-signal index by design rather than by accident.

**What I already shipped so nothing lies in the meantime:** a layer coverage gate — below a minimum input count/weight the layer is marked UNRELIABLE, its score suppressed, and the SSI size multiplier held neutral at 1.00 instead of 0.80/1.20. Layer 1 at 3-of-4 with 65% of nominal weight is above that floor, so it still scores, and the page reads "Running on 3 of 4 signals — weights renormalised" with NAAIM flagged amber and dated. A `manual` source tag exists in the cache, unused, reserved for option (b).

I also repaired the scraper itself while I was in there — it was parsing for a column name that never matched and returned 0 rows; it now returns 131. That fixes a real bug but does **not** fix freshness, because the source it reaches is the frozen one.

**The one thing I need from you:** ask NAAIM directly whether membership includes the right to display a derived index on a commercial site. I do not want to pay and then find we cannot show it.

---

## 4. The four chased items — honest status

The pattern here is the same in all four: **the work is done and written up; the reply never left.** That is on me, and it is a process fix, not a work fix.

| Item | Real status | What I owe you |
|---|---|---|
| **4 prompt-v3 questions** (11 Aug, chased 17 Aug "kindly reply") | **Answered against live code on 20 Aug**, and one divergence found and fixed. Q2: composite is a single float, sub-scores never emitted, `cagr_score` does not exist. Q3: code implements **v4** (C1 E[R] 40 / C2 alpha 25 / C3 Sharpe 20 / C4 CAGR_diff 10), not the 3-component v3 the MasterSpec text says. **Q4: DIVERGED — fixed.** Shorts had `signal_alpha = er` with no benchmark subtracted; `compute_random_window_return()` now takes direction and mirrors the baseline. Q4b audit: no stray 0/IRX uses outside the four allowed. Q5: **both** Gate A2 forms are live simultaneously. | The reply mail. Plus **my own 4 open items back to you** from §3 of the addendum: (1) case 1's "below threshold" — I shipped `conviction_bq_score < +2`; (2) case 2's `≥ +8` — `bq_raw` and `conviction_score` are different scales (`bq_raw` −5…+14 median 8.5; `conviction_score` −12…+10 median 4.0), `≥+8` on `bq_raw` qualifies ~53% of rows; (3) "borderline composite" shipped as the 30–40 band; (4) `TACTICAL_FEARFUL`/`STRATEGIC_BULLISH` exist nowhere in the code — I mapped them to the five real values `_brave_fearful()` emits. |
| **Runic/audit CRITICAL rows** ("all 80 Not Started") | **The 80 rows are sheet rows 62–141** — that is exactly 80, so we are looking at the same block. Your copy showing all Not Started is a **sheet hygiene failure, not a work failure.** Actual sheet state: 20 Completed, 9 In progress, 11 Waiting for input, 16 Not Started, **24 with a blank status cell** — and only 13 of the 80 carry my reply. The repo job-status log shows materially more done than the sheet admits. | I fill in all 80 status cells against the repo log before the call, or immediately after. Note there is exactly **one** row tagged `[RUNIC CRITICAL]` — row 90, VIX BYPASS on the nightly brief / 12 variables page, `Waiting for input`. The rest of the 80 are SSI/CFTC/MasterSpec/Addendum tagged. If you meant 80 *Runic* rows specifically, we are looking at different documents and I need yours. |
| **6 Aug regime doubts** | **Answered in full on 17 Aug** — `docs/rohit_6aug_answers_2026-08-17.md`. Headlines: the stored table is `macro_regime_log_v2`, 1,901 Friday evaluations 1990→2026; states are **stored**, multipliers are **recomputed on every read**, which is the one place "the stored table is the source of truth" is not literally true today. Your Axiom-2 example (85% × 1.20 × 1.20 = 104%) **cannot happen** — two independent clamps, `min(1.0, ssi_multiplier)` and `min(100, ceiling)`; both ×1.20 terms are dead on the upside. The 20-date test you asked for exists: `tests/test_regime_source_of_truth.py`, fixed dates, API vs export vs direct table read agree field-for-field. | Send the doc. It has been sitting in the repo for a week. |
| **Website refresh timing** (20 Aug) | **Answered by §1 above.** Public site last built **18 Aug 07:23 UTC** and is 23 commits behind. It refreshes when Parth rebuilds and restarts — not on my deploy. | A date from Parth, which is item 6. |
| **Chatbot** | Verification sweep passed **18/18 checks, 71/71 MTM**. Router guardrail (`apply_internal_level_override`, resistance rule) went to prod in the 20 Aug merge. Known open gap: macro questions can still route to the web and contradict Runic — the word "combo" is MindWealth-only vocabulary and still did not force an internal route. Needs a wording rule **and** a Runic feed the chatbot does not currently have. | Tell you which of those two you want first. |

---

## 5. 2003 COT rebuild — GO. Here is what it actually costs you

Taking it as a decision, not a question. One thing you should know before I spend the time, because it changes what the output means:

**The legacy series is already built** — legacy COT non-commercial S&P 500 net, **417 weekly prints, 2003-01-07 → 2010-12-28**, cached beside the TFF files. What the overlap says:

| Measure | Value |
|---|---|
| Overlap | 2006-06-13 → 2010-12-28 (238 weeks) |
| Level correlation | 0.641 |
| Weekly-change correlation | 0.572 |
| Percentile correlation | 0.540 |
| Mean absolute percentile difference | **23.1 points** |
| Agreement on FM<10 weeks | **22 of 47** (Jaccard 0.47) |
| Means | legacy −2,961 vs TFF −43,191 contracts |

**Non-commercial ≠ leveraged money.** Roughly half the extreme weeks disagree and the two series sit at completely different levels. Stitching them moves grid cells for reasons that have nothing to do with the market.

**So my plan, unless you say otherwise on the call:** run it **both ways** and hand you both.

1. **Spliced series** (2003→2026, percentile-normalised per segment to blunt the level break) — this is your GO, delivered.
2. **TFF-only** (2006→2026) — unchanged control.
3. Both grids re-run on both: **SQUEEZE** and **LIQUIDITY EXIT**, same reporting spec as 11 Aug — episode collapse, mean−median gap ranking, PAR row, excess over market, dated episodes.
4. A diff table showing which cells changed and by how much, so you can see whether 2003–06 is telling you something or just adding level noise.

If the spliced grids and the TFF grids disagree on the recommended cut, **the disagreement is the finding** and we should not ship either until we understand it.

**Also in scope for the same re-run** (both are stale for the same reason — they predate the 20 Aug data fixes): the **row 53 FM sweep** and the **row 54 Layer 2 grid**. If I am re-running grids anyway, those two should come along, so you make all four picks off one consistent sample.

**Estimate: 2–3 days** for all of it including the write-up.

**One decision I still want from you inside this** (row 42): the event-gated table says the **old LIQUIDITY EXIT cut RM<30 & FM>60 is genuinely bearish around CPI/NFP/FOMC** — 8 episodes, 12-week mean **−3.00%**, excess **−5.31%**, hit 37.5% — while the FM≥80-only placeholder you told me to ship is much weaker (excess −1.58%). So **RM earns its place in LIQUIDITY EXIT even though it does not in SQUEEZE.** Say the word and RM<30 goes back on that flag only. That is a one-line CONFIG change.

**Correction I owe you on the record:** the earlier reports said the rolling grids excluded Sep 2008 – May 2009. That was wrong — hard-coded boilerplate, not the filter actually applied. Percentile cells run continuously from 2006-10-24 and the 2008 episodes **are** in the grids; they are the largest negatives in the LIQ EXIT cells. The real caveat is narrower: 2008 ranks against a partial ~115-week lookback rather than a full 3-year window. Wording is corrected in the 20 Aug report.

---

## 6. Parth — the chase list, with evidence attached

Chasing him directly, not through you. Every one of these is the same root cause, and I want to lead with that rather than six separate nags:

> **The public Nuxt tree has not been rebuilt since 18 Aug and is 23 commits behind `ui-dev`.** It has no `components/sentiment/` at all.

| # | Item | Where it stands |
|---|---|---|
| 1 | **Conviction engine v2** on the display | Backend done — 22 items, `bank` + `high_margin_hardware` business types, `COVERAGE INCOMPLETE` third hard gate, rebuilt `fs_score_breakdown()`, 112 tests pass. `fs_cap_breakdown` / `yield_trap_breakdown` exposed on every record for his Engine Layers click-through. **UI side is his.** |
| 2 | **D/E amended thresholds** on the display | No `D/E` or `debt_to_equity` string anywhere in the Nuxt tree — dev or prod. **Not started on the UI.** Needs him to confirm he has the field from the API. |
| 3 | **Portfolio page date** | `PortfolioOverviewView.vue` exists on dev, **absent from the prod tree**. Blocked on the rebuild. |
| 4 | **NH/(NH+NL) label** | Fixed on dev 17 Aug — dev reads `NH Share (NH/(NH+NL))`, prod still reads `NH/NL Ratio`. Pure deploy gap. |
| 5 | **A–F legibility** on the Macro Runic page (sheet row 19, `Not Started Yet`) | Genuinely not started by anyone. Contrast/weight change on `pages/macro.vue`. Small, his side, and it has been open a while. |
| 6 | **Nuxt date bug** | UTC-safe `formatSignalDate` is on dev; prod `GET :8512/api/meta` still returns `2026-08-14T00:00:00Z`, so the site keeps showing the wrong last-updated stamp until `systemctl restart mindwealth-ui`. |

**What I'm asking him for:** a rebuild date for `/home/ubuntu/MindwealthUI_Vue_prod`, and owners on #2 and #5.

**Separate, and I need your call because it is not mine to fix unilaterally:** `.env` containing `NUXT_API_BASE_URL` and `NUXT_API_KEY` is **committed to git and published on a public repo** (`origin/ui-dev`, `private: false`) via Parth's commit `f99e9d4`. The dev API key is publicly readable and stays in history even if the file is deleted. Fix is rotate the key, `.gitignore` + `git rm --cached`, then purge history with `filter-repo`/BFG and force-push in coordination with him. **No remediation done — waiting on your go-ahead**, because a force-push on his repo needs to be agreed, not sprung.

---

## What I want to walk away from the call with

1. **Merge date confirmed** (proposing Tue 26 Aug) — and your acknowledgement that prod numbers will move when the CFTC history fix lands.
2. **Row 53:** FM cut — I recommend 20, on a re-run sample.
3. **Row 54:** Layer 2 — I recommend demoting to sizing overlay, or 0.5/3 if it stays a gate.
4. **Row 42:** RM back onto LIQUIDITY EXIT only — yes/no.
5. **Row 142 / NAAIM:** (a), (b) or (c) — I recommend (a) at ~$300–600/yr with (b) as the bridge.
6. **Runic 80:** confirm rows 62–141 is the block you mean, or send me yours.
7. **Public-repo API key:** go-ahead to rotate and purge.
8. **Process fix from me:** the four chased items were all *done and unsent*. I will send the write-up the same day the work lands, not batch it.

---

**Sources for the NAAIM pricing:** [NAAIM — Join](https://naaim.org/join-naaim/), [NAAIM — Membership Benefits](https://naaim.org/join-naaim/membership-benefits/). The page renders dues without a decimal separator (`$30000`, `$60000`); read against the `$750 group discount for up to 5 individuals` line these are **$300.00** and **$600.00**. I will confirm in writing with NAAIM before we commit.
