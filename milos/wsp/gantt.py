"""Gantt charts for WSP assigned chains — milos-local, no agent imports."""

from __future__ import annotations

import matplotlib.pyplot as plt

from milos.wsp import data as rollouts
from milos.wsp.common import parse_profile_key
from milos.wsp.config import ANIMAL_NAMES, NUM_DAYS
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
