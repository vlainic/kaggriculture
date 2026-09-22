"""Farmer-only WSP sandbox + replan Gantt — self-contained under milos/ (no agent/)."""

from __future__ import annotations

from typing import Any

__all__ = [
    "FARMER_TILES_FIVE",
    "SolveResult",
    "WspPlan",
    "accumulate_absolute",
    "load_wsp_plans",
    "parse_wsp_plan_lines",
    "plot_plan",
    "plot_planner_board_actions",
    "plot_zone_ops_replans",
    "solve",
]

_LAZY: dict[str, tuple[str, str]] = {
    "FARMER_TILES_FIVE": ("milos.wsp.farmer", "FARMER_TILES_FIVE"),
    "solve": ("milos.wsp.farmer", "solve"),
    "accumulate_absolute": ("milos.wsp.gantt", "accumulate_absolute"),
    "plot_zone_ops_replans": ("milos.wsp.gantt", "plot_zone_ops_replans"),
    "WspPlan": ("milos.wsp.log", "WspPlan"),
    "load_wsp_plans": ("milos.wsp.log", "load_wsp_plans"),
    "parse_wsp_plan_lines": ("milos.wsp.log", "parse_wsp_plan_lines"),
    "SolveResult": ("milos.wsp.types", "SolveResult"),
}


def plot_plan(*args, **kwargs):
    from milos.wsp.gantt import plot_plan as _plot

    return _plot(*args, **kwargs)


def plot_planner_board_actions(*args, **kwargs):
    from milos.wsp.plan_actions import plot_planner_board_actions as _plot

    return _plot(*args, **kwargs)


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        mod_name, attr = _LAZY[name]
        import importlib

        return getattr(importlib.import_module(mod_name), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
