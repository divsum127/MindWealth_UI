"""Runic Macro Intelligence REST routes — v1.3.0."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.dependencies import optional_api_key
from api.services import macro_service as msvc
from api.services import reports_service as svc

router = APIRouter(prefix="/macro", tags=["macro"], dependencies=[Depends(optional_api_key)])


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _runic_or_404(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Legacy endpoints (keep for backward compat)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/runic/nightly", operation_id="get_runic_nightly",
            summary="Full nightly Runic JSON output")
def get_runic_nightly() -> dict[str, Any]:
    """Complete runic_output.json payload — all fields."""
    return _runic_or_404(svc.load_runic_nightly)


@router.get("/runic/variables/current", operation_id="get_runic_variables_current",
            summary="Regime + 12-variable dashboard subset")
def get_runic_variables() -> dict[str, Any]:
    try:
        data = svc.load_runic_nightly()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "date": data.get("date"),
        "regime": data.get("regime", {}),
        "variables_dashboard": data.get("variables_dashboard", []),
    }


@router.get("/combo/active", operation_id="get_active_combos",
            summary="Dominant signal + active and watch combo list")
def get_active_combos() -> dict[str, Any]:
    try:
        data = svc.load_runic_nightly()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "date": data.get("date"),
        "dominant_signal": data.get("dominant_signal"),
        "active_combos": data.get("active_combos", []),
        "watch_combos": data.get("watch_combos", []),
    }


@router.get("/sentiment/positioning", operation_id="get_ssi_positioning",
            summary="SSI positioning JSON")
def get_positioning() -> dict[str, Any]:
    try:
        return svc.load_positioning()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ─────────────────────────────────────────────────────────────────────────────
# NEW — Overview
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/status", operation_id="get_macro_status_bar",
            summary="Header status bar — dominant signal, brave/fearful, CFTC state")
def get_status_bar() -> dict[str, Any]:
    """
    Single endpoint for the top-strip status bar in the frontend.
    Returns dominant signal, brave/fearful display, active/watch combo IDs,
    CFTC status, VIX bypass flag, and Combo C cancel progress.
    """
    return _runic_or_404(msvc.get_status_bar)


@router.get("/overview/kpis", operation_id="get_macro_overview_kpis",
            summary="Five KPI cards for the Overview tab")
def get_overview_kpis() -> dict[str, Any]:
    """
    Structured data for the 5 KPI cards shown in the Overview tab:
    - Dominant signal + posture
    - Combo C duration + bucket
    - Combo F window (weeks elapsed)
    - CAPE + Combo E status
    - WTI 4-week Δ + cancel gate
    """
    return _runic_or_404(msvc.get_overview_kpis)


# ─────────────────────────────────────────────────────────────────────────────
# NEW — Regime
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/regime", operation_id="get_macro_regime",
            summary="5-dimension regime classification + narrative")
def get_regime() -> dict[str, Any]:
    """
    Regime classification card:
    - 5 regime dimensions (fed_cycle, curve_regime, geo_overlay, val_regime, liquidity)
    - Brave/fearful posture + display label
    - Dominant signal + reason
    - Nightly narrative (Claude Sonnet generated)
    - System recommendation
    - VIX bypass state, SSI layer2 status
    """
    return _runic_or_404(msvc.get_regime)


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled macro events (pre-catalyst + post-event regime)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/events/pre-catalyst", operation_id="get_macro_pre_catalyst",
            summary="Pre-catalyst fragility before CPI/FOMC/NFP")
def get_pre_catalyst() -> dict[str, Any]:
    """
    Pre-catalyst fragility intelligence from the latest nightly run:
    - Whether a CPI, FOMC, or NFP event is within the pre-event window (7 days)
    - Count of macro variables in the 60th–79th / 21st–40th percentile bands
    - fragility_score HIGH when 4+ variables are near-threshold
    """
    return _runic_or_404(msvc.get_pre_catalyst_intel)


@router.get("/events/post-regime", operation_id="get_macro_post_event_regime",
            summary="Post-event regime transition within 48h of CPI/FOMC/NFP")
def get_post_event_regime() -> dict[str, Any]:
    """
    Post-event regime reclassification from the latest nightly run:
    - Active when within 48 hours of a scheduled CPI/FOMC/NFP release
    - regime_transition true when 2+ variables crossed RARE thresholds
    - transition_type: LIQUIDITY_SHOCK, FISCAL_DOMINANCE_FEAR, CREDIBILITY_RESTORED,
      BEAR_FLATTEN, or BULL_STEEPEN
    - Event-window metrics (yields, HY, VIX, USD)
    """
    return _runic_or_404(msvc.get_post_event_regime_intel)


@router.get("/events/calendar", operation_id="get_macro_scheduled_events_calendar",
            summary="Upcoming CPI, FOMC, and NFP release dates")
def get_scheduled_events_calendar(
    days: int = Query(21, ge=1, le=90, description="Calendar horizon in days"),
) -> dict[str, Any]:
    """
    Scheduled macro event calendar from pending_releases (CPI, FOMC, NFP).
    FOMC/NFP dates sourced from FRED release calendars; CPI includes consensus
    when available from Trading Economics / BLS ingest.
    """
    return _runic_or_404(msvc.get_scheduled_events_calendar, days=days)


# ─────────────────────────────────────────────────────────────────────────────
# NEW — 12 Variables
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/variables/heatmap", operation_id="get_variables_heatmap",
            summary="12-variable heatmap — tiers, thresholds, combo links")
def get_variables_heatmap() -> dict[str, Any]:
    """
    Enriched 12-variable list for the heatmap panel.
    Each variable includes:
    - current value, tier (NORMAL / RARE / EXTREME / PENDING)
    - pctile_3yr, direction
    - source, compute method, rare_gate, extreme_gate thresholds
    - list of combo letters that use this variable
    """
    return _runic_or_404(msvc.get_variables_heatmap)


# ─────────────────────────────────────────────────────────────────────────────
# NEW — Named Combos (A–G)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/combos", operation_id="list_named_combos",
            summary="All 7 named combos A–G with current status and hit rates")
def list_named_combos() -> dict[str, Any]:
    """
    Full list of all 7 named combos (A–G).
    Each entry includes: name, direction, horizon, legs required,
    current status (ACTIVE / WATCH / INACTIVE / RESOLVED),
    confirmed_legs, duration, hit_rate_primary, avg_return_primary.
    """
    return _runic_or_404(msvc.get_all_combos)


@router.get("/combos/{combo_id}", operation_id="get_named_combo_detail",
            summary="Full detail for one named combo (A–G)")
def get_combo_detail(combo_id: str) -> dict[str, Any]:
    """
    Full detail for a single named combo (A–G):
    - Static metadata (name, variables, thresholds, description)
    - Live status, confirmed legs, duration
    - Hit rate stats (primary + secondary horizons)
    - Historical analog fire dates with SPX forward returns (1m/3m/6m/9m/12m)
    """
    return _runic_or_404(msvc.get_combo_detail, combo_id)


# ─────────────────────────────────────────────────────────────────────────────
# NEW — Combo Trackers
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/combo-c/cancel", operation_id="get_combo_c_cancel_tracker",
            summary="Combo C cancel condition monitor — 0/4 Fridays, CPI, probability")
def get_combo_c_cancel_tracker() -> dict[str, Any]:
    """
    Combo C cancel tracker:
    - fridays_complete / fridays_required (0 of 4)
    - Current WTI 4-week Δ vs +5% cancel gate
    - Latest CPI print (not hot check)
    - Friday-by-Friday log of WTI leg and CPI leg pass/fail
    - Monte Carlo cancel probability model output
    - Upcoming CPI/PPI release dates
    - If-cancelled scenario (F becomes dominant)
    """
    return _runic_or_404(msvc.get_combo_c_cancel_tracker)


@router.get("/combo-f/window", operation_id="get_combo_f_window",
            summary="Combo F 26-week recovery window tracker")
def get_combo_f_window() -> dict[str, Any]:
    """
    Combo F window tracker:
    - fire_date, expiry_date, weeks_elapsed, weeks_remaining
    - progress_pct (0–100 for progress bar)
    - mtm_pct (current mark-to-market from fire date)
    - hit rate stats and historical avg returns
    - Cancel condition (Combo B only)
    - D+F tension explanation
    """
    return _runic_or_404(msvc.get_combo_f_window)


# ─────────────────────────────────────────────────────────────────────────────
# NEW — Analog Tables
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/analogs/{combo_id}", operation_id="get_combo_analog_table",
            summary="Historical analog fire dates with SPX forward returns for one combo")
def get_analog_table(combo_id: str) -> dict[str, Any]:
    """
    Historical analog table for a named combo (A–G):
    - All stored fire dates with context
    - SPX forward returns: 1m, 3m, 6m, 9m, 12m
    - Summary median returns across instances
    - Hit rate stats
    """
    return _runic_or_404(msvc.get_analog_table, combo_id)


# ─────────────────────────────────────────────────────────────────────────────
# NEW — Narrative / Brief
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/narrative", operation_id="get_nightly_narrative",
            summary="Nightly narrative + system recommendation")
def get_narrative() -> dict[str, Any]:
    """
    Nightly brief tab data:
    - Full Claude-generated narrative (200–250 words)
    - System recommendation
    - Brave/fearful posture display
    - Dominant signal + reason
    - Current regime dimensions
    - CFTC status
    """
    return _runic_or_404(msvc.get_narrative)


# ─────────────────────────────────────────────────────────────────────────────
# NEW — Persistence signals
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/persistence", operation_id="get_persistence_signals",
            summary="Persistence signals and generic combo watch list")
def get_persistence_signals() -> dict[str, Any]:
    """
    Persistence signals (7-week grind, VIX suppression, etc.) and
    generic auto-discovered combo candidates passing the ≥80% gate.
    Also includes source freshness audit.
    """
    return _runic_or_404(msvc.get_persistence_signals)


# ─────────────────────────────────────────────────────────────────────────────
# NEW — Source freshness
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/data/freshness", operation_id="get_data_freshness",
            summary="Data source freshness audit for all 12 variables")
def get_data_freshness() -> dict[str, Any]:
    """
    Per-variable source freshness: last data date, lag vs report, CFTC status,
    pending CPI flag, and expected next source dates.
    """
    return _runic_or_404(msvc.get_source_freshness)


# ─────────────────────────────────────────────────────────────────────────────
# NEW — Trigger nightly run
# ─────────────────────────────────────────────────────────────────────────────

class NightlyRunRequest(BaseModel):
    as_of: str | None = None
    use_claude: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# SSI  (Super Sentiment Index)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/ssi/summary", operation_id="get_ssi_summary",
            summary="Latest SSI snapshot — level, percentile, multiplier, layer2 status + votes")
def get_ssi_summary() -> dict[str, Any]:
    """
    Returns the latest day's SSI data from `ssi.db`:

    - ssi_level (composite sentiment score)
    - ssi_percentile_5y (rank vs last 5-years)
    - ssi_multiplier (1.0 / 1.2 / 0.8 sizing factor)
    - layer2_status (CONFIRMED / UNCONFIRMED)
    - layer2_confirmed_count (how many of the 4 inputs agree)
    - posture (RISK_ON / RISK_OFF / NEUTRAL)
    - per-input breakdown (hyg_lqd, dbmf_beta, cnn_fg, vix_ratio)
    """
    try:
        return msvc.get_ssi_summary()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/ssi/history", operation_id="get_ssi_history",
            summary="Daily SSI time series — level, multiplier, inputs (up to 90 days)")
def get_ssi_history(days: int = 30) -> dict[str, Any]:
    """
    Returns chronological daily SSI series for charting.

    - `days` query param (default 30, max 90): number of calendar days to return.
    - Each row: date, ssi_level, ssi_percentile_5y, ssi_multiplier, layer2_status,
      layer2_confirmed_count, and the 4 raw input values.
    """
    if days < 1:
        days = 1
    if days > 90:
        days = 90
    try:
        return msvc.get_ssi_history(days=days)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/ssi/multiplier", operation_id="get_ssi_multiplier",
            summary="Current SSI multiplier + sizing signals (lightweight)")
def get_ssi_multiplier() -> dict[str, Any]:
    """
    Lightweight endpoint for position-sizing checks.

    Returns the current multiplier (1.0 / 1.2 / 0.8), ssi_level,
    layer2 status, and the long/short signal flags + entry thresholds.
    Does NOT load the full SSI payload.
    """
    try:
        return msvc.get_ssi_multiplier()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ─────────────────────────────────────────────────────────────────────────────

@router.post("/run-nightly", operation_id="trigger_nightly_run",
             summary="Trigger a nightly Runic run (no Claude by default)")
def trigger_nightly_run(body: NightlyRunRequest | None = None) -> dict[str, Any]:
    """
    Trigger the full nightly data pull + combo detection + JSON write.
    use_claude=False (default) skips Claude API for speed and cost.
    Set use_claude=True to include geo overlay + narrative regeneration.

    Returns: status, date, dominant_signal, active_combos, output_path.
    """
    req = body or NightlyRunRequest()
    try:
        return msvc.trigger_nightly_run(as_of=req.as_of, use_claude=req.use_claude)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
