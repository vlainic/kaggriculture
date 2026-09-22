"""Milos farmer-only submission + WSP sandbox."""

from __future__ import annotations

from typing import Any

from milos.zoning import FARMER, FARMER_TILES, NUM_TILES, WORKERS, WORKER_TILES, worker_for_tile

__all__ = [
    "FARMER",
    "FARMER_TILES",
    "NUM_TILES",
    "PlanBoard",
    "WORKERS",
    "WORKER_TILES",
    "apply_solver_result",
    "board_for_plot",
    "build_day0",
    "chains_to_absolute",
    "empty_board",
    "merge_wsp_plan",
    "worker_for_tile",
]

_PLANNER_EXPORTS = frozenset({
    "PlanBoard",
    "apply_solver_result",
    "board_for_plot",
    "build_day0",
    "chains_to_absolute",
    "empty_board",
    "merge_wsp_plan",
})


def __getattr__(name: str) -> Any:
    if name in _PLANNER_EXPORTS:
        from milos import planner

        return getattr(planner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
