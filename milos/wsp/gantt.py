"""Gantt charts for WSP assigned chains — milos-local, no agent imports."""

from __future__ import annotations

import matplotlib.pyplot as plt

from milos.wsp import data as rollouts
from milos.wsp.common import parse_profile_key
from milos.wsp.config import ANIMAL_NAMES

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


def plot_plan(
    assigned: dict[int, list],
    *,
    replan_day: int = 0,
    horizon: int = 30,
    title: str | None = None,
    patterns: list | None = None,
) -> None:
    del patterns
    if not assigned:
        fig, ax = plt.subplots(figsize=(8, 2))
        ax.text(0.5, 0.5, "empty assignment", ha="center", va="center")
        ax.axis("off")
        plt.show()
        return

    tiles = sorted(assigned.keys())
    fig, ax = plt.subplots(figsize=(14, max(3, 0.55 * len(tiles) + 1)))
    season_end = replan_day + horizon

    for tile in tiles:
        y = tile + 1
        chain = assigned.get(tile) or []
        for profile_key, start in chain:
            label, suffix = parse_profile_key(profile_key)
            start_abs = replan_day + int(start)
            end_abs = _segment_end(label, suffix, start_abs, season_end)
            if end_abs <= start_abs:
                continue
            st = _style(label)
            ax.barh(
                y=y,
                width=end_abs - start_abs,
                left=start_abs,
                height=0.55,
                color=st["color"],
                hatch=st.get("hatch", ""),
                edgecolor="#333333",
                linewidth=0.8,
                alpha=0.95,
            )
            tag = f"{label[:3]}{start}"
            ax.text(
                start_abs + 0.12,
                y,
                tag,
                va="center",
                fontsize=7,
                color="#111",
            )

    ax.set_yticks([t + 1 for t in tiles], [f"t{t + 1}" for t in tiles])
    ax.set_xlim(replan_day - 0.5, season_end + 0.5)
    ax.set_xlabel("season day")
    ax.set_title(title or f"WSP plan d={replan_day} horizon={horizon}")
    ax.grid(axis="x", alpha=0.25)
    plt.tight_layout()
    plt.show()
