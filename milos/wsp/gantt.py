"""Gantt charts for WSP assigned chains — milos-local, no agent imports."""

from __future__ import annotations

import matplotlib.pyplot as plt

from milos.wsp import data as rollouts
from milos.wsp.common import parse_profile_key
from milos.wsp.config import ANIMAL_NAMES, FARMER, FARMER_NET_TILE_OPS, NUM_DAYS
from milos.wsp.log import WspPlan

CROP_STYLE: dict[str, dict[str, str]] = {
    "WHEAT": {"color": "#e8c84a", "hatch": "///"},
    "CARROT": {"color": "#e8913a", "hatch": "+++"},
    "TOMATO": {"color": "#8bc34a", "hatch": "xxx"},
    "MELON": {"color": "#2e7d32", "hatch": "ooo"},
    "STRAWBERRY": {"color": "#d94f4f", "hatch": "..."},
}
ANIMAL_STYLE: dict[str, dict[str, str]] = {
    "SHEEP": {"color": "#bdbdbd", "hatch": "\\\\\\"},
    "COW": {"color": "#8d6e63", "hatch": "|||"},
    "GOOSE": {"color": "#eceff1", "hatch": "---"},
}

ALPHA_PAST = 0.2
ALPHA_FUTURE = 0.4
ALPHA_DELTA = 1.0


def _style(label: str) -> dict[str, str]:
    if label in CROP_STYLE:
        return CROP_STYLE[label]
    if label in ANIMAL_STYLE:
        return ANIMAL_STYLE[label]
    return {"color": "#999999", "hatch": ""}


def _segment_end(label: str, suffix: str, start_abs: int, season_end: int) -> int:
    if label in ANIMAL_NAMES or suffix in ("no_care", "with_care"):
        return season_end
    span = rollouts.tile_free_age(label, suffix)
    return min(season_end, start_abs + span)


def _draw_span(
    ax,
    *,
    y: float,
    left: float,
    right: float,
    st: dict[str, str],
    alpha: float,
    label: str | None = None,
) -> None:
    if right <= left:
        return
    ax.barh(
        y=y,
        width=right - left,
        left=left,
        height=0.55,
        color=st["color"],
        hatch=st.get("hatch", ""),
        edgecolor="#333333",
        linewidth=0.8,
        alpha=alpha,
    )
    if label is not None:
        ax.text(
            left + 0.12,
            y,
            label,
            va="center",
            fontsize=7,
            color="#111",
            alpha=min(1.0, alpha + 0.25),
        )


def accumulate_absolute(
    plans: list[WspPlan],
    *,
    tiles: set[int] | None = None,
) -> list[tuple[WspPlan, dict[int, list], set[int]]]:
    """Merge successive [wsp_plan] deltas into full absolute-start boards.

    Returns (plan, full_assigned, delta_tiles) per event.
    """
    state: dict[int, list] = {}
    out: list[tuple[WspPlan, dict[int, list], set[int]]] = []
    for plan in plans:
        delta: set[int] = set()
        for tile, chain in plan.assigned.items():
            if tiles is not None and tile not in tiles:
                continue
            state[tile] = [[pk, plan.day + int(start)] for pk, start in chain]
            delta.add(tile)
        snap = {t: [list(pair) for pair in chain] for t, chain in state.items()}
        out.append((plan, snap, delta))
    return out


def plot_plan(
    assigned: dict[int, list],
    *,
    replan_day: int = 0,
    horizon: int = 30,
    title: str | None = None,
    patterns: list | None = None,
    now: int | None = None,
    absolute: bool = False,
    delta_tiles: set[int] | None = None,
) -> None:
    """Full-season Gantt: past=0.3, unchanged future=0.6, delta future=1.0."""
    del patterns
    if not assigned:
        fig, ax = plt.subplots(figsize=(8, 2))
        ax.text(0.5, 0.5, "empty assignment", ha="center", va="center")
        ax.axis("off")
        plt.show()
        return

    cut = replan_day if now is None else now
    changed = delta_tiles or set()
    tiles = sorted(assigned.keys())
    fig, ax = plt.subplots(figsize=(14, max(3, 0.55 * len(tiles) + 1)))
    season_end = max(NUM_DAYS, replan_day + horizon, cut + 1)

    for tile in tiles:
        y = tile + 1
        fut_alpha = ALPHA_DELTA if tile in changed else ALPHA_FUTURE
        chain = assigned.get(tile) or []
        for profile_key, start in chain:
            label, suffix = parse_profile_key(profile_key)
            start_abs = int(start) if absolute else replan_day + int(start)
            end_abs = _segment_end(label, suffix, start_abs, season_end)
            if end_abs <= start_abs:
                continue
            st = _style(label)
            tag = f"{label[:3]}{start_abs if absolute else start}"

            if end_abs <= cut:
                _draw_span(
                    ax, y=y, left=start_abs, right=end_abs, st=st, alpha=ALPHA_PAST, label=tag
                )
            elif start_abs >= cut:
                _draw_span(
                    ax,
                    y=y,
                    left=start_abs,
                    right=end_abs,
                    st=st,
                    alpha=fut_alpha,
                    label=tag,
                )
            else:
                _draw_span(
                    ax, y=y, left=start_abs, right=cut, st=st, alpha=ALPHA_PAST, label=tag
                )
                _draw_span(
                    ax, y=y, left=cut, right=end_abs, st=st, alpha=fut_alpha, label=None
                )

    ax.axvline(cut, color="#616161", ls="--", lw=1, alpha=0.7)
    ax.set_yticks([t + 1 for t in tiles], [f"t{t + 1}" for t in tiles])
    ax.set_xlim(-0.5, season_end + 0.5)
    ax.set_xlabel("season day")
    ax.set_title(title or f"WSP plan d={replan_day} horizon={horizon}")
    ax.grid(axis="x", alpha=0.25)
    plt.tight_layout()
    plt.show()


def _profile_days(profile_key: str) -> list:
    label, suffix = parse_profile_key(profile_key)
    crops = rollouts.crops()["crops"]
    if label in crops:
        return crops[label][suffix]["days"]
    animals = rollouts.animals()["animals"]
    if label in animals:
        return animals[label][suffix]["days"]
    raise KeyError(profile_key)


def placement_daily_tile_ops(
    profile_key: str,
    start_abs: int,
    *,
    season_days: int = NUM_DAYS,
) -> list[int]:
    """Stamp rollout actions onto absolute season days (MIP daily_tile_ops)."""
    days = _profile_days(profile_key)
    ops = [0] * season_days
    for day in days:
        cal = int(start_abs) + int(day["age"])
        if cal >= season_days:
            break
        if cal < 0:
            continue
        ops[cal] += len(day["actions"])
    return ops


def zone_daily_tile_ops(
    assigned: dict[int, list],
    tiles: set[int] | frozenset[int] | tuple[int, ...] | list[int],
    *,
    season_days: int = NUM_DAYS,
) -> list[int]:
    """Sum planned daily_tile_ops across tiles in a zone (absolute starts)."""
    tile_set = set(tiles)
    total = [0] * season_days
    for tile, chain in assigned.items():
        if tile not in tile_set:
            continue
        for profile_key, start in chain or []:
            for d, n in enumerate(
                placement_daily_tile_ops(profile_key, int(start), season_days=season_days)
            ):
                total[d] += n
    return total


def plot_zone_ops_replans(
    plans: list[WspPlan],
    zones: dict[str, set[int] | frozenset[int] | tuple[int, ...] | list[int]],
    *,
    season_days: int = NUM_DAYS,
    ops_limits: dict[str, int] | None = None,
    cmap_name: str = "turbo",
    title: str | None = None,
) -> None:
    """Per-zone OPS over days: one line+dots per replan (color = replan day).

    Uses accumulate_absolute boards; each line is zone total daily_tile_ops from
    that replan day through season end. Colorbar is fixed to season days 0..(N-2)
    (0–28 for a 30-day season), independent of the last replan.
    """
    if not plans:
        fig, ax = plt.subplots(figsize=(8, 2))
        ax.text(0.5, 0.5, "no wsp_plan events", ha="center", va="center")
        ax.axis("off")
        plt.show()
        return

    scope = set()
    for tiles in zones.values():
        scope |= set(tiles)
    snaps = accumulate_absolute(plans, tiles=scope or None)
    # same idea as Gantt: skip events with empty delta in scoped tiles
    snaps = [(p, a, d) for p, a, d in snaps if d]
    zone_names = [name for name, tiles in zones.items() if tiles]
    active: list[str] = []
    for name in zone_names:
        tile_set = set(zones[name])
        if any(tile_set & set(assigned) for _, assigned, _ in snaps):
            active.append(name)
    if not active or not snaps:
        fig, ax = plt.subplots(figsize=(8, 2))
        ax.text(0.5, 0.5, "no zone tiles in plans", ha="center", va="center")
        ax.axis("off")
        plt.show()
        return

    limits = dict(ops_limits or {})
    if FARMER in active and FARMER not in limits:
        limits[FARMER] = FARMER_NET_TILE_OPS

    # Fixed season-day color scale (0..28 for NUM_DAYS=30), not replan-index.
    cbar_vmax = max(1, season_days - 2)
    cmap = plt.colormaps[cmap_name]
    norm = plt.Normalize(vmin=0, vmax=cbar_vmax)

    fig, axes = plt.subplots(
        len(active),
        1,
        sharex=True,
        figsize=(14, max(2.4, 1.8 * len(active) + 0.8)),
        squeeze=False,
        layout="constrained",
    )
    for zi, name in enumerate(active):
        ax = axes[zi][0]
        tile_set = set(zones[name])
        for plan, assigned, _delta in snaps:
            ops = zone_daily_tile_ops(assigned, tile_set, season_days=season_days)
            d0 = min(max(0, int(plan.day)), season_days - 1)
            xs = list(range(d0, season_days))
            ys = ops[d0:season_days]
            ax.plot(xs, ys, "-o", color=cmap(norm(plan.day)), ms=3.5, lw=1.3, alpha=0.9)
        if name in limits:
            cap = int(limits[name])
            ax.axhline(
                cap,
                color="#c62828",
                ls="--",
                lw=1.4,
                alpha=0.9,
                label=f"net_tile_ops={cap}",
            )
            # ax.legend(loc="upper right", fontsize=8, framealpha=0.85)
        ax.set_ylabel(name, fontsize=9)
        ax.set_ylim(bottom=0)
        ax.grid(axis="x", alpha=0.25)
        ax.grid(axis="y", alpha=0.2)

    axes[-1][0].set_xlabel("season day")
    axes[-1][0].set_xlim(-0.5, season_days - 0.5)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(
        sm,
        ax=axes.ravel().tolist(),
        location="right",
        fraction=0.035,
        pad=0.04,
        aspect=30,
    )
    tick_step = 7 if cbar_vmax >= 28 else max(1, cbar_vmax // 4)
    ticks = list(range(0, cbar_vmax + 1, tick_step))
    if ticks[-1] != cbar_vmax:
        ticks.append(cbar_vmax)
    cbar.set_ticks(ticks)
    cbar.set_label("replan day")
    fig.suptitle(title or "Zone OPS by replan (line+dots = planned daily_tile_ops)")
    plt.show()
