# Macro / Runic API

**Status:** implemented (v1.2.0)

**Router:** `api/routers/macro.py`

**Source:** `macro_intelligence/output/runic_output.json`, `positioning.json`

**Domain docs:** [`docs/MACRO_INTELLIGENCE_MASTER.md`](../../../MACRO_INTELLIGENCE_MASTER.md)

## Endpoints

| Method | Path | Doc |
|--------|------|-----|
| GET | `/macro/runic/nightly` | [get-runic-nightly.md](endpoints/get-runic-nightly.md) |
| GET | `/macro/runic/variables/current` | [get-runic-variables.md](endpoints/get-runic-variables.md) |
| GET | `/macro/combo/active` | [get-active-combos.md](endpoints/get-active-combos.md) |
| GET | `/macro/sentiment/positioning` | [get-positioning.md](endpoints/get-positioning.md) |

All paths are prefixed with `/api/v1`.

## Errors

| Status | Cause |
|--------|-------|
| 404 | Runic or positioning output file not found on disk |

## Related

Merged SSI + sentiment view: [get-sentiment-layers.md](../analytics/endpoints/get-sentiment-layers.md)
