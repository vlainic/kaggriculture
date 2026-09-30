"""Smoke analysis — parse local smoke_test logs into diagnostic reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from smoke_analysis import (
    parse_actions,
    parse_earnings,
    parse_exec,
    parse_opp,
    parse_planner,
    parse_sell_prices,
    parse_snap,
    parse_fc_err,
    parse_shed,
    audit_threeland,
)
from smoke_analysis.kpi import compute_kpis
from smoke_analysis.load import SEASON_DAYS, load_lines, parse_seed

__all__ = [
    "analyze",
    "plot_smoke",
    "plot_earnings_by_day",
    "plot_earnings_by_zone",
    "plot_worker_actions",
    "plot_stuck_skip_freq",
    "plot_zone_capacity",
    "plot_zone_earnings_vs_cost",
    "plot_us_vs_opp_daily",
    "plot_sell_price_heatmap",
    "plot_fc_err",
    "summarize_distribution",
    "load_lines",
    "SEASON_DAYS",
]


def plot_smoke(report: dict[str, Any], *, title: str | None = None) -> None:
    from smoke_analysis.plot import plot_smoke as _plot

    return _plot(report, title=title)


def plot_earnings_by_day(report: dict[str, Any], *, title: str | None = None) -> None:
    from smoke_analysis.plot import plot_earnings_by_day as _plot

    return _plot(report, title=title)


def plot_earnings_by_zone(report: dict[str, Any], *, title: str | None = None) -> None:
    from smoke_analysis.plot import plot_earnings_by_zone as _plot

    return _plot(report, title=title)


def plot_worker_actions(report: dict[str, Any], *, title: str | None = None) -> None:
    from smoke_analysis.plot import plot_worker_actions as _plot

    return _plot(report, title=title)


def plot_stuck_skip_freq(
    reports: list[dict[str, Any]], *, title: str | None = None
) -> None:
    from smoke_analysis.plot import plot_stuck_skip_freq as _plot

    return _plot(reports, title=title)


def plot_zone_capacity(report: dict[str, Any], *, title: str | None = None) -> None:
    from smoke_analysis.plot import plot_zone_capacity as _plot

    return _plot(report, title=title)


def plot_zone_earnings_vs_cost(
    report: dict[str, Any], *, title: str | None = None
) -> None:
    from smoke_analysis.plot import plot_zone_earnings_vs_cost as _plot

    return _plot(report, title=title)


def plot_us_vs_opp_daily(report: dict[str, Any], *, title: str | None = None) -> None:
    from smoke_analysis.plot import plot_us_vs_opp_daily as _plot

    return _plot(report, title=title)


def plot_sell_price_heatmap(report: dict[str, Any], *, title: str | None = None) -> None:
    from smoke_analysis.plot import plot_sell_price_heatmap as _plot

    return _plot(report, title=title)


def plot_fc_err(report: dict[str, Any], *, title: str | None = None) -> None:
    from smoke_analysis.plot import plot_fc_err as _plot

    return _plot(report, title=title)


def analyze(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    lines = load_lines(path)

    from smoke_analysis.layout import active_layout

    layout = active_layout()
    workers = layout["workers"]
    hand_workers = layout["hand_workers"]
    worker_tiles = layout["worker_tiles"]
    land2_workers = layout["land2_workers"]

    parse_snap.bind_workers(workers)

    snaps = parse_snap.parse_snaps(lines)
    empty_by_worker = parse_snap.empty_by_worker_by_day(snaps, season_days=SEASON_DAYS)
    total_empty = []
    for day in range(SEASON_DAYS):
        vals = [empty_by_worker[w][day] for w in workers if empty_by_worker.get(w)]
        total_empty.append(sum(v for v in vals if v is not None) if vals else None)

    passes = parse_exec.parse_passes(lines, season_days=SEASON_DAYS)
    hires = parse_exec.parse_hires(lines, season_days=SEASON_DAYS)
    buy_land_day = parse_exec.parse_buy_land_day(lines)
    reward = parse_exec.parse_final_reward(lines)
    passed = parse_exec.smoke_passed(lines)

    planner = parse_planner.parse_planner_events(lines)
    planner["start_blocks"] = parse_exec.parse_start_blocks(lines)
    if buy_land_day is None and planner.get("buy_land_day_logged") is not None:
        buy_land_day = planner["buy_land_day_logged"]

    kpi = compute_kpis(
        planner=planner,
        snaps_empty=empty_by_worker,
        hires=hires,
        buy_land_day=buy_land_day,
        worker_tiles=worker_tiles,
        land2_workers=land2_workers,
        workers=workers,
        land2_tile_min=layout["land2_tile_min"],
        has_land2=layout["has_land2"],
        land2_probe_worker=layout.get("land2_probe_worker"),
    )

    actions = parse_actions.parse_worker_actions(
        lines,
        season_days=SEASON_DAYS,
        hand_workers=hand_workers,
        workers=list(workers),
    )

    hands_dawn = parse_exec.parse_hands_dawn(lines, season_days=SEASON_DAYS)
    hands_eod = parse_exec.parse_hands_eod(lines, season_days=SEASON_DAYS)

    earnings = parse_earnings.parse_earnings(
        lines,
        snaps,
        season_days=SEASON_DAYS,
        hand_workers=hand_workers,
        worker_tiles=worker_tiles,
    )

    opp = parse_opp.parse_opp(lines, season_days=SEASON_DAYS)
    vs_opp = {
        **opp,
        "us_tile_ops_by_day": parse_opp.us_tile_ops_by_day(
            actions, season_days=SEASON_DAYS
        ),
        "opp_tile_ops_by_day": opp["tile_ops_by_day"],
        "us_net_cash_by_day": earnings.get("net_cash_by_day") or [0.0] * SEASON_DAYS,
        "opp_net_cash_by_day": opp["net_cash_by_day"],
        "us_money_by_day": parse_snap.money_by_day(snaps, season_days=SEASON_DAYS),
        "opp_money_by_day": opp["money_by_day"],
    }

    sell_prices = parse_sell_prices.parse_sell_price_heatmap(
        lines, snaps, season_days=SEASON_DAYS
    )

    fc_err = parse_fc_err.parse_fc_err(lines, season_days=SEASON_DAYS)
    shed_cap = parse_shed.parse_shed_cap(lines, season_days=SEASON_DAYS)
    disposal = parse_shed.parse_disposal_events(lines)
    threeland_audit = audit_threeland.audit_threeland(lines, season_days=SEASON_DAYS)

    worker_first_day = parse_exec.parse_worker_first_active_day(
        lines,
        workers,
        season_days=SEASON_DAYS,
        harvest_by_worker_by_day=earnings.get("harvest_by_worker_by_day"),
    )

    return {
        "log_path": str(path),
        "log_stem": path.stem,
        "seed": parse_seed(path),
        "layout": layout["layout_name"],
        "reward": reward,
        "smoke_passed": passed,
        "buy_land_day": buy_land_day,
        "tiles": {
            "empty_by_worker_by_day": empty_by_worker,
            "total_empty_by_day": total_empty,
        },
        "passes": passes,
        "money": {"by_day": parse_snap.money_by_day(snaps, season_days=SEASON_DAYS)},
        "earnings": earnings,
        "actions": actions,
        "vs_opp": vs_opp,
        "sell_prices": sell_prices,
        "fc_err": fc_err,
        "shed_cap": shed_cap,
        "disposal": disposal,
        "threeland_audit": threeland_audit,
        "hires": hires,
        "hands": {**hands_dawn, **hands_eod},
        "planner": planner,
        "kpi": kpi,
        "workers": list(workers),
        "land1_workers": list(layout["land1_workers"]),
        "land2_workers": list(land2_workers),
        "land2_tile_min": layout["land2_tile_min"],
        "has_land2": layout["has_land2"],
        "land2_probe_worker": layout.get("land2_probe_worker"),
        "net_tile_ops": dict(layout.get("net_tile_ops") or {}),
        "hand_daily_cost": dict(layout.get("hand_daily_cost") or {}),
        "worker_first_day": worker_first_day,
        "package": layout.get("package"),
    }


def summarize_distribution(reports: list[dict[str, Any]]) -> str:
    if not reports:
        return "no reports"
    rewards = [r["reward"] for r in reports if r.get("reward") is not None]
    seeds = [r.get("seed") for r in reports if r.get("seed") is not None]
    stuck_fires = [
        sum(
            1
            for e in ((r.get("planner") or {}).get("zone_streak_events") or [])
            if e.get("status") == "stuck"
        )
        for r in reports
    ]
    skip_counts = [
        len((r.get("planner") or {}).get("skip_cascade") or []) for r in reports
    ]
    stuck_worker_counts = [
        len((r.get("kpi") or {}).get("stuck_zones", {}).get("workers_stuck") or [])
        for r in reports
    ]
    lines = [f"runs={len(reports)}"]
    if rewards:
        mean = sum(rewards) / len(rewards)
        spread = max(rewards) - min(rewards)
        lines.append(
            f"reward: min={min(rewards):.0f} max={max(rewards):.0f} "
            f"mean={mean:.0f} spread={spread:.0f} "
            f"values={[round(x) for x in rewards]}"
        )
    if seeds:
        lines.append(f"seeds (observed): {seeds}")
    if stuck_fires:
        n_any = sum(1 for c in stuck_fires if c > 0)
        mean_f = sum(stuck_fires) / len(stuck_fires)
        lines.append(
            f"stuck_fires: runs_with={n_any}/{len(reports)} "
            f"mean={mean_f:.1f} values={stuck_fires}"
        )
    if skip_counts:
        mean_s = sum(skip_counts) / len(skip_counts)
        lines.append(
            f"skip_cascade: mean={mean_s:.1f} values={skip_counts}"
        )
    if stuck_worker_counts:
        n_stuck = sum(1 for c in stuck_worker_counts if c > 0)
        lines.append(
            f"stuck_runs={n_stuck}/{len(reports)} stuck_worker_counts={stuck_worker_counts}"
        )
    prem_means = [
        (r.get("fc_err") or {}).get("mean_premium_abs_err_d3_plus")
        for r in reports
    ]
    prem_vals = [v for v in prem_means if v is not None]
    if prem_vals:
        lines.append(
            f"fc_err premium d3+ mean: "
            f"avg={sum(prem_vals)/len(prem_vals):.2f} values={[round(v, 1) for v in prem_vals]}"
        )
    wool_ranges = [
        (r.get("fc_err") or {}).get("err_range_by_product_d3_plus", {}).get("WOOL")
        for r in reports
    ]
    wool_ranges = [v for v in wool_ranges if v is not None]
    if wool_ranges:
        lines.append(
            f"fc_err WOOL d3+ range: avg={sum(wool_ranges)/len(wool_ranges):.1f} "
            f"values={[round(v, 1) for v in wool_ranges]}"
        )
    streaks = [(r.get("shed_cap") or {}).get("max_cap_streak") for r in reports]
    streaks = [v for v in streaks if v is not None]
    if streaks:
        lines.append(
            f"shed max_cap_streak: mean={sum(streaks)/len(streaks):.1f} values={streaks}"
        )
    room_ev = [((r.get("disposal") or {}).get("room_events")) for r in reports]
    room_ev = [v for v in room_ev if v is not None]
    if room_ev:
        lines.append(f"[room] events mean={sum(room_ev)/len(room_ev):.1f} values={room_ev}")
    wasted = [
        (r.get("threeland_audit") or {}).get("wasted_land_events", 0) for r in reports
    ]
    if any(wasted):
        lines.append(
            f"audit wasted_land: mean={sum(wasted)/len(wasted):.1f} values={wasted}"
        )
    return "\n".join(lines)


def summarize(report: dict[str, Any]) -> str:
    stuck = report.get("kpi", {}).get("stuck_zones") or {}
    land2 = report.get("land2_workers") or []
    lines = [
        f"log={report.get('log_stem')} seed={report.get('seed')} "
        f"layout={report.get('layout')} package={report.get('package')} "
        f"land2={len(land2)} workers "
        f"reward={report.get('reward')} "
        f"smoke_passed={report.get('smoke_passed')} buy_land_day={report.get('buy_land_day')}",
        f"PASS total={report.get('passes', {}).get('total')} "
        f"HIRE total={report.get('hires', {}).get('total')}",
        f"replan_days={len(report.get('planner', {}).get('replan_days', []))} "
        f"skip_cascade={len(report.get('planner', {}).get('skip_cascade', []))} "
        f"infeasible={len(report.get('planner', {}).get('infeasible', []))}",
    ]
    vs = report.get("vs_opp") or {}
    if vs.get("present"):
        us_ops = sum(vs.get("us_tile_ops_by_day") or [])
        opp_ops = sum(vs.get("opp_tile_ops_by_day") or [])
        lines.append(
            f"vs_opp: tile_ops us={us_ops} opp={opp_ops} "
            f"reward_us={vs.get('reward_us')} reward_opp={vs.get('reward_opp')} "
            f"margin={vs.get('margin')}"
        )
    idle = report.get("kpi", {}).get("idle_proxy", {})
    lines.append(
        f"idle: mean_empty={idle.get('mean_empty_per_dawn', 0):.1f} "
        f"land2_mean={idle.get('land2_mean_empty_per_dawn', 0):.1f} "
        f"hire5_empty_days={idle.get('hire5_empty_days')} "
        f"max_streak={idle.get('max_hire5_empty_streak')}"
    )
    lines.append(
        f"stuck: workers={stuck.get('workers_stuck') or '-'} "
        f"healed<={stuck.get('heal_within_days', 5)}d={stuck.get('workers_healed_within_n_days') or '-'} "
        f"permanent/slow={stuck.get('workers_permanent_or_slow') or '-'}"
    )
    for name, check in (report.get("kpi", {}).get("acceptance") or {}).items():
        if isinstance(check, dict):
            mark = "OK" if check.get("pass") else "FAIL"
            lines.append(f"  [{mark}] {name}: {check.get('detail', '')}")
    prem = (report.get("fc_err") or {}).get("mean_premium_abs_err_d3_plus")
    if prem is not None:
        lines.append(f"fc_err premium d3+ mean={prem:.2f}")
    wool_rng = (report.get("fc_err") or {}).get("err_range_by_product_d3_plus", {}).get(
        "WOOL"
    )
    if wool_rng is not None:
        lines.append(f"fc_err WOOL d3+ range={wool_rng:.1f}")
    sc = report.get("shed_cap") or {}
    if sc.get("max_cap_streak") is not None:
        lines.append(
            f"shed: days_at_cap={sc.get('days_at_cap')} "
            f"max_cap_streak={sc.get('max_cap_streak')}"
        )
    disp = report.get("disposal") or {}
    if disp:
        lines.append(
            f"disposal: room={disp.get('room_events')} "
            f"animal_cap={disp.get('animal_cap_events')} "
            f"sell_lead={disp.get('sell_lead_events')}"
        )
    aud = report.get("threeland_audit") or {}
    if aud:
        lines.append(
            f"threeland_audit: wasted_land={aud.get('wasted_land_events')} "
            f"value_unknown={aud.get('value_unknown_events')} "
            f"latch_suspects={len(aud.get('low_value_latch_suspects') or [])} "
            f"cascade_skip={aud.get('cascade_skip_lines')}"
        )
    return "\n".join(lines)
