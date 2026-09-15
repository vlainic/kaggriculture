"""Matplotlib dashboard for smoke analysis reports."""

from __future__ import annotations

from collections import Counter
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

from smoke_analysis.load import SEASON_DAYS
from smoke_analysis.parse_actions import ACTION_COLORS, ACTION_ORDER, HOURS_PER_DAY

DAYS = list(range(SEASON_DAYS))
US_COLOR = "#1565c0"
LAND1_COLOR = "#42a5f5"
LAND2_COLOR = "#ef6c00"


def plot_smoke(report: dict[str, Any], *, title: str | None = None) -> None:
    stem = title or report.get("log_stem") or "smoke"
    reward = report.get("reward")
    fig = plt.figure(figsize=(16, 28))
    gs = fig.add_gridspec(7, 2, hspace=0.45, wspace=0.28)
    fig.suptitle(
        f"{stem}  reward={reward:.0f}" if reward is not None else stem,
        fontsize=11,
    )

    _plot_empties(fig.add_subplot(gs[0, :]), report)
    _plot_money(fig.add_subplot(gs[1, :]), report)
    _plot_passes(fig.add_subplot(gs[2, 0]), report)
    _plot_hires(fig.add_subplot(gs[2, 1]), report)
    _plot_planner_heatmap(fig.add_subplot(gs[3, :]), report)
    _plot_start_histogram(fig.add_subplot(gs[4, 0]), report)
    _plot_keep_timeline(fig.add_subplot(gs[4, 1]), report)
    _plot_acceptance(fig.add_subplot(gs[5, :]), report)
    _plot_infeasible(fig.add_subplot(gs[6, :]), report)

    plt.tight_layout()
    plt.show()


def _plot_empties(ax, report: dict[str, Any]) -> None:
    tiles = report.get("tiles") or {}
    empty_by_worker = tiles.get("empty_by_worker_by_day") or {}
    land2 = tuple(report.get("land2_workers") or ())
    land1 = tuple(
        report.get("land1_workers")
        or [w for w in (report.get("workers") or []) if w not in land2]
    )
    total_land1 = np.zeros(SEASON_DAYS)
    total_land2 = np.zeros(SEASON_DAYS)
    for w in land1:
        series = empty_by_worker.get(w) or [None] * SEASON_DAYS
        for d, v in enumerate(series):
            if v is not None:
                total_land1[d] += v
    for w in land2:
        series = empty_by_worker.get(w) or [None] * SEASON_DAYS
        for d, v in enumerate(series):
            if v is not None:
                total_land2[d] += v
    ax.fill_between(DAYS, 0, total_land1, alpha=0.7, color=LAND1_COLOR, label="land1 empty")
    if land2:
        ax.fill_between(
            DAYS,
            total_land1,
            total_land1 + total_land2,
            alpha=0.7,
            color=LAND2_COLOR,
            label="land2 empty",
        )
    buy_day = report.get("buy_land_day")
    if buy_day is not None:
        ax.axvline(buy_day, color="green", ls="--", lw=1, label=f"BUY_LAND d={buy_day}")
    title = "Dawn empty tiles"
    if land2:
        title += " (stacked land1 + land2)"
    ax.set_title(title)
    ax.set_xlabel("day")
    ax.set_ylabel("empty count")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_xlim(0, SEASON_DAYS - 1)


def _plot_money(ax, report: dict[str, Any]) -> None:
    money = (report.get("money") or {}).get("by_day") or []
    vals = [m if m is not None else np.nan for m in money]
    ax.plot(DAYS, vals, color=US_COLOR, marker="o", ms=3)
    buy_day = report.get("buy_land_day")
    if buy_day is not None:
        ax.axvline(buy_day, color="green", ls="--", lw=1)
    ax.set_title("Dawn cash (snap h=0)")
    ax.set_xlabel("day")
    ax.set_ylabel("money")
    ax.set_xlim(0, SEASON_DAYS - 1)


def _plot_passes(ax, report: dict[str, Any]) -> None:
    by_worker = (report.get("passes") or {}).get("by_worker") or {}
    bottom = np.zeros(SEASON_DAYS)
    for worker in sorted(by_worker):
        vals = np.array(by_worker[worker][:SEASON_DAYS], dtype=float)
        ax.bar(DAYS, vals, bottom=bottom, label=worker, width=0.8)
        bottom += vals
    ax.set_title("PASS counts by worker")
    ax.set_xlabel("day")
    ax.legend(fontsize=6, ncol=2)


def _plot_hires(ax, report: dict[str, Any]) -> None:
    hires = (report.get("hires") or {}).get("by_day") or [0] * SEASON_DAYS
    ax.bar(DAYS, hires[:SEASON_DAYS], color=US_COLOR, width=0.8)
    buy_day = report.get("buy_land_day")
    if buy_day is not None:
        ax.axvline(buy_day, color="green", ls="--", lw=1)
    ax.set_title("HIRE count by day")
    ax.set_xlabel("day")


def _plot_planner_heatmap(ax, report: dict[str, Any]) -> None:
    planner = report.get("planner") or {}
    solves = planner.get("zone_solves") or []
    workers = sorted({z["worker"] for z in solves})
    replan_days = sorted({z.get("day") for z in solves if z.get("day") is not None})
    if not workers or not replan_days:
        ax.text(0.5, 0.5, "no planner zone solves", ha="center", va="center")
        ax.axis("off")
        return
    w_idx = {w: i for i, w in enumerate(workers)}
    d_idx = {d: i for i, d in enumerate(replan_days)}
    grid = np.full((len(workers), len(replan_days)), np.nan)
    for zs in solves:
        day = zs.get("day")
        if day not in d_idx:
            continue
        wi = w_idx[zs["worker"]]
        di = d_idx[day]
        if zs.get("skipped") or zs.get("status") == "INFEASIBLE":
            grid[wi, di] = -1
        elif zs.get("write_anyway"):
            grid[wi, di] = 0.5
        else:
            grid[wi, di] = float(zs.get("picks") or 0)
    im = ax.imshow(grid, aspect="auto", cmap="RdYlGn", vmin=-1, vmax=16)
    ax.set_yticks(range(len(workers)), workers)
    ax.set_xticks(range(len(replan_days)), replan_days)
    ax.set_xlabel("replan day")
    ax.set_title("Zone picks per replan (-1=INFEASIBLE/skip, 0.5=thin write)")
    plt.colorbar(im, ax=ax, fraction=0.02)


def _plot_start_histogram(ax, report: dict[str, Any]) -> None:
    hist: Counter[int] = Counter()
    for zs in (report.get("planner") or {}).get("zone_solves") or []:
        for start_day, count in (zs.get("starts_hist") or {}).items():
            hist[int(start_day)] += int(count)
    if not hist:
        ax.text(0.5, 0.5, "no start histograms", ha="center", va="center")
        ax.axis("off")
        return
    xs = sorted(hist)
    ys = [hist[x] for x in xs]
    ax.bar(xs, ys, color=US_COLOR, width=0.8)
    ax.set_title("Aggregate start_day histogram")
    ax.set_xlabel("start_day offset")
    ax.set_ylabel("pick count")


def _plot_keep_timeline(ax, report: dict[str, Any]) -> None:
    keep = (report.get("planner") or {}).get("keep_assignments") or []
    tile_min = int(report.get("land2_tile_min") or 26)
    if not (report.get("land2_workers") or []):
        ax.text(0.5, 0.5, "one-land layout (no land2 keep)", ha="center", va="center")
        ax.axis("off")
        return
    land2 = [k for k in keep if k["tile"] >= tile_min]
    if not land2:
        ax.text(0.5, 0.5, "no land2 keep assignments", ha="center", va="center")
        ax.axis("off")
        return
    tiles = sorted({k["tile"] for k in land2})
    t_idx = {t: i for i, t in enumerate(tiles)}
    for k in land2:
        day = k.get("day") or 0
        ax.scatter(day, t_idx[k["tile"]], c="red", s=20, alpha=0.7)
    ax.set_yticks(range(len(tiles)), [f"t{t}" for t in tiles])
    ax.set_xlabel("replan day")
    ax.set_title("Land2 keep assignments")
    ax.set_xlim(-0.5, SEASON_DAYS - 0.5)


def _plot_acceptance(ax, report: dict[str, Any]) -> None:
    kpi = report.get("kpi") or {}
    acceptance = kpi.get("acceptance") or {}
    idle = kpi.get("idle_proxy") or {}
    stuck = kpi.get("stuck_zones") or {}
    rows = []
    for name, check in acceptance.items():
        if isinstance(check, dict):
            mark = "PASS" if check.get("pass") else "FAIL"
            rows.append([name, mark, check.get("detail", "")])
    rows.append(["mean_empty_per_dawn", "-", f"{idle.get('mean_empty_per_dawn', 0):.1f}"])
    rows.append(["hire5_empty_days", "-", str(idle.get("hire5_empty_days", 0))])
    rows.append(["max_hire5_empty_streak", "-", str(idle.get("max_hire5_empty_streak", 0))])
    rows.append(["stuck_workers", "-", ",".join(stuck.get("workers_stuck") or []) or "-"])
    rows.append(["stuck_healed_quick", "-", ",".join(stuck.get("workers_healed_within_n_days") or []) or "-"])
    rows.append(["stuck_permanent", "-", ",".join(stuck.get("workers_permanent_or_slow") or []) or "-"])
    rows.append(["seed", "-", str(report.get("seed") or "-")])
    rows.append(["smoke_passed", "-", str(report.get("smoke_passed"))])
    ax.axis("off")
    table = ax.table(
        cellText=rows,
        colLabels=["check", "result", "detail"],
        loc="center",
        cellLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.3)
    ax.set_title("Acceptance checklist + idle proxy", pad=12)


def plot_earnings_by_day(report: dict[str, Any], *, title: str | None = None) -> None:
    """Bar chart of sell revenue per day (+ net cash delta line)."""
    earnings = report.get("earnings") or {}
    sell = earnings.get("sell_revenue_by_day") or [0] * SEASON_DAYS
    net = earnings.get("net_cash_by_day") or [0] * SEASON_DAYS
    stem = title or report.get("log_stem") or "smoke"
    sell_label = "sell revenue"
    if not earnings.get("sell_rev_logged"):
        sell_label = "sell revenue (re-run smoke for sell_rev logs)"

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.bar(DAYS, sell[:SEASON_DAYS], color=US_COLOR, alpha=0.75, label=sell_label)
    ax.plot(DAYS, net[:SEASON_DAYS], color="#c62828", marker="o", ms=3, lw=1.2, label="net cash Δ dawn")
    buy_day = report.get("buy_land_day")
    if buy_day is not None:
        ax.axvline(buy_day, color="green", ls="--", lw=1, label=f"BUY_LAND d={buy_day}")
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_title(f"{stem} — earnings per day")
    ax.set_xlabel("day")
    ax.set_ylabel("coins")
    ax.set_xlim(0, SEASON_DAYS - 1)
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", linestyle="--", alpha=0.35)
    plt.tight_layout()
    plt.show()


def plot_earnings_by_zone(report: dict[str, Any], *, title: str | None = None) -> None:
    """Gantt-style heatmap: zones × days, color = harvest × base price."""
    earnings = report.get("earnings") or {}
    by_worker = earnings.get("harvest_by_worker_by_day") or {}
    workers = report.get("workers") or sorted(by_worker)
    stem = title or report.get("log_stem") or "smoke"

    fig, ax = plt.subplots(figsize=(14, 6))
    if not by_worker or not any(sum(v) > 0 for v in by_worker.values()):
        ax.text(0.5, 0.5, "no harvest earnings parsed", ha="center", va="center")
        ax.axis("off")
        plt.show()
        return

    grid = np.zeros((len(workers), SEASON_DAYS))
    for i, worker in enumerate(workers):
        grid[i] = (by_worker.get(worker) or [0] * SEASON_DAYS)[:SEASON_DAYS]

    cmap = plt.colormaps["turbo"].copy()
    cmap.set_bad("#eceff1")
    masked = np.ma.masked_where(grid <= 0, grid)

    im = ax.imshow(
        masked,
        aspect="auto",
        cmap=cmap,
        interpolation="nearest",
        origin="upper",
        extent=(-0.5, SEASON_DAYS - 0.5, len(workers) - 0.5, -0.5),
    )
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("harvest × base price (coins)")

    ax.set_yticks(range(len(workers)), workers)
    ax.set_xticks(DAYS[::2], DAYS[::2])
    ax.set_xlabel("day")
    ax.set_ylabel("zone")

    buy_day = report.get("buy_land_day")
    if buy_day is not None:
        ax.axvline(buy_day, color="white", ls="--", lw=1.5, alpha=0.9)
        ax.axvline(buy_day, color="#2e7d32", ls="--", lw=1, label=f"BUY_LAND d={buy_day}")

    earn_logged = (report.get("earnings") or {}).get("earn_logged")
    n_events = sum((report.get("earnings") or {}).get("harvest_events_by_worker", {}).values())
    title_suffix = f" ({n_events} harvest/collect events)"
    if earn_logged is False:
        title_suffix = " (re-run smoke for earn= logs)"
    ax.set_title(f"{stem} — zone harvest earnings (Gantt view){title_suffix}")
    ax.set_xlim(-0.5, SEASON_DAYS - 0.5)
    if buy_day is not None:
        ax.legend(fontsize=8, loc="upper right")
    plt.tight_layout()
    plt.show()


def plot_worker_actions(report: dict[str, Any], *, title: str | None = None) -> None:
    """Nested heatmap: each worker×day cell is hour×action_type."""
    actions = report.get("actions") or {}
    grid = actions.get("grid")
    workers = report.get("workers") or []
    stem = title or report.get("log_stem") or report.get("replay_stem") or "smoke"
    n_actions = len(ACTION_ORDER)
    n_workers = len(workers)

    if grid is None or n_workers == 0:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "no worker actions parsed", ha="center", va="center")
        ax.axis("off")
        plt.show()
        return

    n_cols = SEASON_DAYS * HOURS_PER_DAY
    n_rows = n_workers * n_actions
    display = np.array(grid, dtype=float) - 1.0  # 0..14 for ListedColormap
    masked = np.ma.masked_invalid(display)

    cmap = ListedColormap([ACTION_COLORS[a] for a in ACTION_ORDER])
    cmap.set_bad("#ffffff")

    fig_w = max(20, SEASON_DAYS * 1.3)
    fig_h = max(10, n_workers * 0.7)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)

    ax.imshow(
        masked,
        aspect="auto",
        interpolation="nearest",
        origin="upper",
        cmap=cmap,
        vmin=0,
        vmax=n_actions - 1,
        extent=(0, n_cols, n_rows, 0),
    )

    for d in range(1, SEASON_DAYS):
        ax.axvline(d * HOURS_PER_DAY, color="#bdbdbd", lw=0.8)
    for w in range(1, n_workers):
        ax.axhline(w * n_actions, color="#bdbdbd", lw=0.8)
    ax.axvline(0, color="#757575", lw=1.0)
    ax.axhline(0, color="#757575", lw=1.0)

    buy_day = report.get("buy_land_day")
    if buy_day is not None:
        x = buy_day * HOURS_PER_DAY
        ax.axvline(x, color="#2e7d32", ls="--", lw=1.2, label=f"BUY_LAND d={buy_day}")

    ax.set_xticks([d * HOURS_PER_DAY + HOURS_PER_DAY / 2 for d in range(SEASON_DAYS)])
    ax.set_xticklabels([str(d) for d in range(SEASON_DAYS)])
    ax.set_yticks([w * n_actions + n_actions / 2 for w in range(n_workers)])
    ax.set_yticklabels(workers)
    ax.set_xlabel("day (24 hours per column block)")
    ax.set_ylabel("zone (15 action rows per block)")

    n_events = len(actions.get("events") or [])
    ax.set_title(f"{stem} — worker actions (hour × type) [{n_events} events]")

    legend_handles = [
        Patch(facecolor=ACTION_COLORS[a], edgecolor="#888888", label=a)
        for a in ACTION_ORDER
    ]
    if buy_day is not None:
        legend_handles.append(
            Patch(
                facecolor="none",
                edgecolor="#2e7d32",
                linestyle="--",
                label=f"BUY_LAND d={buy_day}",
            )
        )
    ax.legend(
        handles=legend_handles,
        loc="upper left",
        bbox_to_anchor=(1.01, 1),
        fontsize=7,
        frameon=True,
    )

    plt.tight_layout()
    plt.show()


def _plot_infeasible(ax, report: dict[str, Any]) -> None:
    infeas = (report.get("planner") or {}).get("infeasible") or []
    if not infeas:
        ax.text(0.5, 0.5, "no INFEASIBLE zone lines", ha="center", va="center")
        ax.axis("off")
        return
    workers = sorted({x["worker"] for x in infeas})
    w_idx = {w: i for i, w in enumerate(workers)}
    for x in infeas:
        day = x.get("day") or 0
        ax.scatter(day, w_idx[x["worker"]], c="crimson", s=30, alpha=0.8)
        if x.get("empty") == 1:
            ax.annotate("e=1", (day, w_idx[x["worker"]]), fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.set_yticks(range(len(workers)), workers)
    ax.set_xlabel("replan day")
    ax.set_title("INFEASIBLE events (e=1 = leftover tile)")
    ax.set_xlim(-0.5, SEASON_DAYS - 0.5)
