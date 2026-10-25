# Conviction Engine + Conviction page — master to-do list (2026-10-25)

Compiled read-only from: memory layer + hubs + job status + dev→prod todos + Sep close-out reports,
every Rohit mail 1 May → 25 Oct 2026, and every row of the `mindwealth todos` sheet
(`v2_TODOs`, `wtssp replies` = WhatsApp tracker, `macro_tasks`, `ssi`).

No conviction-specific Rohit mail after 24 Sep. Latest touch: 21 Oct HY mail — Ahil to later assess
"the improved (to be done by Divyanshu) Conviction engine".

**Sheet column:** `—` = not on any tab · `v2 N` = `v2_TODOs` row N · `wa N` = `wtssp replies` row N · `partial` = row exists but misses part of the ask.

Status keys: NS not started · IP in progress · DEV done on dev, prod pending · R blocked on Rohit · A blocked on Ahil · OPS needs human/ops (agent may not write prod data).

## A. Rohit decided, code not done (engine)

| id | task | status | owner | source | sheet |
|---|---|---|---|---|---|
| CE-01 | Persist SBUX "mature/transitioning compounder" override before any recalc (auto-rule would flip it to income) | NS | Divyanshu | mail 24 Sep `1a0d2e58` ("ok"); job_status TODO CE#1 | — |
| CE-02 | P/E confidence bands: 20y+ full, 10–20y provisional, <10y neutral; show depth + source on page (audit still says strict-20y pending, `api/services/conviction_service.py:428`) | NS | Divyanshu | mail 21/24 Sep; CE hub ledger | partial (v2 6 low-data tax Q — this answers it) |
| CE-03 | Dividend ingest: classify specials in pipeline (2-of-3 gate: retrieval, type word, amount outlier); attribute to declared period; frequency as history; start/end-of-year handling; list of names whose frequency changed in 5y | NS | Divyanshu | mail 1 Sep C2; 24 Sep A1 | — |
| CE-04 | Dividend-cut penalty: show verified diff, then switch `apply_dividend_cut_penalty` on globally; policy_reset half-penalty unless coverage worsens / leverage rises | NS (waits CE-03) | Divyanshu → Rohit | mail 1 Sep C3; 24 Sep | — |
| CE-05 | Reclassify SFTBY (venture/holding co, not telco) | NS | Divyanshu | mail 24 Sep | — |
| CE-06 | Mixed-business tie-break by dominant operating segment (+ documented overrides); continuous margin-normalised EV/Rev, no bucket gate | NS | Divyanshu | mail 1 Sep E2; 21/24 Sep | — |
| CE-07 | Telco/utility stay COVERAGE INCOMPLETE (CNU.NZ, T.TO, SPK.NZ, BIPC.TO) until Rohit's framework; fix short polarity (CNU.NZ SHORT −5 → "CANCEL") | NS | Divyanshu | WA 28 Sep; mail 24 Sep | wa 46 |
| CE-08 | Claude override cases 1 & 2 repoint to `conviction_score` (+2/+8 from sell ladder); widen tier field; list unrunnable cases | NS | Divyanshu | mail 14 Sep | partial (v2 103) |
| CE-09 | Claude payload: add `conviction_bq_score`(bq_raw), `conviction_fs_class`, `coverage_incomplete` to `_load_conviction_lookup` (send_email.py:145-155); clean prompt merge after Ahil sign-off | NS / A | Divyanshu, Ahil | mail 26 Aug; WA 14/21 Sep | v2 94, 100, 110, 116; wa 22 |
| CE-10 | Payload: add `market_cap`, `pe_ratio`, `fundamental_anomaly_flag` (P/E <5 or >80, negative book, implausible NI/revenue) | NS | Divyanshu | mail 26 Aug SQS G1(a) | — |
| CE-11 | Prod report-only guard (no 75/40/0% sizing, no "BUY cancelled regardless"); header v5→v6; explain/remove "15 dims · 7 auto + 8 manual" | NS | Divyanshu, Parth | WA 28 Sep; mail 26 Aug decision | wa 45 |
| CE-12 | FX / ETF / commodity conviction → "not applicable → base size", never BLOCKED → $0 | NS (verify) | Divyanshu | mail 10 Jul, 15 Jul D2, 21 Jul | — |
| CE-13 | Compounder valuation: explain IBKR cap at +4 / no compounder module; BDGI.TO inconsistent message | NS | Divyanshu | WA 21 Sep | wa 39 |

## B. Data, adjusted EPS, P/E sources

| id | task | status | owner | source | sheet |
|---|---|---|---|---|---|
| CE-14 | Adjusted EPS B1–B4 + `adjusted_eps_source`; SPK 11.9c / 18.4x; >20% unidentified NI → size cap (not score); which path made GOOGL's number | DEV? (WA 7 Sep says B1–B4 + SPK done) — verify + reply | Divyanshu | mail 1 Sep B | — |
| CE-15 | G1: full-universe CSV (`pe_ttm`, `pe_ttm_adjusted`, `adjusted_eps_basis`, `adjusted_eps_source`, `one_off_review_needed`) | NS | Divyanshu | mail 1 Sep G1 | — |
| CE-16 | G2: missing statement fails loudly + empty-fields report per name at last recalc (also answer "empty statement / bug / ASX" inline Qs) | NS | Divyanshu | mail 1 Sep G2 | — |
| CE-17 | Deal-delay tax only when EV/forward revenue ≥ 4x | NS (verify) | Divyanshu | mail 1 Sep C5 | — |
| CE-18 | Say which hardware threshold is in code; answer "debt purpose classification" origin (his 24 May v5 brief Part 4) | NS | Divyanshu | mail 1 Sep A | — |
| CE-19 | E3 Gartner/G2 search-then-fetch, no G2 for hardware/semis; E4 GOOGL buyback-suspension trigger; E5 `supply_constraint_flag` | NS (verify) | Divyanshu | mail 1 Sep E3–E5 | — |
| CE-20 | E6: business_type pass over full universe; engine vs Google Sheet ticker list | NS | Divyanshu | mail 1 Sep E6 | — |
| CE-21 | F: correct Section 5.7 | NS | Divyanshu | mail 1 Sep F | — |
| CE-22 | SONY bare ticker on US path (`is_us_ticker`); store issuer domicile separately from suffix | NS | Divyanshu | job_status PE-01a; E2E audit 21 Sep | — |
| CE-23 | Paid data: EODHD/FMP commercial terms + samples, dividends and P/E tested separately; PE-02 FMP key; PE-03 manual non-US list; PE-05 CAD/USD (TRI.TO/BN.TO); PE-06 India; PE-07 NZ | NS / R | Divyanshu, Rohit | mail 1/21/24 Sep; job_status PE-02..07 | partial (v2 7, wa 35) |
| CE-24 | `ceo_start_date` from SEC DEF14A; non-US CEO tenure via Tavily (research only) | NS | Divyanshu | ssi hub OQ2; decisions doc | — |
| CE-25 | Insurer + deep-value valuation modules | deferred | — | conviction_fixes_decisions.md:293 | — |

## C. Recalc, tests, research

| id | task | status | owner | source | sheet |
|---|---|---|---|---|---|
| CE-26 | Full dev recalc after CE-01..04 (purge `pe_history_cache/*_sec.json`), diff all 198 records, verify API + page; G3 list of changes to Rohit before prod | NS (dev store last full calc 27 Aug) | Divyanshu | job_status CE#5; mail 1 Sep G3; WA 21 Sep | wa 23 |
| CE-27 | Ahil live test on dev 8507/8514 with correct engine (BQ raw, valuation tax, FS); "does engine add value?" | A (waits CE-26) | Ahil, Divyanshu | mail 10 Sep, 24 Sep; call 16 Oct | partial (wa 45 mention) |
| CE-28 | NVDA/GOOGL two-name agent model comparison, hard $5 cap, request-only; first replace retired default model id (`agent_dims.py:19`) | NS | Divyanshu | mail 24 Sep | — |
| CE-29 | Point-in-time S&P 500 BQ replay (current + bear market) → HARD/FULL EXIT merge recommendation; conviction on SELL stays non-binding until then | NS | Divyanshu | mail 21/24 Sep | — |
| CE-30 | Calibrate sell ladder (cut points assume BQ values engine can't produce) | deferred | Divyanshu | job_status 2026-09-02 | — |
| CE-31 | Real SSI-ceiling + conviction-tier feed for Ahil's four-book attribution ("Date please") | NS (verify) | Divyanshu | mail 21 Jul; chased 6 & 22 Aug | — |
| CE-32 | Is sizing live or placeholder; does BQ duplicate composite_score v4 | NS (likely stale) | Divyanshu | mail 10 Jul item 6 | — |

## D. Conviction page (frontend)

| id | task | status | owner | source | sheet |
|---|---|---|---|---|---|
| CE-33 | Any-ticker input on Conviction page → score + systematic breakdown | NS | Divyanshu (API), Parth (UI) | mail 24 Sep | — |
| CE-34 | COVERAGE INCOMPLETE verdict label/colour in conviction panels | NS | Parth | v2 5; decisions doc | partial (v2 5) |
| CE-35 | Held positions: MTM "—", FD "→ sta" every row; which portfolio is "held" | NS | Divyanshu, Parth | WA 28 Sep | wa 47 |
| CE-36 | "degrading" despite fwd WR 75%; left tabs blank; Layer 2 not clickable (verify on 8514) | NS | Divyanshu, Parth | WA 22 Sep | wa 28 |
| CE-37 | Yield-trap panel fired vs watching; Engine Layers click-through (valuation tax / FS cap / yield trap; `fs_cap_breakdown` unused) | NS | Parth | decisions doc :297, :300 | — |
| CE-38 | Section 6 nav: signal-row "BQ drill" → drawer BQ tab; "FS page →" | partial | Parth | ssi hub OQ1 | — |
| CE-39 | Portfolio positions + Contradictions tabs wired to backend | NS (verify) | Parth, Divyanshu | mail 21 Jul Part 7 | — |
| CE-40 | Conviction page timestamp alignment live on prod (Parth build) | DEV | Parth / ops | v2 2, 14; migration :2421 | v2 2, 14 |

## E. Replies owed to Rohit

| id | task | status | owner | source | sheet |
|---|---|---|---|---|---|
| CE-41 | Answer 24 Sep clarifications: "across the store"; 55 below +2 = BQ or conviction; model-reported vs starting confidence; evidence text source; 0–10 assessment; caps origin (his 24 May brief); 144 set / non-equity / usable payment history; 136 computable?; 27 income names; "bear market replay"; 5.2 on call | NS | Divyanshu | mail 24 Sep | — |
| CE-42 | Answer 14 Sep: prod merge date, blockers, which live numbers not to trust; MCY + SPK FS slice breakdowns | NS | Divyanshu | mail 14 Sep | — |
| CE-43 | 1 Sep inline: "I DONT UNDERSTAND THIS COMMENT" (prod recalc); tag Ahil on parked payload field definitions; write definitions against current site not Streamlit | NS | Divyanshu | mail 1 Sep | — |
| CE-44 | Cross-system status reply (12–13 Sep) + 17 Sep "all conviction issues on website" + all-pages review call | IP | Divyanshu | WA 12–17 Sep | wa 18, 38 |
| CE-45 | Chase Parth: 29–30 Jul conviction fixes visible on website | IP | Parth | mail 17 Aug | partial (v2 5) |

## F. Prod promotion and hygiene

| id | task | status | owner | source | sheet |
|---|---|---|---|---|---|
| CE-46 | Prod full conviction recalc by ops (PE-01b + all later fixes). Prod PYPL still `pe_percentile_20y=83.33`, `valuation_tax=-3.0`, `last_full_recalc=None` | OPS | ops | migration :1687, :2566, :2622, :2669, :3101 | — |
| CE-47 | Promote dev conviction code: 27 Aug adj-EPS/dividend cadence (`29fff0c61`, API 1.14), 2 Sep `2a804c709` (no migration block yet), 17/19/22 Sep gates + audit API 1.16/1.17, MW-016/017/019/020/043, Nuxt shortlist tier `9235f1c` | DEV | Divyanshu → ops, Parth | migration :375, :413, :464, :780, :804, MW blocks | partial (v2 5, 7) |
| CE-48 | GitHub credentials (`divsum127` PAT reported invalid) — 25+ unpushed `chatbot-dev` commits block promotion (verify) | OPS | Divyanshu | migration MW blocks | — |
| CE-49 | Commit untracked `reports/conviction_engine_closeout_2026-09-17/` + `followup_2026-09-21/`; write migration block for `2a804c709` | NS | Divyanshu | git status; job_status :727 | — |
| CE-50 | Memory hygiene: CE hub open questions/ledger after 24 Sep; asset map stale (3 Sep); July migration blocks say "merge pending" though code on prod since 20 Aug | NS | Divyanshu | agent audit 25 Oct | — |
| CE-51 | Status unclear, verify before tracking: M&A feature flag (`ma_activity` + weekly cron), KXS.TO/MSFT manual audit, Earnings-call LLM module, v5 brief Part 8 Qs | verify | Divyanshu | mail 9/24 May, 20 Jul | — |

## Owed to us
- Rohit: telco/regulated-utility framework; PE-03 priority non-US ticker list; India/NZ source + paid-provider approval; conviction-on-SELL after CE-29.
- Ahil: "does engine add value" (CE-27); qualification-design set (252/365, R_REF/clips, E[R] floors, Tier-A cut, hard vs flag gates).

## Sheet coverage summary
- On sheet (full): CE-07, CE-09, CE-11, CE-13, CE-26, CE-35, CE-36, CE-40, CE-44 (9).
- Partial: CE-02, CE-08, CE-23, CE-27, CE-34, CE-45, CE-47 (7).
- Not on sheet: 35 items.
- Stale sheet statuses: v2 6 "Not Started Yet" (low-data tax now answered by P/E bands); v2 7 status blank; wa 22/23 no reply sent; wa 28/39/45/46/47 no reply.
