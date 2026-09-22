"""Planned actions from absolute planner board → worker×action heatmap (milos-local)."""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

from milos.wsp.common import parse_profile_key
from milos.wsp.config import NUM_DAYS
from milos.wsp import data as rollouts
from milos.zoning import FARMER, FARMER_TILES

HOURS_PER_DAY = 24
SEASON_DAYS = NUM_DAYS

ACTION_ORDER: tuple[str, ...] = (
    "PICKUP",
    "MOVE",
    "PLANT",
    "WATER",
    "FERTILIZE",
    "BUILD",
    "FEED",
    "CARE",
    "COLLECT",
    "HARVEST",
    "DIG",
    "PLACE",
    "DROP",
    "PASS",
    "OTHER",
)

ACTION_COLORS: dict[str, str] = {
    "PICKUP": "#6a1b9a",
    "MOVE": "#78909c",
    "PLANT": "#2e7d32",
    "WATER": "#0288d1",
    "FERTILIZE": "#00897b",
    "BUILD": "#5d4037",
    "FEED": "#f9a825",
    "CARE": "#ff8f00",
    "COLLECT": "#7b1fa2",
    "HARVEST": "#c62828",
    "DIG": "#795548",
    "PLACE": "#1565c0",
    "DROP": "#455a64",
    "PASS": "#cfd8dc",
    "OTHER": "#212121",
}

_MOVE_VERBS = frozenset({"NORTH", "SOUTH", "EAST", "WEST"})
_BUILD_VERBS = frozenset({"BUILD_COOP", "BUILD_PASTURE"})


def classify_action(verb: str) -> str:
    v = verb.upper()
    if v.startswith("PICKUP"):
        return "PICKUP"
    if v in _MOVE_VERBS:
        return "MOVE"
    if v in _BUILD_VERBS:
        return "BUILD"
    if v == "COLLECT_FERTILIZER":
        return "COLLECT"
    if v in ACTION_ORDER:
        return v
    return "OTHER"


def _actions_at_age(profile_key: str, age: int) -> list[str]:
    label, suffix = parse_profile_key(profile_key)
    crops = rollouts.crops()["crops"]
    if label in crops:
        days = crops[label][suffix]["days"]
    else:
        days = rollouts.animals()["animals"][label][suffix]["days"]
    for day in days:
        if int(day["age"]) == age:
            return list(day["actions"])
    return []


def board_planned_events(
    board: dict[int, list],
    *,
    worker: str = FARMER,
    tiles: tuple[int, ...] = FARMER_TILES,
) -> list[dict[str, Any]]:
    """Stamp rollout tape onto farmer snake order; sequential hours within each day."""
    events: list[dict[str, Any]] = []
    for cal_day in range(SEASON_DAYS):
        hour = 0
        for tile in tiles:
            if tile not in board:
                continue
            for profile_key, start_abs in board.get(tile) or []:
                age = cal_day - int(start_abs)
                if age < 0:
                    continue
                for verb in _actions_at_age(profile_key, age):
                    if hour >= HOURS_PER_DAY:
                        break
                    events.append(
                        {
                            "worker": worker,
                            "day": cal_day,
                            "hour": hour,
                            "verb": verb,
                            "bucket": classify_action(verb),
                            "tile": tile,
                        }
                    )
                    hour += 1
        while hour < HOURS_PER_DAY:
            events.append(
                {
                    "worker": worker,
                    "day": cal_day,
                    "hour": hour,
                    "verb": "PASS",
                    "bucket": "PASS",
                    "tile": None,
                }
            )
            hour += 1
    return events


def _placement_active(profile_key: str, age: int) -> bool:
    """True while age ≥ 0 and crop is still occupying the tile (animals stay forever)."""
    if age < 0:
        return False
    label, suffix = parse_profile_key(profile_key)
    crops = rollouts.crops()["crops"]
    if label in crops:
        return age < rollouts.tile_free_age(label, suffix)
    return True


def day_executor_io(
    board: dict[int, list],
    day: int,
    *,
    tiles: tuple[int, ...] = FARMER_TILES,
) -> dict[str, Any]:
    """Synthetic planned tape for one day (NOT live executor output).

    See ``milos.diagnostics.print_planner_executor_trace`` for real queue + step I/O.
    """
    inputs: list[dict[str, Any]] = []
    for tile in tiles:
        for profile_key, start_abs in board.get(tile) or []:
            age = day - int(start_abs)
            if not _placement_active(profile_key, age):
                continue
            ops = _actions_at_age(profile_key, age)
            inputs.append(
                {
                    "tile": tile,
                    "profile": profile_key,
                    "start": int(start_abs),
                    "age": age,
                    "ops": ops,
                }
            )

    outputs = [
        ev
        for ev in board_planned_events(board, tiles=tiles)
        if int(ev["day"]) == day
    ]
    return {"day": day, "input": inputs, "output": outputs}


def print_day_executor_io(
    board: dict[int, list],
    *,
    days: range | None = None,
    tiles: tuple[int, ...] = FARMER_TILES,
    show_pass: bool = False,
) -> None:
    """Print synthetic planned tape per day (heatmap model — not executor returns)."""
    day_range = days if days is not None else range(SEASON_DAYS)
    for day in day_range:
        io = day_executor_io(board, day, tiles=tiles)
        print(f"=== d={day} ===")
        print("INPUT (active placements → ops):")
        if not io["input"]:
            print("  (none)")
        else:
            for row in io["input"]:
                ops = ",".join(row["ops"]) if row["ops"] else "—"
                print(
                    f"  t{row['tile'] + 1} {row['profile']} "
                    f"start={row['start']} age={row['age']} ops=[{ops}]"
                )
        print("OUTPUT (executor hour tape):")
        shown = 0
        for ev in io["output"]:
            if not show_pass and ev["verb"] == "PASS":
                continue
            tile = f" t{ev['tile'] + 1}" if ev["tile"] is not None else ""
            print(f"  h{ev['hour']:02d} {ev['verb']}{tile}")
            shown += 1
        if shown == 0:
            print("  (all PASS)" if not show_pass else "  (none)")
        print()


def events_to_action_grid(
    events: list[dict[str, Any]],
    *,
    workers: tuple[str, ...] = (FARMER,),
    season_days: int = SEASON_DAYS,
) -> dict[str, Any]:
    worker_list = list(workers)
    worker_idx = {w: i for i, w in enumerate(worker_list)}
    n_actions = len(ACTION_ORDER)
    action_idx = {a: i for i, a in enumerate(ACTION_ORDER)}

    grid = np.full(
        (len(worker_list) * n_actions, season_days * HOURS_PER_DAY),
        np.nan,
        dtype=float,
    )
    for ev in events:
        worker = ev["worker"]
        if worker not in worker_idx:
            continue
        day, hour = int(ev["day"]), int(ev["hour"])
        if not (0 <= day < season_days and 0 <= hour < HOURS_PER_DAY):
            continue
        bucket = ev["bucket"]
        ai = action_idx.get(bucket, action_idx["OTHER"])
        row = worker_idx[worker] * n_actions + ai
        col = day * HOURS_PER_DAY + hour
        grid[row, col] = ai + 1

    return {
        "action_order": list(ACTION_ORDER),
        "action_colors": dict(ACTION_COLORS),
        "hours_per_day": HOURS_PER_DAY,
        "grid": grid,
        "events": events,
    }


def plot_planner_board_actions(
    board: dict[int, list],
    *,
    workers: tuple[str, ...] = (FARMER,),
    replan_day: int | None = None,
    title: str | None = None,
) -> None:
    """Nested heatmap like smoke_analysis.plot_worker_actions — planned tape from board."""
    events = board_planned_events(board)
    actions = events_to_action_grid(events, workers=workers)
    grid = actions["grid"]
    worker_list = list(workers)
    n_actions = len(ACTION_ORDER)
    n_workers = len(worker_list)

    if grid is None or n_workers == 0:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "no planned actions", ha="center", va="center")
        ax.axis("off")
        plt.show()
        return

    n_cols = SEASON_DAYS * HOURS_PER_DAY
    n_rows = n_workers * n_actions
    display = np.array(grid, dtype=float) - 1.0
    masked = np.ma.masked_invalid(display)

    cmap = ListedColormap([ACTION_COLORS[a] for a in ACTION_ORDER])
    cmap.set_bad("#ffffff")

    fig_w = max(20, SEASON_DAYS * 1.3)
    fig_h = max(6, n_workers * 0.7)
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

    if replan_day is not None and 0 <= replan_day < SEASON_DAYS:
        x = replan_day * HOURS_PER_DAY
        ax.axvline(x, color="#1565c0", ls="--", lw=1.2, label=f"replan d={replan_day}")

    ax.set_xticks([d * HOURS_PER_DAY + HOURS_PER_DAY / 2 for d in range(SEASON_DAYS)])
    ax.set_xticklabels([str(d) for d in range(SEASON_DAYS)])
    ax.set_yticks([w * n_actions + n_actions / 2 for w in range(n_workers)])
    ax.set_yticklabels(worker_list)
    ax.set_xlabel("day (24 hours per column block)")
    ax.set_ylabel("zone (15 action rows per block)")

    stem = title or "milos planner board"
    n_events = len(events)
    ax.set_title(f"{stem} — planned actions (hour × type) [{n_events} stamped]")

    legend_handles = [
        Patch(facecolor=ACTION_COLORS[a], edgecolor="#888888", label=a)
        for a in ACTION_ORDER
    ]
    if replan_day is not None:
        legend_handles.append(
            Patch(
                facecolor="none",
                edgecolor="#1565c0",
                linestyle="--",
                label=f"replan d={replan_day}",
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
