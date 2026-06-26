1. COMBOS D AND E — FIX THRESHOLDS

The per-fire backtest data shows both combos need threshold tightening:

Combo D (FOMO Top) — 435 triggers, 2010–2026:
  Bear hit rate: 1W=39.6%, 2W=37.8%, 3W=35.6%, 4W=35.2%, 1M=35.3%, 2M=31.7%

Combo E (Valuation Extreme) — 484 triggers, 2010–2026:
  Bear hit rate: 1M=30.4%, 2M=26.0%, 3M=21.5%, 6M=22.0%, 9M=19.6%, 12M=20.5%

Both are below 40% bear hit rate at every horizon — predicting bullish outcomes more than bearish. 435 and 484 triggers in 15 years means firing roughly every 2–3 weeks. These should be rare extremes.

TO TEST (Divyanshu and/or Ahil):
- Significantly tighten thresholds for both D and E to reduce instance count to roughly 20–40 total (comparable to Combo B ~8 fires and Combo F ~16 fires)
- Re-run bear hit rate analysis on the tightened set
- Target: bear hit rate above 80% at the relevant horizon (D = tactical 1–4 weeks; E = structural 6–12 months)
- Test D alone, E alone, D+E in sync
- Overlay yield curve regime — does D+E in STEEPENING produce better hit rates than in NORMAL?
- Fewer high-quality instances beats many low-quality ones
- Report back: new thresholds, instance count, bear hit rate per horizon

Note: D and E are combos, not standalone variable signals.
