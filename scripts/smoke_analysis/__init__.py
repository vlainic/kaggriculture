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
    return "\n".join(lines)
