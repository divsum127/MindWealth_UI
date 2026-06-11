## Macro report fix suggestions

1. Combo E hit rate shown as 19.9%. This is probably a logic inversion bug.
Combo E is a BEARISH combo. The hit rate should be measured as the percentage of fires where SPX was NEGATIVE at the target horizon. The system appears to be computing it as % of fires where SPX was POSITIVE. Thus i guess you need to label the combos as bullish or bearish to be fair to you - i shd have speccd that clearly
    
    Hit rate computation for bearish combos = fraction of fires where spx_3m < 0.
    
2. 2nd point re pdf> Combo C shows INACTIVE but no CANCELLED status.
As of our last confirmed reading (May 26), I THINK Combo C was ACTIVE week 11 MEDIUM? — WTI is now at −5.11% 4-week change. If the cancellation clock has been running for 4 consecutive Fridays with delta(WTI) below +5%, Combo C should show CANCELLED (with the date it cancelled), not just INACTIVE. INACTIVE implies it never fired recently. The briefing needs a distinct CANCELLED state with the cancel date stored. This is different from INACTIVE.  
3. 3rd point re v2 pdf > in the second header  Combo F active (week 10, MEDIUM). looks good/may be helpful if we specify week 10 start date as i am not sure whether week 10 is over or being looked at as Monday next week being week 10 start
4. 4> Combo F Recovery dominates the tactical picture, active for 10 weeks in MEDIUM duration with a commanding 75%
three-month hit rate versus Combo E's dismal 20% accuracy.—> naturally noting point 2> this “dismal” 20% will change… is this being done by claude api or have you speccd some language for this and is python doing it? In that context, suggest we dont use words like commanding. Perhaps just say “… with 75% 3-month hit rate….” use 3 as a number instead of three as alphabets. More pro and harder for our eye to miss.
5. 5>Big Error 🙂 -  How is E confirmed? - it needs 80th percentile for cftc . page 3 table reading for cftc shows 5th percentil…
6. Potential big error: WALCL showing 85th percentile at 0.03% MoM.
A near-zero MoM% change on WALCL (0.03%) should be around the 50th percentile?, not the 85th. PER CLAUDE ——>>>> The 85th percentile of WALCL MoM% historically corresponds to approximately +0.5–0.8% (active QE i e Quantitative Easing). Perhaps the percentile is being computed for the wrong distribution? Eg absolute level rather than MoM%, Please advise how WALCL percentile is computed?
7. 7> Please change BRAVE to EASY MONEY/BULLISH . I meant to communicate this in my earlier email but probably forgot. Brave means something one does when there is a challenge not when there is easy money/euphoria… While ITS VERY HARD TO DO, I would prefer to be brave when others are fearful :). Through this process I also hope to communicate some subtleties of cross asset rate markets to you… this is invaluable experience for you and will help you later in life for jobs etc…
8. 8> can you clarify the source of the cftc number.
9. Use the combo's own validated horizon, not a uniform 3m. The PDF showing "3M Hit Rate" on page 1 for all combos is wrong for several of the combos:
    
    Combo E: horizon 6–18m (YOU SHOULD VALIDATE THIS as per the email i sent). Use 12m. The 3m hit rate for E is near meaningless — E is a slow structural signal that does not predict short-term moves. Measuring E at 3m gives misleading results.
    Combo C: horizon 1–6m. (Same comment)  Use 6m as primary, 3m as secondary.
    Combo D: horizon 3–10 days.(same comment) Use 5 days.
    Combo G: not a return predictor — a timing warning. No return hit rate.
    Combo B: horizon 3m. (same comment) 3m is correct.
    Combo F: horizon 3–6m. (same comment) Use 6m as primary.
    
    The "validated horizons" came from:
    
    Combo B 3m — the 8 confirmed instances since 1990 were measured at 3m in the i3 Invest data I had shared with you in the past and per some institutional research frameworks I asked Claude to reference. This one has the most external backing.
    Combo F 6m — the 16 instances with +9.46% avg came from the i3 Invest table. The 6m measurement was in that source. That is a real external reference.
    Combo C CORRECTION TO MY ABOVE WHATD APP MESSAGE 1–6m — duration-tracked. The 1–6m range is the spec definition, not a statistically derived optimal. It reflects how long energy shocks typically transmit to the economy, which is economic reasoning not empirical optimization. I will address this separately below as its not a 1 maturity fits all shoe…
    Combo E 6–18m QUALIFICAITON TO WHAT I WHATS APPED EARLIER/..— This is a bit complex as each leg of this 3-legged combo has different dynamics… eg CAPE-based overvaluation signals historically take a long time to resolve. The 6–18m range is what macro research desks typically use for valuation-based signals. It was not derived by sweeping horizons on the 3–4 historical instances.
    Combo D 3–10 days — derived from the definition of FOMO tactical short horizon. Not empirically tested on the 4–5 instances.
    Combo G — explicitly marked as a leading indicator, not a return predictor. No horizon claimed.
    
10. q for you - so really uyou need to start testintg. alot of the stuff mentioned in my email and subsequent whats app…
    
    The pre-2007 B instances (3 of the 8) are tricky to test for G because the 3m VIX data does not exist prior to 2007
    
    **Runic Agent Na…Combos v2.pdf**
    
    15 KB ·
    
    for now note in the Briefing note —> Combo G testable from 2007 only
    
    also note dates of G firing,B firing, and spx bottom date...
    
    Test the actual elapsed time between G fire and B fire in each confirmed instance and let the data set the window. From the known instances:
    
    Pre-Aug 2015: G fired approximately 3 weeks before B
    Pre-Dec 2018: G fired approximately 4 weeks before B
    Pre-COVID Feb 2020: G fired approximately 3 weeks before B
    Apr 2025: G fired, B never formally completed
    
    Of the 5 post-2007 B instances, how many were preceded by a G fire within 6 weeks? If the answer is all 5, then G is a perfect early warning for B within the testable period. If some were not preceded by G, those are B fires without warning — useful to know because they represent the scenario where capitulation arrives without the credit-vol divergence signal building first (sudden shock rather than slow stress buildup).
    
    Note the historical instances columns - wrt what i have been saying eaerlier
    
    ACTION: Check every confirmed Combo B fire date — what was the actual HY OAS reading on that date? If any instance had HY between 375–400bps, the 400 threshold is too high and needs lowering. If all instances had HY well above 400bps, the threshold is fine. Also confirm the DUAL condition is implemented: HY must exceed BOTH the 400bps absolute floor AND the 80th percentile of its full expanding history (from 1996, FRED BAMLH0A0HYM2 inception) simultaneously. Do NOT use a 3-year rolling window for HY percentile rank — HY is a structural credit variable and must be benchmarked against its full long-run distribution, not the recent regime.
    
    Note the key note special rules column and row G of that
    
11. I have already talked about the combo C cancel condition. page 2 of this document swells on that in detail.
this supercedes the pdf combo C cancel condiiton pn page 2
these small things make all the difference to accuracy. so have spent lot of time thinking abt it
Divyanshu — two corrections to Combo C logic:
    
    FIRE CONDITION ERROR IN THE PDF: The fire condition should read CPI actual > consensus by ≥+0.2pp (HOT surprise). The PDF incorrectly shows CPI actual ≤ consensus in the fire row — that belongs only in the cancel logic. I think i pointed this out subsequently via whats app. Either way, please fix it.
    CANCEL LOGIC — CPI LEG CLARIFICATION:
    The CPI leg of the cancel condition works as follows:
    — On each Friday, check the most recent confirmed CPI print available (regardless of when it was published)
    — If that print shows actual ≤ consensus: CPI leg PASSES
    — If that print shows actual > consensus: CPI leg BLOCKED
    — If BLS is delayed or shutdown: the most recent confirmed print before the disruption remains the governing reading. No special handling needed — just use whatever the last confirmed print was
    — CPI leg status updates automatically the moment a new print is published and confirmed
    So the only two states are PASSES or BLOCKED. No pending flags, no clock pausing. The WTI 4-consecutive-Friday counter runs independently and resets to zero any Friday where either leg fails
    — PPI is NOT a substitute for CPI in the cancel logic. Remove PPI fallback entirely. PPI stored separately as ppi_cooling (true/false) for narrative context only