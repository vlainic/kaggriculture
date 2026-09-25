"""Matplotlib charts for replay analysis reports."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.pricing import base_price  # noqa: E402

from replay_analysis.load import SEASON_DAYS

DAYS = list(range(SEASON_DAYS))

US_COLOR = "#1565c0"
US_COLOR_LIGHT = "#90caf9"
OPP_COLOR = "#c62828"
OPP_COLOR_LIGHT = "#ef9a9a"


def _player_label(report: dict[str, Any], player: int) -> str:
    names = report.get("agents") or []
    if player < len(names):
        return names[player]
    return f"P{player}"


def _us_opp(report: dict[str, Any]) -> tuple[int, int]:
    us = report.get("us_index")
    if us is None:
        us = 0
    return us, 1 - us


def plot_game(report: dict[str, Any], *, title: str | None = None) -> None:
    us, opp = _us_opp(report)
    us_label = _player_label(report, us)
    opp_label = _player_label(report, opp)
    stem = title or report.get("replay_stem") or "replay"
    kpi = report.get("kpi") or {}

    fig = plt.figure(figsize=(16, 40))
    gs = fig.add_gridspec(12, 2, hspace=0.45, wspace=0.25)
    fig.suptitle(
        f"{stem}  seed={report.get('seed')}  rewards={report.get('rewards')}",
        fontsize=11,
    )

    tiles = report["tiles"]["by_player"]
    _plot_tiles(fig.add_subplot(gs[0, 0]), tiles[us], us_label)
    _plot_tiles(fig.add_subplot(gs[0, 1]), tiles[opp], opp_label)

    passes = report["passes"]["by_player"]
    _plot_passes(fig.add_subplot(gs[1, 0]), passes[us], us_label)
    _plot_passes(fig.add_subplot(gs[1, 1]), passes[opp], opp_label)

    money = report["money"]["by_player"]
    _plot_money(fig.add_subplot(gs[2, :]), money, us, opp, us_label, opp_label)

    yield_block = report.get("yield") or {}
    potential_list = yield_block.get("potential")
    harvested_list = yield_block.get("harvested") or yield_block.get("by_player")
    sells = report["sells"]["by_player"]
    _plot_yield_pipeline(
        fig.add_subplot(gs[3, 0]),
        _player_entry(potential_list, us),
        _player_entry(harvested_list, us),
        sells[us],
        us_label,
    )
    _plot_yield_pipeline(
        fig.add_subplot(gs[3, 1]),
        _player_entry(potential_list, opp),
        _player_entry(harvested_list, opp),
        sells[opp],
        opp_label,
    )

    _plot_price_violins(
        fig.add_subplot(gs[4, :]),
        report.get("sells", {}).get("events") or [],
        us,
        opp,
        us_label,
        opp_label,
    )

    shed = report["shed_end"]["by_player"]
    _plot_shed_table(fig.add_subplot(gs[5, :]), shed, us, opp, us_label, opp_label)

    exec_k = kpi.get("executor") or []
    _plot_action_histogram(
        fig.add_subplot(gs[6, 0]),
        _player_entry(exec_k, us),
        us_label,
        US_COLOR,
    )
    _plot_action_histogram(
        fig.add_subplot(gs[6, 1]),
        _player_entry(exec_k, opp),
        opp_label,
        OPP_COLOR,
    )

    _plot_ripe_care(
        fig.add_subplot(gs[7, :]),
        _player_entry(exec_k, us),
        _player_entry(exec_k, opp),
        us_label,
        opp_label,
    )

    mkt_k = kpi.get("market") or []
    _plot_revenue_spend(
        fig.add_subplot(gs[8, :]),
        _player_entry(mkt_k, us),
        _player_entry(mkt_k, opp),
        us_label,
        opp_label,
    )

    _plot_fill_price_quality(
        fig.add_subplot(gs[9, :]),
        _player_entry(mkt_k, us),
        us_label,
    )

    plan_k = kpi.get("planner") or []
    _plot_planner_cash(
        fig.add_subplot(gs[10, :]),
        _player_entry(plan_k, us),
        _player_entry(plan_k, opp),
        _player_entry(mkt_k, us),
        _player_entry(mkt_k, opp),
        us_label,
        opp_label,
    )

    _plot_kpi_table(
        fig.add_subplot(gs[11, :]),
        _player_entry(exec_k, us),
        _player_entry(mkt_k, us),
        _player_entry(plan_k, us),
        us_label,
    )

    plt.tight_layout()
    plt.show()


def _plot_tiles(ax, series: list[dict[str, int]], label: str) -> None:
    occupied = [d.get("occupied", 0) for d in series]
    empty = [d.get("empty", 0) for d in series]
    weed = [d.get("weed", 0) for d in series]
    empty_struct = [d.get("empty_structure", 0) for d in series]
    ax.stackplot(
        DAYS,
        occupied,
        empty,
        weed,
        empty_struct,
        labels=["occupied", "empty", "weed", "empty_struct"],
        alpha=0.85,
    )
    ax.set_title(f"{label} — tiles (h=0)")
    ax.set_ylabel("count")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, linestyle="--", alpha=0.35)


def _plot_passes(ax, stats: dict[str, Any], label: str) -> None:
    per_day = stats.get("per_day") or [0] * SEASON_DAYS
    workers = stats.get("workers_by_day") or [1] * SEASON_DAYS
    ax.bar(DAYS, per_day, color="#607d8b", alpha=0.85, label="PASS")
    ax2 = ax.twinx()
    ax2.plot(
        DAYS,
        workers,
        color="#ff9800",
        linewidth=1.5,
        label="workers",
    )
    ax.set_title(
        f"{label} — PASS / day (total={stats.get('total', 0)}, "
        f"mean/worker={stats.get('mean_per_worker', 0):.2f})"
    )
    ax.set_ylabel("passes")
    ax2.set_ylabel("workers", color="#ff9800")
    ax2.tick_params(axis="y", labelcolor="#ff9800")
    ax.grid(True, axis="y", linestyle="--", alpha=0.35)


def _plot_money(
    ax,
    money: list[dict[str, Any]] | dict[int, dict[str, Any]],
    us: int,
    opp: int,
    us_label: str,
    opp_label: str,
) -> None:
    for player, label, color, color_light in (
        (us, us_label, US_COLOR, US_COLOR_LIGHT),
        (opp, opp_label, OPP_COLOR, OPP_COLOR_LIGHT),
    ):
        m = _player_entry(money, player)
        start = m.get("start") or []
        end = m.get("end") or []
        ax.plot(DAYS, start, color=color, linewidth=2, label=f"{label} start")
        ax.plot(
            DAYS,
            end,
            color=color_light,
            linewidth=1.5,
            linestyle="--",
            label=f"{label} end",
        )
        final = m.get("final_reward")
        if final is not None:
            ax.scatter(
                [SEASON_DAYS - 1],
                [final],
                color=color,
                s=50,
                zorder=5,
                label=f"{label} final",
            )
    ax.set_title("Bank balance — start (solid) / end (dashed) + final score")
    ax.set_ylabel("coins")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.grid(True, linestyle="--", alpha=0.35)


def _plot_yield_pipeline(
    ax,
    potential_map: dict[str, int],
    harvested_map: dict[str, int],
    sell_stats: dict[str, Any],
    label: str,
) -> None:
    sold = sell_stats.get("filled_units") or {}
    products = sorted(set(potential_map) | set(harvested_map) | set(sold))
    if not products:
        ax.text(0.5, 0.5, "No yield data", ha="center", va="center")
        ax.set_title(f"{label} — potential / harvested / sold")
        return
    x = np.arange(len(products))
    w = 0.25
    ax.bar(
        x - w,
        [potential_map.get(p, 0) for p in products],
        w,
        label="potential",
        color="#bdbdbd",
    )
    ax.bar(
        x,
        [harvested_map.get(p, 0) for p in products],
        w,
        label="harvested",
        color="#8bc34a",
    )
    ax.bar(
        x + w,
        [sold.get(p, 0) for p in products],
        w,
        label="sold",
        color="#1976d2",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(products, rotation=45, ha="right", fontsize=8)
    ax.set_title(f"{label} — potential / harvested / sold")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", linestyle="--", alpha=0.35)


def _price_events_by_product(
    events: list[dict[str, Any]], us: int, opp: int
) -> dict[str, dict[int, list[float]]]:
    by_product: dict[str, dict[int, list[float]]] = defaultdict(
        lambda: {us: [], opp: []}
    )
    for ev in events:
        prod = ev.get("product")
        player = ev.get("player")
        price = ev.get("price")
        if prod is None or player not in (us, opp) or price is None:
            continue
        base = base_price(str(prod))
        by_product[str(prod)][player].append(int(price) / base)
    return by_product


def _violin_density(values: list[float], y_grid: np.ndarray) -> np.ndarray:
    """Gaussian KDE — smooth violin shape from discrete fill prices."""
    if not values:
        return np.zeros_like(y_grid)
    arr = np.asarray(values, dtype=float)
    n = len(arr)
    if n == 1:
        bw = 0.04
        z = (y_grid - arr[0]) / bw
        return np.exp(-0.5 * z * z)

    std = float(arr.std(ddof=1)) if n > 1 else 0.0
    if std < 1e-6:
        std = max(0.04, abs(float(arr.mean())) * 0.05)
    # Silverman-ish bandwidth; floor keeps discrete price ladders smooth.
    bw = max(0.045, 1.06 * std * (n ** (-0.2)))

    z = (y_grid[:, None] - arr[None, :]) / bw
    return np.exp(-0.5 * z * z).sum(axis=1) / (n * bw * np.sqrt(2.0 * np.pi))


def _draw_split_violin_at(
    ax,
    x_center: float,
    us_vals: list[float],
    opp_vals: list[float],
    y_grid: np.ndarray,
    *,
    half_width: float = 0.35,
    show_legend: bool = False,
    us_label: str = "",
    opp_label: str = "",
) -> None:
    us_d = _violin_density(us_vals, y_grid)
    opp_d = _violin_density(opp_vals, y_grid)
    peak = max(float(us_d.max()), float(opp_d.max()), 1e-9)
    us_d /= peak
    opp_d /= peak

    if us_vals:
        ax.fill_betweenx(
            y_grid,
            x_center - us_d * half_width,
            x_center,
            color=US_COLOR,
            alpha=0.65,
            label=us_label if show_legend else None,
        )
        ax.plot(
            x_center - us_d * half_width,
            y_grid,
            color=US_COLOR,
            linewidth=0.6,
            alpha=0.9,
        )
    if opp_vals:
        ax.fill_betweenx(
            y_grid,
            x_center,
            x_center + opp_d * half_width,
            color=OPP_COLOR,
            alpha=0.65,
            label=opp_label if show_legend else None,
        )
        ax.plot(
            x_center + opp_d * half_width,
            y_grid,
            color=OPP_COLOR,
            linewidth=0.6,
            alpha=0.9,
        )

    for vals, color in ((us_vals, US_COLOR), (opp_vals, OPP_COLOR)):
        if vals:
            ax.hlines(
                float(np.median(vals)),
                x_center - half_width,
                x_center + half_width,
                colors=color,
                linestyles="--",
                linewidth=1.0,
                alpha=0.9,
            )


def _plot_price_violins(
    ax,
    events: list[dict[str, Any]],
    us: int,
    opp: int,
    us_label: str,
    opp_label: str,
) -> None:
    by_product = _price_events_by_product(events, us, opp)
    products = sorted(by_product)
    if not products:
        ax.text(0.5, 0.5, "No sells", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Sell price / base")
        return

    all_vals = [
        v
        for prod in products
        for v in by_product[prod][us] + by_product[prod][opp]
    ]
    lo, hi = min(all_vals), max(all_vals)
    pad = max(0.05, (hi - lo) * 0.12)
    y_grid = np.linspace(max(0.0, lo - pad), hi + pad, 400)

    positions = np.arange(len(products))
    for i, prod in enumerate(products):
        _draw_split_violin_at(
            ax,
            float(positions[i]),
            by_product[prod][us],
            by_product[prod][opp],
            y_grid,
            show_legend=(i == 0),
            us_label=us_label,
            opp_label=opp_label,
        )

    ax.axhline(1.0, color="gray", linewidth=0.8, linestyle=":", alpha=0.8)
    ax.set_xticks(positions)
    ax.set_xticklabels(products, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("price / base")
    ax.set_xlim(-0.6, len(products) - 0.4)
    ax.set_title(
        f"Sell price / base — {us_label} (left, blue) vs {opp_label} (right, red)"
    )
    ax.grid(True, axis="y", linestyle="--", alpha=0.35)
    if any(by_product[p][us] or by_product[p][opp] for p in products):
        ax.legend(loc="upper right", fontsize=8)


def _player_entry(by_player: list[Any] | dict[int, Any], player: int) -> Any:
    if isinstance(by_player, dict):
        return by_player.get(player) or {}
    if by_player is None:
        return {}
    if player < len(by_player):
        entry = by_player[player]
        return entry if isinstance(entry, dict) else {}
    return {}


def _plot_shed_table(
    ax,
    shed: list[dict[str, Any]] | dict[int, dict[str, Any]],
    us: int,
    opp: int,
    us_label: str,
    opp_label: str,
) -> None:
    ax.axis("off")
    rows = []
    for player, label in ((us, us_label), (opp, opp_label)):
        s = _player_entry(shed, player)
        combined = s.get("combined") or {}
        if not combined:
            rows.append([label, "(empty)", "", ""])
            continue
        for item, qty in sorted(combined.items()):
            shed_q = (s.get("shed") or {}).get(item, 0)
            carried_q = (s.get("carried") or {}).get(item, 0)
            rows.append([label, item, str(shed_q), str(carried_q)])
            label = ""
    if not rows:
        ax.text(0.5, 0.5, "Empty end shed", ha="center", va="center")
        return
    table = ax.table(
        cellText=rows,
        colLabels=["player", "item", "shed", "carried"],
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.3)
    ax.set_title("End-of-game inventory (shed + carried)", pad=20)


def _plot_action_histogram(
    ax, exec_k: dict[str, Any], label: str, color: str
) -> None:
    hist = exec_k.get("action_histogram") or {}
    if not hist:
        ax.text(0.5, 0.5, "No actions", ha="center", va="center")
        ax.set_title(f"{label} — action histogram")
        return
    ops = sorted(hist, key=lambda k: -hist[k])[:14]
    vals = [hist[o] for o in ops]
    ax.barh(ops, vals, color=color, alpha=0.75)
    ax.invert_yaxis()
    overhead = exec_k.get("move_overhead", 0)
    noops = (exec_k.get("noop_ops") or {}).get("total", 0)
    ax.set_title(
        f"{label} — actions (move/prod={overhead:.2f}, noops={noops})",
        fontsize=9,
    )
    ax.grid(True, axis="x", linestyle="--", alpha=0.35)


def _plot_ripe_care(
    ax,
    exec_us: dict[str, Any],
    exec_opp: dict[str, Any],
    us_label: str,
    opp_label: str,
) -> None:
    ripe_us = ((exec_us.get("ripe_unharvested") or {}).get("by_day") or [0] * SEASON_DAYS)
    ripe_opp = ((exec_opp.get("ripe_unharvested") or {}).get("by_day") or [0] * SEASON_DAYS)
    ax.plot(DAYS, ripe_us, color=US_COLOR, label=f"{us_label} ripe tile-turns")
    ax.plot(DAYS, ripe_opp, color=OPP_COLOR, label=f"{opp_label} ripe tile-turns")
    ax2 = ax.twinx()
    util_us = exec_us.get("ops_utilization_by_day") or [0] * SEASON_DAYS
    util_opp = exec_opp.get("ops_utilization_by_day") or [0] * SEASON_DAYS
    ax2.plot(DAYS, util_us, color=US_COLOR_LIGHT, linestyle="--", label=f"{us_label} util")
    ax2.plot(DAYS, util_opp, color=OPP_COLOR_LIGHT, linestyle="--", label=f"{opp_label} util")
    ax.set_title("Ripe-unharvested by day + ops utilization (dashed)")
    ax.set_ylabel("ripe tile-turns / day")
    ax2.set_ylabel("utilization", color="gray")
    ax.legend(loc="upper left", fontsize=7)
    ax2.legend(loc="upper right", fontsize=7)
    ax.grid(True, linestyle="--", alpha=0.35)


def _plot_revenue_spend(
    ax,
    mkt_us: dict[str, Any],
    mkt_opp: dict[str, Any],
    us_label: str,
    opp_label: str,
) -> None:
    rev_us = mkt_us.get("revenue_by_day") or [0] * SEASON_DAYS
    spend_us = mkt_us.get("spend_by_day") or [0] * SEASON_DAYS
    rev_opp = mkt_opp.get("revenue_by_day") or [0] * SEASON_DAYS
    spend_opp = mkt_opp.get("spend_by_day") or [0] * SEASON_DAYS
    ax.bar(DAYS, rev_us, color=US_COLOR, alpha=0.7, label=f"{us_label} revenue")
    ax.bar(DAYS, [-s for s in spend_us], color=US_COLOR_LIGHT, alpha=0.7, label=f"{us_label} spend")
    ax.bar(
        [d + 0.35 for d in DAYS],
        rev_opp,
        width=0.35,
        color=OPP_COLOR,
        alpha=0.7,
        label=f"{opp_label} revenue",
    )
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_title("Daily revenue (+) vs spend (−)")
    ax.set_ylabel("coins")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(True, axis="y", linestyle="--", alpha=0.35)


def _plot_fill_price_quality(ax, mkt: dict[str, Any], label: str) -> None:
    fill = mkt.get("fill_rate") or {}
    products = sorted(fill)
    if not products:
        ax.text(0.5, 0.5, "No fill data", ha="center", va="center")
        return
    x = np.arange(len(products))
    w = 0.2
    stock_lim = [fill[p].get("stock_limited_units", 0) for p in products]
    demand_lim = [fill[p].get("demand_limited_units", 0) for p in products]
    ax.bar(x - w, stock_lim, w, label="stock-limited", color="#ef5350")
    ax.bar(x, demand_lim, w, label="demand-limited", color="#ffa726")
    ax2 = ax.twinx()
    rvq = mkt.get("realized_vs_quote") or {}
    ax2.plot(
        x,
        [rvq.get(p, 0) for p in products],
        "o-",
        color=US_COLOR,
        label="realized/quote",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(products, rotation=45, ha="right", fontsize=8)
    ax.set_title(f"{label} — fill failures + realized/quote")
    ax.legend(loc="upper left", fontsize=7)
    ax2.legend(loc="upper right", fontsize=7)
    ax.grid(True, axis="y", linestyle="--", alpha=0.35)


def _plot_planner_cash(
    ax,
    plan_us: dict[str, Any],
    plan_opp: dict[str, Any],
    mkt_us: dict[str, Any],
    mkt_opp: dict[str, Any],
    us_label: str,
    opp_label: str,
) -> None:
    idle_us = plan_us.get("idle_tile_days") or {}
    idle_opp = plan_opp.get("idle_tile_days") or {}
    ax.bar(
        [0, 1, 2],
        [
            idle_us.get("empty", 0),
            idle_us.get("empty_structure", 0),
            idle_us.get("weed", 0),
        ],
        color=US_COLOR,
        alpha=0.7,
        label=f"{us_label} idle turns",
    )
    ax.bar(
        [0.4, 1.4, 2.4],
        [
            idle_opp.get("empty", 0),
            idle_opp.get("empty_structure", 0),
            idle_opp.get("weed", 0),
        ],
        color=OPP_COLOR,
        alpha=0.7,
        label=f"{opp_label} idle turns",
    )
    ax.set_xticks([0.2, 1.2, 2.2])
    ax.set_xticklabels(["empty", "empty_struct", "weed"])
    ax2 = ax.twinx()
    min_us = plan_us.get("min_cash_by_day") or [0] * SEASON_DAYS
    min_opp = plan_opp.get("min_cash_by_day") or [0] * SEASON_DAYS
    ax2.plot(DAYS, min_us, color=US_COLOR, linestyle="--", label=f"{us_label} min cash")
    ax2.plot(DAYS, min_opp, color=OPP_COLOR, linestyle="--", label=f"{opp_label} min cash")
    ax.set_title("Idle tile-turns (bars) + min cash by day (lines)")
    ax2.set_ylabel("min cash")
    ax.legend(loc="upper left", fontsize=7)
    ax2.legend(loc="upper right", fontsize=7)
    ax.grid(True, linestyle="--", alpha=0.35)


def _plot_kpi_table(
    ax,
    exec_k: dict[str, Any],
    mkt_k: dict[str, Any],
    plan_k: dict[str, Any],
    label: str,
) -> None:
    ax.axis("off")
    ripe = exec_k.get("ripe_unharvested") or {}
    noop = exec_k.get("noop_ops") or {}
    slot = mkt_k.get("order_slot_saturation") or {}
    hold = mkt_k.get("holding_time") or {}
    idle = plan_k.get("idle_tile_days") or {}
    hire = plan_k.get("hire_profile") or {}
    rows = [
        ["move_overhead", f"{exec_k.get('move_overhead', 0):.2f}"],
        ["noop_ops", str(noop.get("total", 0))],
        ["ripe_tile_turns", str(ripe.get("total_tile_turns", 0))],
        ["mean_harvest_latency", f"{ripe.get('mean_latency_turns', 0):.1f}"],
        ["uncollected_fert_turns", str(exec_k.get("uncollected_fertilizer_tile_turns", 0))],
        ["order_slot_saturation", f"{slot.get('saturation_rate', 0):.1%}"],
        ["holding_time_mean", f"{hold.get('mean_turns', 0):.1f}"],
        ["unexplained_delta", f"{mkt_k.get('unexplained_delta', 0):.0f}"],
        ["tile_day_utilization", f"{idle.get('tile_day_utilization', 0):.1%}"],
        ["total_hire_spend", str(hire.get("total_hire_spend", 0))],
        ["days_below_floor", str(plan_k.get("days_below_floor", 0))],
    ]
    table = ax.table(
        cellText=rows,
        colLabels=["KPI", label],
        loc="center",
        cellLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)
    ax.set_title(f"{label} — diagnostic KPIs", pad=12)


def plot_earnings_by_day(report: dict[str, Any], *, title: str | None = None) -> None:
    """Sell revenue + net cash by day (smoke-style; us player from replay)."""
    from smoke_analysis.plot import plot_earnings_by_day as _plot
    from replay_analysis.smoke_views import smoke_style_from_report

    _plot(smoke_style_from_report(report), title=title)


def plot_earnings_by_zone(report: dict[str, Any], *, title: str | None = None) -> None:
    """Zone×day harvest value heatmap (smoke-style; us player from replay)."""
    from smoke_analysis.plot import plot_earnings_by_zone as _plot
    from replay_analysis.smoke_views import smoke_style_from_report

    _plot(smoke_style_from_report(report), title=title)


def plot_worker_actions(report: dict[str, Any], *, title: str | None = None) -> None:
    """Worker×day hour-action heatmap (smoke-style; us player from replay)."""
    from smoke_analysis.plot import plot_worker_actions as _plot
    from replay_analysis.smoke_views import smoke_style_from_report

    _plot(smoke_style_from_report(report), title=title)


def plot_zone_capacity(report: dict[str, Any], *, title: str | None = None) -> None:
    """Per-zone daily ops vs net_tile_ops cap (replay; no dawn theo)."""
    from smoke_analysis.plot import plot_zone_capacity as _plot
    from replay_analysis.smoke_views import smoke_style_from_report

    _plot(
        smoke_style_from_report(report),
        title=title,
        compare_theo=False,
    )
