"""Part H — automated 9-step combo discovery pipeline for 298 generic combos."""

from __future__ import annotations

import itertools
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from src.macro_intelligence.claude._client import call_claude, parse_json_text
from src.macro_intelligence.claude.geo_news import fetch_geo_headlines
from src.macro_intelligence.config import load_config
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.engine.combo_detector import VAR_IDS

HORIZON_COLS = ["spx_1m", "spx_3m", "spx_6m", "spx_9m", "spx_12m"]
REGIME_DIMS = ["fed_cycle", "curve_regime", "val_regime", "geo_overlay", "liquidity"]
BEARISH_DIRECTIONS = {"BEARISH", "NEGATIVE", "TIGHT", "HIGH", "WIDE", "STRESSED", "ELEVATED"}


@dataclass
class FireRecord:
    combo_id: int
    date: str
    var_ids: tuple[str, ...]
    directions: list[str | None]
    returns: dict[str, float | None]
    regime: dict[str, Any]


@dataclass
class ComboResult:
    signature: str
    var_ids: tuple[str, ...]
    combo_size: int
    bullish: bool
    n_fires: int = 0
    horizons: dict[str, dict[str, Any]] = field(default_factory=dict)
    primary_hit_rate: float | None = None
    primary_avg_return: float | None = None
    surfaced: bool = False
    beta_pass: bool = False
    beta_hostile_hit_rate_55: float | None = None
    beta_hostile_hit_rate_60: float | None = None
    beta_beats_unconditional: bool = False
    beta_beats_single_var: bool = False
    beta_beats_regime_base: bool = False
    directionality_pass: bool = False
    directionality_dims_passing: int = 0
    directionality_detail: dict[str, float | None] = field(default_factory=dict)
    promotion_candidate: bool = False
    story_status: str = "PENDING"
    story_coherent: bool | None = None
    story_narrative: str | None = None
    fire_dates: list[str] = field(default_factory=list)
    gate_stage: str = "filtered"


def combo_signature(var_ids: tuple[str, ...]) -> str:
    return "+".join(sorted(var_ids))


def enumerate_all_signatures() -> list[tuple[str, ...]]:
    """298 combos: C(12,1) + C(12,2) + C(12,3)."""
    out: list[tuple[str, ...]] = []
    for r in (1, 2, 3):
        out.extend(tuple(sorted(c)) for c in itertools.combinations(VAR_IDS, r))
    return out


def _discovery_cfg() -> dict[str, Any]:
    return load_config().get("combo_discovery", {})


def _infer_bullish(directions: list[str | None]) -> bool:
    bearish = sum(1 for d in directions if d and str(d).upper() in BEARISH_DIRECTIONS)
    return bearish < len([d for d in directions if d]) / 2


def _hit_rate(returns: list[float], bullish: bool) -> float | None:
    if not returns:
        return None
    if bullish:
        return sum(1 for r in returns if r > 0) / len(returns)
    return sum(1 for r in returns if r < 0) / len(returns)


def _avg_return(returns: list[float]) -> float | None:
    if not returns:
        return None
    return float(np.mean(returns))


def _horizon_metrics(fires: list[FireRecord], bullish: bool) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for col in HORIZON_COLS:
        vals = [f.returns[col] for f in fires if f.returns.get(col) is not None]
        hr = _hit_rate(vals, bullish)
        out[col] = {
            "n": len(vals),
            "hit_rate": round(hr, 4) if hr is not None else None,
            "avg_return": round(_avg_return(vals), 4) if vals else None,
        }
    return out


def load_generic_fires() -> list[FireRecord]:
    records: list[FireRecord] = []
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.combo_id, cf.date, cf.var1_id, cf.var2_id, cf.var3_id,
                   cf.var1_direction, cf.var2_direction, cf.var3_direction,
                   cf.macro_regime,
                   fr.spx_1m, fr.spx_3m, fr.spx_6m, fr.spx_9m, fr.spx_12m
            FROM combo_fires cf
            LEFT JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE cf.runic_combo IS NULL
            ORDER BY cf.date
            """
        ).fetchall()
    for row in rows:
        var_ids = tuple(v for v in (row["var1_id"], row["var2_id"], row["var3_id"]) if v)
        directions = [row["var1_direction"], row["var2_direction"], row["var3_direction"]]
        directions = [d for d in directions if d is not None][: len(var_ids)]
        regime: dict[str, Any] = {}
        if row["macro_regime"]:
            try:
                regime = json.loads(row["macro_regime"])
            except json.JSONDecodeError:
                regime = {}
        records.append(
            FireRecord(
                combo_id=row["combo_id"],
                date=row["date"],
                var_ids=var_ids,
                directions=directions,
                returns={
                    "spx_1m": row["spx_1m"],
                    "spx_3m": row["spx_3m"],
                    "spx_6m": row["spx_6m"],
                    "spx_9m": row["spx_9m"],
                    "spx_12m": row["spx_12m"],
                },
                regime=regime,
            )
        )
    return records


def _group_fires_by_signature(fires: list[FireRecord]) -> dict[str, list[FireRecord]]:
    grouped: dict[str, list[FireRecord]] = {}
    for f in fires:
        sig = combo_signature(f.var_ids)
        grouped.setdefault(sig, []).append(f)
    return grouped


def _is_hostile(regime: dict[str, Any], cfg: dict[str, Any]) -> bool:
    fed = str(regime.get("fed_cycle", "")).upper()
    curve = str(regime.get("curve_regime", "")).upper()
    hostile_fed = [x.upper() for x in cfg.get("hostile_fed_cycles", [])]
    hostile_curve = [x.upper() for x in cfg.get("hostile_curve_regimes", [])]
    return any(h in fed for h in hostile_fed) or curve in hostile_curve


def _compute_base_rates(
    all_fires: list[FireRecord],
    signature_fires: list[FireRecord],
    horizon: str,
    bullish: bool,
) -> dict[str, float | None]:
    """Unconditional, single-var proxy, and regime-matched base avg returns."""
    all_vals = [f.returns[horizon] for f in all_fires if f.returns.get(horizon) is not None]
    unconditional_avg = _avg_return(all_vals)

    sig_vars = set(signature_fires[0].var_ids) if signature_fires else set()
    single_vals: list[float] = []
    for f in all_fires:
        if len(f.var_ids) != 1:
            continue
        if f.var_ids[0] not in sig_vars:
            continue
        v = f.returns.get(horizon)
        if v is not None:
            single_vals.append(v)
    single_avg = _avg_return(single_vals)

    regime_avgs: list[float] = []
    for f in signature_fires:
        fed = f.regime.get("fed_cycle")
        if not fed:
            continue
        matched = [
            x.returns[horizon]
            for x in all_fires
            if x.returns.get(horizon) is not None and x.regime.get("fed_cycle") == fed
        ]
        if matched:
            regime_avgs.append(_avg_return(matched) or 0.0)
    regime_base_avg = _avg_return(regime_avgs) if regime_avgs else unconditional_avg

    return {
        "unconditional_avg": unconditional_avg,
        "single_var_avg": single_avg,
        "regime_base_avg": regime_base_avg,
    }


def _directionality_check(
    fires: list[FireRecord],
    horizon: str,
    bullish: bool,
    cfg: dict[str, Any],
) -> tuple[bool, int, dict[str, float | None]]:
    min_dims = int(cfg.get("directionality_min_dims", 2))
    min_hr = float(cfg.get("directionality_min_hit_rate", 0.50))
    detail: dict[str, float | None] = {}
    passing = 0
    for dim in REGIME_DIMS:
        buckets: dict[str, list[float]] = {}
        for f in fires:
            key = str(f.regime.get(dim, "UNKNOWN"))
            v = f.returns.get(horizon)
            if v is not None:
                buckets.setdefault(key, []).append(v)
        dim_hrs = [_hit_rate(vals, bullish) for vals in buckets.values() if len(vals) >= 2]
        dim_hr = max(dim_hrs) if dim_hrs else None
        detail[dim] = round(dim_hr, 4) if dim_hr is not None else None
        if dim_hr is not None and dim_hr >= min_hr:
            passing += 1
    return passing >= min_dims, passing, detail


def _evaluate_signature(
    var_ids: tuple[str, ...],
    fires: list[FireRecord],
    all_fires: list[FireRecord],
    cfg: dict[str, Any],
) -> ComboResult:
    sig = combo_signature(var_ids)
    bullish = _infer_bullish(fires[0].directions) if fires else True
    horizons = _horizon_metrics(fires, bullish) if fires else {c: {"n": 0, "hit_rate": None, "avg_return": None} for c in HORIZON_COLS}
    primary = str(cfg.get("primary_horizon", "spx_3m"))
    primary_vals = [f.returns[primary] for f in fires if f.returns.get(primary) is not None]
    primary_hr = _hit_rate(primary_vals, bullish)
    primary_avg = _avg_return(primary_vals)

    result = ComboResult(
        signature=sig,
        var_ids=var_ids,
        combo_size=len(var_ids),
        bullish=bullish,
        n_fires=len(fires),
        horizons=horizons,
        primary_hit_rate=round(primary_hr, 4) if primary_hr is not None else None,
        primary_avg_return=round(primary_avg, 4) if primary_avg is not None else None,
        fire_dates=[f.date for f in fires],
    )

    min_fires = int(cfg.get("surface_min_fires", 3))
    min_hr = float(cfg.get("surface_min_hit_rate", 0.60))
    if result.n_fires < min_fires or primary_hr is None or primary_hr < min_hr:
        result.gate_stage = "below_surface"
        return result

    result.surfaced = True
    result.gate_stage = "surfaced"

    hostile_fires = [f for f in fires if _is_hostile(f.regime, cfg)]
    hostile_vals = [f.returns[primary] for f in hostile_fires if f.returns.get(primary) is not None]
    hr55 = float(cfg.get("beta_min_hit_rate", 0.55))
    hr60 = float(cfg.get("beta_min_hit_rate_alt", 0.60))
    hostile_hr = _hit_rate(hostile_vals, bullish) if hostile_vals else None
    result.beta_hostile_hit_rate_55 = round(hostile_hr, 4) if hostile_hr is not None else None
    result.beta_hostile_hit_rate_60 = result.beta_hostile_hit_rate_55

    bases = _compute_base_rates(all_fires, fires, primary, bullish)
    combo_avg = primary_avg or 0.0
    if bullish:
        beats_uncond = combo_avg > (bases["unconditional_avg"] or -999)
        beats_single = combo_avg > (bases["single_var_avg"] or -999) if bases["single_var_avg"] is not None else True
        beats_regime = combo_avg > (bases["regime_base_avg"] or -999)
    else:
        beats_uncond = combo_avg < (bases["unconditional_avg"] or 999)
        beats_single = combo_avg < (bases["single_var_avg"] or 999) if bases["single_var_avg"] is not None else True
        beats_regime = combo_avg < (bases["regime_base_avg"] or 999)

    result.beta_beats_unconditional = beats_uncond
    result.beta_beats_single_var = beats_single
    result.beta_beats_regime_base = beats_regime
    hostile_ok = hostile_hr is None or hostile_hr >= hr55
    result.beta_pass = hostile_ok and beats_uncond and beats_single and beats_regime

    if not result.beta_pass:
        result.gate_stage = "failed_beta"
        return result

    dir_pass, dir_count, dir_detail = _directionality_check(fires, primary, bullish, cfg)
    result.directionality_pass = dir_pass
    result.directionality_dims_passing = dir_count
    result.directionality_detail = dir_detail
    if not dir_pass:
        result.gate_stage = "failed_directionality"
        return result

    result.gate_stage = "survivor"
    promo_fires = int(cfg.get("promotion_min_fires", 5))
    promo_hr = float(cfg.get("promotion_min_hit_rate", 0.80))
    if result.n_fires >= promo_fires and primary_hr is not None and primary_hr >= promo_hr:
        result.promotion_candidate = True
    return result


def _has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def enrich_narratives(results: list[ComboResult], *, use_claude: bool = True) -> None:
    """Step 7: economic story for all Step 4-6 survivors."""
    survivors = [r for r in results if r.gate_stage == "survivor" or r.gate_stage == "survivor_pending_story"]
    if not use_claude or not _has_api_key():
        for r in survivors:
            r.story_status = "SKIPPED"
        return

    system = (
        'Return ONLY JSON: {"story_coherent": true|false, "narrative": "2-3 sentence causal summary"}'
    )
    for r in survivors:
        dates_sample = r.fire_dates[:5]
        headlines_parts: list[str] = []
        for d in dates_sample:
            h = fetch_geo_headlines(d)
            if h:
                headlines_parts.append(f"{d}: {h[:500]}")
        user = (
            f"Combo variables: {r.signature}. Direction: {'bullish' if r.bullish else 'bearish'} SPX. "
            f"Historical fire dates ({r.n_fires} total): {', '.join(dates_sample)}. "
            f"3m hit rate: {r.primary_hit_rate}. News context:\n"
            + ("\n".join(headlines_parts) or "No headlines.")
            + "\nDoes this combo have a coherent economic causal story or is it likely coincidence?"
        )
        try:
            text = call_claude(system, user, max_tokens=300)
            data = parse_json_text(text)
            r.story_coherent = bool(data.get("story_coherent"))
            r.story_narrative = str(data.get("narrative", ""))
            r.story_status = "COMPLETE"
        except Exception as exc:
            r.story_status = f"ERROR:{exc}"
            r.story_coherent = None
            r.story_narrative = None

        if r.promotion_candidate and r.story_coherent is False:
            r.promotion_candidate = False


def run_combo_discovery_pipeline(
    *,
    horizon: str | None = None,
    use_claude: bool = False,
) -> dict[str, Any]:
    """Run all 298 combos through Steps 1-9 in one pass."""
    cfg = _discovery_cfg()
    if horizon:
        cfg = {**cfg, "primary_horizon": horizon}

    all_sigs = enumerate_all_signatures()
    all_fires = load_generic_fires()
    grouped = _group_fires_by_signature(all_fires)

    results: list[ComboResult] = []
    for var_ids in all_sigs:
        sig = combo_signature(var_ids)
        fires = grouped.get(sig, [])
        results.append(_evaluate_signature(var_ids, fires, all_fires, cfg))

    enrich_narratives(results, use_claude=use_claude)

    survivors = [r for r in results if r.gate_stage == "survivor"]
    surfaced = [r for r in results if r.surfaced]
    promotion = [r for r in results if r.promotion_candidate and r.story_coherent is not False]

    def _sort_key(r: ComboResult) -> tuple:
        return (
            0 if r.promotion_candidate else 1,
            0 if r.gate_stage == "survivor" else 1,
            -(r.primary_hit_rate or 0),
            -r.n_fires,
        )

    ranked = sorted(results, key=_sort_key)

    return {
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "config": cfg,
        "summary": {
            "total_signatures": len(all_sigs),
            "signatures_with_fires": sum(1 for r in results if r.n_fires > 0),
            "surfaced": len(surfaced),
            "beta_pass": sum(1 for r in results if r.beta_pass),
            "directionality_pass": sum(1 for r in results if r.directionality_pass),
            "survivors": len(survivors),
            "promotion_candidates": len(promotion),
            "total_generic_fires": len(all_fires),
        },
        "survivors": [_result_to_dict(r) for r in ranked if r.gate_stage == "survivor"],
        "surfaced_not_survivors": [
            _result_to_dict(r)
            for r in ranked
            if r.surfaced and r.gate_stage not in ("survivor",)
        ],
        "promotion_candidates": [_result_to_dict(r) for r in promotion],
        "all_results": [_result_to_dict(r) for r in ranked],
    }


def _result_to_dict(r: ComboResult) -> dict[str, Any]:
    return {
        "signature": r.signature,
        "var_ids": list(r.var_ids),
        "combo_size": r.combo_size,
        "bullish": r.bullish,
        "n_fires": r.n_fires,
        "primary_hit_rate": r.primary_hit_rate,
        "primary_avg_return": r.primary_avg_return,
        "horizons": r.horizons,
        "surfaced": r.surfaced,
        "beta_pass": r.beta_pass,
        "beta_hostile_hit_rate_55": r.beta_hostile_hit_rate_55,
        "beta_hostile_hit_rate_60": r.beta_hostile_hit_rate_60,
        "beta_beats_unconditional": r.beta_beats_unconditional,
        "beta_beats_single_var": r.beta_beats_single_var,
        "beta_beats_regime_base": r.beta_beats_regime_base,
        "directionality_pass": r.directionality_pass,
        "directionality_dims_passing": r.directionality_dims_passing,
        "directionality_detail": r.directionality_detail,
        "promotion_candidate": r.promotion_candidate,
        "story_status": r.story_status,
        "story_coherent": r.story_coherent,
        "story_narrative": r.story_narrative,
        "gate_stage": r.gate_stage,
        "fire_dates": r.fire_dates,
    }


def write_pipeline_artifacts(
    payload: dict[str, Any],
    *,
    write_report: bool = True,
) -> tuple[Path, Path | None]:
    """Write JSON artifact and optional markdown report."""
    out_dir = Path("macro_intelligence/analysis/combo_discovery")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = payload.get("run_date", datetime.now().strftime("%Y-%m-%d")).replace("-", "")
    json_path = out_dir / f"combo_discovery_{stamp}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_path: Path | None = None
    if write_report:
        md_path = Path("docs/ssi_validation/COMBO_DISCOVERY_PIPELINE_REPORT.md")
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_report(payload), encoding="utf-8")
    return json_path, md_path


def _render_report(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    cfg = payload["config"]
    primary = cfg.get("primary_horizon", "spx_3m")
    lines = [
        "# Combo Discovery Pipeline Report (Part H)",
        "",
        f"**Run date:** {payload['run_date']}",
        f"**Primary horizon:** {primary}",
        f"**Source:** automated 9-step pipeline — fixed CONFIG thresholds, no per-combo fitting",
        "",
        "## Summary funnel",
        "",
        "| Stage | Count |",
        "|-------|-------|",
        f"| Signatures enumerated | {s['total_signatures']} |",
        f"| Signatures with ≥1 fire | {s['signatures_with_fires']} |",
        f"| Surfaced (≥{cfg.get('surface_min_fires')} fires, ≥{int(cfg.get('surface_min_hit_rate', 0.6)*100)}% HR) | {s['surfaced']} |",
        f"| Beta filter pass | {s['beta_pass']} |",
        f"| Directionality pass | {s['directionality_pass']} |",
        f"| **Survivors (Steps 4–6)** | **{s['survivors']}** |",
        f"| Promotion candidates (≥{cfg.get('promotion_min_fires')} fires, ≥{int(cfg.get('promotion_min_hit_rate', 0.8)*100)}% HR) | {s['promotion_candidates']} |",
        "",
        "## Ranked survivors",
        "",
        "| Signature | n | 3m HR | 3m avg% | Hostile HR | Beta | Dir | Promo | Story |",
        "|-----------|---|-------|---------|------------|------|-----|-------|-------|",
    ]
    for r in payload.get("survivors", []):
        h3 = r.get("horizons", {}).get("spx_3m", {})
        lines.append(
            f"| {r['signature']} | {r['n_fires']} | {h3.get('hit_rate')} | {h3.get('avg_return')} | "
            f"{r.get('beta_hostile_hit_rate_55')} | {'Y' if r.get('beta_pass') else 'N'} | "
            f"{r.get('directionality_dims_passing')}/5 | "
            f"{'Y' if r.get('promotion_candidate') else 'N'} | {r.get('story_status')} |"
        )
    if not payload.get("survivors"):
        lines.append("| *(none)* | | | | | | | | |")

    lines.extend(["", "## Promotion candidates", ""])
    promos = payload.get("promotion_candidates", [])
    if promos:
        for r in promos:
            lines.append(f"### {r['signature']}")
            lines.append(f"- Fires: {r['n_fires']}, 3m hit rate: {r['primary_hit_rate']}")
            if r.get("story_narrative"):
                lines.append(f"- Narrative: {r['story_narrative']}")
            lines.append("")
    else:
        lines.append("No combos met promotion gate (5 fires, 80% HR, beta pass, coherent story).")
        lines.append("")

    failed = payload.get("surfaced_not_survivors", [])[:20]
    if failed:
        lines.extend(["## Surfaced but filtered (top 20 by hit rate)", ""])
        lines.append("| Signature | n | HR | Failed at |")
        lines.append("|-----------|---|-----|-----------|")
        for r in failed:
            lines.append(
                f"| {r['signature']} | {r['n_fires']} | {r['primary_hit_rate']} | {r['gate_stage']} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Human review",
            "",
            "Review survivors and promotion candidates above. Thresholds are fixed in `macro_intelligence/CONFIG.yaml` — do not tune per combo.",
            "",
            f"JSON artifact: `macro_intelligence/analysis/combo_discovery/combo_discovery_{payload['run_date'].replace('-', '')}.json`",
            "",
        ]
    )
    return "\n".join(lines)
