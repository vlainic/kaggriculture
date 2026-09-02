"""Shared solver result types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SolveResult:
    """Result from a solver.

    assigned: Tile index -> chain assignments. Always safe to use for tiles
              present in the dict.
    complete: True if all zones succeeded. False if any zone failed
              (zonewise) or problem was infeasible (monolithic).
              Even when False, assigned may contain valid partial results.
    solved_workers: Workers that successfully solved. Empty on full failure.
                    Zonewise uses this for conservative handoff; apply_replan
                    writes only tiles in the solved prefix (farmer first).
    """

    assigned: dict[int, list]
    complete: bool
    solved_workers: tuple[str, ...]
    buy_land: bool = False
