# Layer 2 confirm-driver display — UI spec for Parth

**From:** Divyanshu  
**Repo:** `MindwealthUI_Vue`  
**Backend:** ready (no API changes needed)  
**Date:** 2026-08-04

## Problem

Layer 2 rows show **raw** values for all 6 inputs, but ✓/✗ badges use **different logic** per input. Users read small decimals (0.57, 0.75) as z-scores and large prints (−5.96, 141.23, 67.9%) as unrelated raw data. Backend is correct; fix is display only.

## API (single source)

**Endpoint:** `GET /api/v1/analytics/sentiment/layers`  
**Dev:** `http://<host>:8507/api/v1/analytics/sentiment/layers`  
**Prod:** `http://<host>:8506/api/v1/analytics/sentiment/layers`  
**Auth:** `X-API-Key` header (same as other analytics routes)

Nuxt BFF should proxy this endpoint unchanged. Existing Sentiment page loader (`loadSentiment()` / `mapSentimentLayers()`) already hits it.

**Do not** call `GET /macro/ssi/summary` for this panel — it lacks per-row gate detail.

### Top-level fields for panel header

| JSON path | Use |
|-----------|-----|
| `layer2_gate_label` | Panel subtitle, e.g. `L2: 3 long / 0 short of 6 - long confirmed` |
| `layer2_gate_direction` | `LONG_CONFIRMED` \| `SHORT_CONFIRMED` \| `CONTESTED` \| `UNCONFIRMED` |
| `layer2_gate_confirmed_count` | Active votes (0–6) |
| `layer2_gate_conf_long` | Long-side active count |
| `layer2_gate_conf_short` | Short-side active count |

Same fields also exist under `positioning.inputs.*` and `positioning.layer2_gate_*` after `run_ssi_daily.py`. Prefer **top-level aliases** (API enriches stale `positioning.json`).

### Per-row data — join by `input` key

Build a map from `layer2_gate_votes` (or `positioning.inputs.layer2_gate_votes`):

```ts
const gateByKey = Object.fromEntries(
  (body.layer2_gate_votes ?? []).map((g) => [g.input, g])
);
```

| Row key (`input`) | Display label | Main value (raw) | Confirm driver sub-label |
|-------------------|---------------|------------------|--------------------------|
| `mcclellan` | McClellan Oscillator | `positioning.inputs.layer2.mcclellan` | `gate.norm` → z-gate |
| `nh_nl_ratio` | NH Share (NH/(NH+NL)) | `positioning.inputs.layer2.nh_nl_ratio` | `gate.norm` → z-gate |
| `hyg_lqd` | HYG/LQD | `positioning.inputs.layer2.hyg_lqd` | `gate.pctile` + `gate.signal` → legacy |
| `skew` | CBOE SKEW | `positioning.inputs.layer2.skew` | `gate.norm` → z-gate |
| `vix_ratio` | VIX Term Structure | `positioning.inputs.layer2.vix_ratio` | `gate.raw` + `gate.signal` → legacy |
| `pct_above_200dma` | % Above 200DMA | `positioning.inputs.layer2.pct_above_200dma` | `gate.norm` → z-gate |

**Badge:** `gate.vote` (boolean) → ✓ / ✗ (existing behaviour).  
**Side tint (optional):** `gate.side` when present (`long` \| `short`).

### Confirm rules (for sub-label copy)

**Z-gate** (`mcclellan`, `nh_nl_ratio`, `skew`, `pct_above_200dma`):

- Confirm when `|gate.norm| >= 0.5` (`gate_z_min` in `SSI_CONFIG.yaml`)
- `gate.signal`: `bullish` \| `bearish` \| `neutral`
- Sub-label example: `z −0.60 · confirms` or `z −0.29 · need |z|≥0.5`

**Legacy HYG/LQD** (`hyg_lqd`):

- Confirm when 5y percentile `gate.pctile` ≥ 70 (`risk_on`) or ≤ 30 (`risk_off`)
- `gate.signal`: `risk_on` \| `risk_off` \| `neutral`
- Sub-label example: `100th pctile · risk on`

**Legacy VIX ratio** (`vix_ratio`):

- `gate.raw` = VIX ÷ VIX3M (>1 backwardation, <1 contango)
- Confirm when `raw >= 1.05` (`stress`) or `raw <= 0.95` (`complacency`)
- Sub-label example: `ratio 0.91 · complacency (≤0.95)` or `ratio 1.09 · stress (≥1.05)`

**Null / missing:** if `gate.raw` or `gate.norm` is null, show `unavailable` and no ✓.

## Suggested row layout

```
McClellan Oscillator          −5.99    ✗
  z −0.29 · need |z|≥0.5

NH Share (NH/(NH+NL))          0.57    ✓
  z −0.60 · bearish

HYG/LQD                        0.75    ✓
  100th pctile · risk on

CBOE SKEW                    141.23    ✗
  z −0.07 · need |z|≥0.5

VIX Term Structure             0.91    ✓
  ratio 0.91 · complacency (≤0.95)

% Above 200DMA                67.86    ✗
  z +0.46 · need |z|≥0.5
```

*(First block = original bug report scenario, 2026-08-04 investigation.)*

## Live payload reference (2026-08-04, after refresh)

```json
{
  "layer2_gate_label": "L2: 3 long / 0 short of 6 - long confirmed",
  "layer2_gate_direction": "LONG_CONFIRMED",
  "positioning": {
    "inputs": {
      "layer2": {
        "mcclellan": 2.96,
        "nh_nl_ratio": 1.0,
        "hyg_lqd": 0.75,
        "skew": 139.96,
        "vix_ratio": null,
        "pct_above_200dma": 69.86
      },
      "layer2_gate_votes": [
        { "input": "mcclellan", "norm": 0.13, "vote": false, "signal": "neutral" },
        { "input": "nh_nl_ratio", "norm": 0.88, "vote": true, "signal": "bullish", "side": "long" },
        { "input": "hyg_lqd", "pctile": 99.98, "vote": true, "signal": "risk_on", "side": "long" },
        { "input": "skew", "norm": 0.03, "vote": false, "signal": "neutral" },
        { "input": "vix_ratio", "raw": null, "vote": false, "signal": "neutral" },
        { "input": "pct_above_200dma", "norm": 0.58, "vote": true, "signal": "bullish", "side": "long" }
      ]
    }
  }
}
```

## Panel header (optional but recommended)

Under **Layer 2 · Daily Timing** title, show `layer2_gate_label` when present.

Do **not** reuse `layer2_status` / `ssi_multiplier` text for this — those are sizing labels. Gate label is directional (long vs short tally).

## Vue files (expected touch points)

| File | Change |
|------|--------|
| `server/utils/sentiment-mapper.ts` | `formatLayer2GateItem()` — add confirm-driver sub-label from rules above |
| `pages/sentiment.vue` | Layer 2 panel header → bind `layer2_gate_label` |
| `types/api.ts` | Ensure `layer2_gate_label`, `layer2_gate_direction`, `layer2_gate_conf_long`, `layer2_gate_conf_short` typed on layers response |

## Do not

- Use `positioning.layers.layer2.components.*.raw` for the main value column (full float, not display-rounded).
- Use `components.*.norm` as the main value (that's the z-score; users need the familiar raw print).
- Assume all ✓ rows are z-score confirms (HYG and VIX are percentile/ratio rules).

## Smoke test

```bash
curl -s -H "X-API-Key: $API_KEY" \
  http://localhost:8507/api/v1/analytics/sentiment/layers \
  | jq '{
      label: .layer2_gate_label,
      direction: .layer2_gate_direction,
      gates: [.layer2_gate_votes[] | {input, vote, signal, norm, pctile, raw}]
    }'
```

Sentiment page: each Layer 2 row shows raw value + confirm driver sub-label; header shows gate label.

## API docs

Full field reference: `docs/mindwealth-api-docs/services/analytics/endpoints/get-sentiment-layers.md`
