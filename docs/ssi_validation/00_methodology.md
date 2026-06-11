# SSI validation methodology

## Threshold origins (Part 1)

Most SSI and Layer 2 cutoffs in `macro_intelligence/SSI_CONFIG.yaml` were set by design intent (e.g. long gate ≈ 20th percentile of 5-year SSI distribution), not by formal optimization on full history. This suite empirically tests those choices.

**Primary long/short gates for production** (after validation):

- `long_entry_pctile` / `short_entry_pctile` on 5-year SSI history (Tests 1–2)
- Raw `long_entry` / `short_entry` level retained for comparison

## Z-score vs percentile (Part 1.2)

Production composite in `ssi_score.py` uses z-scores on inputs. Test 9 builds a **parallel** 3-year rolling percentile composite. Do not switch production until `SIGNOFF.md` records Rohit approval.

## Overlap with Runic (Part 8)

- HY OAS → Runic only; HYG/LQD ratio → SSI only
- VIX term structure → Runic combos; SSI uses VIX ratio in composite only
- CNN F&G → SSI Layer 1/2 → `ssi_multiplier` in Runic JSON
