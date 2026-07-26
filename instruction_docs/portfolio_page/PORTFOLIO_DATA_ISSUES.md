# Portfolio data requirements — issues brief

**Audience:** backend + product  
**Date:** 2026-07-23 (re-verified live)  
**UI:** MindWealth Alpha Terminal — `/portfolio` Overview  
**Related:** `docs/PORTFOLIO_API_HANDOFF.md` (full contracts), `docs/PORTFOLIO_UI_RESTORE.md` (UI wiring), API docs pack **8** (`mindwealth-api-docs-main 8`)

---

## 1. Executive summary

The Portfolio **Overview** page is empty by design when backend Overview payloads are missing. The UI is already wired to the required v1 endpoints and **does not invent NAV, P&L, allocations, or chart series**.

Two separate problems currently block data:

1. **Prod API (`:8506`)** — Overview endpoints are **not routed** (`404 Not Found`).
2. **Test API (`:8507`)** — supposed home of v1.8.2 Overview routes — is **down** (Squid returns HTML `503` for all `/api/v1/*`).

Until Overview APIs return **200 JSON** on whatever host the UI points at, Overview will keep showing:

> *Portfolio overview waiting for backend data. Layout remains available; no figures are synthesized in frontend.*

Sizing & Allocation / Portfolio Risk can still work on prod (sizer + risk already `200` on `:8506`). Overview cannot.

---

## 2. What the UI needs (product rules)

| Rule | Meaning |
|------|---------|
| Backend owns all math | No client-side allocation scaling, normalize-to-100%, or stitching VT + conviction into fake sizes |
| Books | `model` \| `brokerage` \| `personal` |
| Model valuation books | `base` \| `ssi` \| `cv` \| `enhanced` (UI default `enhanced`; query `book` only when `book_id=model`) |
| Nulls | Missing values must be `null` (UI shows `—`). Do not fabricate zeroes for missing NAV/P&L |
| Empty vs error | Valid empty book → `[]` / nulls. Failed compute → `5xx` / structured error. Never sample data |

Frontend only formats and displays what the API returns.

---

## 3. Endpoints that unblock Overview

All paths are under `/api/v1`.

| Priority | Method | Path | Query (model example) | UI surface blocked |
|----------|--------|------|------------------------|--------------------|
| **P0** | GET | `/portfolio/nav` | `book_id=model&book=enhanced` | NAV hero, day MTM, since go-live, positions, deployed, L/S, attribution, admission/next-in/out, eviction, contributors/detractors, risk chips, waterfall, NAV chart |
| **P0** | GET | `/portfolio/holdings` | `book_id=model&book=enhanced` | Holdings table + detail rail; brokerage/personal Live P&L |
| **P1** | GET | `/signals/entries` | `book_id=model` | Pipeline **NEW ENTRIES** count/list |
| **P1** | GET | `/signals/exits` | `book_id=model` | Pipeline **NEW EXITS** count/list |

**Also required for other Portfolio tabs (already live on prod):**

| Priority | Method | Path | Status on `:8506` |
|----------|--------|------|-------------------|
| P0 | GET | `/portfolio/sizer?scenario=normal\|stress\|lowvol` | **200** |
| P0 | GET | `/portfolio/risk?scenario=…` | **200** |
| P1 | GET | `/portfolio/risk/search` | **200** |
| P1 | POST | `/portfolio/risk/analyze` | **200** |

Full response shapes: `PORTFOLIO_API_HANDOFF.md` §§3–6. Docs pack 8 marks nav/holdings/entries/exits as **implemented (v1.8.2)** for **MODEL `book=enhanced` only**; four-book NAV history still pending (`null` / `[]` + `nav_history_note` is OK).

---

## 4. Live environment status (2026-07-23)

| Host | Role | Overview routes (`nav` / `holdings` / `entries` / `exits`) | Sizer / Risk |
|------|------|-------------------------------------------------------------|--------------|
| `http://51.20.53.218:8507` | Testing API (v1.8.2 target) | **503** Squid HTML — upstream process not reachable | **503** Squid HTML |
| `http://51.20.53.218:8506` | Prod API (current UI `.env`) | **404** `{"detail":"Not Found"}` — routes not deployed | **200** JSON |

Nuxt BFF proxies `NUXT_API_BASE_URL`. With `.env` on `:8506`:

```http
GET /api/v1/portfolio/nav?book_id=model&book=enhanced
→ 404 Not Found
```

That is exactly why Overview shows dashes, `0` pipeline counts, “No data returned,” and “NAV series unavailable from backend.”

### Probe examples

```bash
# Prod — routes missing
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "X-API-Key: $KEY" \
  "http://51.20.53.218:8506/api/v1/portfolio/nav?book_id=model&book=enhanced"
# → 404

# Test — host down (Squid)
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "X-API-Key: $KEY" \
  "http://51.20.53.218:8507/api/v1/portfolio/nav?book_id=model&book=enhanced"
# → 503 (HTML error page, not JSON)

# Prod — already working (non-Overview)
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "X-API-Key: $KEY" \
  "http://51.20.53.218:8506/api/v1/portfolio/sizer?scenario=normal"
# → 200
```

---

## 5. Docs vs reality mismatch

| Source | Claim | Reality (2026-07-23) |
|--------|-------|----------------------|
| API docs pack **8** | `GET /portfolio/nav`, `/holdings`, `/signals/entries`, `/signals/exits` **implemented v1.8.2** (MODEL `book=enhanced`) | Not available on **prod `:8506`**. Test **`:8507`** is the intended host but currently **down**. |
| `PORTFOLIO_API_HANDOFF.md` (2026-07-22) | Overview endpoints **404 / blocked** | Still true on prod. |
| UI restore playbook | Point local Overview work at **`:8507`** | Correct *when* 8507 is healthy; pointless while Squid 503. |

**Conclusion:** Frontend is waiting for a backend that either is not deployed to the host the UI uses, or is documented on a test host that is offline.

---

## 6. Secondary field gaps (do not block Overview shell)

These endpoints return **200** on prod but omit fields the UI already renders when present:

| Endpoint | Gap | UI effect |
|----------|-----|-----------|
| `GET /portfolio/sizer` | `pnl_rows[]` / positions often lack `cross_function_exit`, `asset_class`, `status` | Badges / status chips stay hidden |
| `GET /portfolio/risk` | No `conviction_summary` | Conviction panel stays `—` |
| `GET /signals/reports/portfolio-risk/latest` | No `implied_natural_exit_date`; `book_id` isolation unclear | Conflict panel incomplete |

Priority: **P1** after Overview P0 routes ship.

---

## 7. What is *not* a frontend bug

- Empty Overview with waiting banner → **correct** when nav/holdings fail.
- Dashes (`—`) instead of `$0` → **correct** null handling.
- No fake NAV chart from sizer data → **correct** (restore rule: do not fill Overview from sizer).
- Sizing/Risk still usable on prod while Overview empty → **expected** split of endpoint maturity.

Do **not** ask UI to mock Overview figures to “look live.” That violates the portfolio contract.

---

## 8. Unblock checklist (backend / ops)

### Immediate

- [ ] Bring API process behind **`:8507`** back up (stop Squid HTML 503 on `/api/v1/*`).
- [ ] Confirm v1.8.2 Overview routes on that host:
  - [ ] `GET /api/v1/portfolio/nav?book_id=model&book=enhanced` → **200** JSON
  - [ ] `GET /api/v1/portfolio/holdings?book_id=model&book=enhanced` → **200** JSON
  - [ ] `GET /api/v1/signals/entries?book_id=model` → **200**
  - [ ] `GET /api/v1/signals/exits?book_id=model` → **200**
- [ ] Point UI test `.env` at the healthy host:
  ```env
  NUXT_API_BASE_URL=http://51.20.53.218:8507
  NUXT_API_KEY=<same key>
  ```
  Restart Nuxt after change.

### Then (product completeness)

- [ ] Deploy same Overview routes to **prod `:8506`** (or explicitly keep Overview-only on test until cutover).
- [ ] Extend beyond MODEL `enhanced` when ready: `base` / `ssi` / `cv`, plus `brokerage` / `personal` books (HANDOFF §3–4).
- [ ] Fill P1 field gaps on sizer / risk / conflicts (§6).

### Acceptance smoke (UI)

- [ ] `/portfolio` Overview shows live NAV (or honest empty arrays) — never invented dollars.
- [ ] Valuation toggle works for model; non-model books hide Sizing + Risk.
- [ ] Holdings table populated from `/holdings`.
- [ ] Entries/exits pipeline counts match API arrays.
- [ ] Sizing/Risk still match sizer/risk JSON pass-through.

---

## 9. Owner split

| Layer | Responsibility |
|-------|----------------|
| **Backend / ops** | Implement or deploy `/portfolio/nav`, `/portfolio/holdings`, `/signals/entries`, `/signals/exits`; keep test host healthy; eventually ship to prod |
| **Frontend** | Already wired; keep pass-through; empty-state until 200; no mocks |
| **Product** | Decide whether Overview stays test-only on `:8507` until prod deploy, vs blocking prod UI on missing routes |

---

## 10. One-line status for standup

> Portfolio Overview is empty because prod (`:8506`) returns **404** for nav/holdings/entries/exits, and the test host that docs say implements them (`:8507`) is **503 / down**. UI will light up when those four endpoints return 200 on the configured `NUXT_API_BASE_URL`.

End of brief.
