"""Shared solver result types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SolveResult:
    """Result from a solver.

    assigned: Tile index -> chain assignments. Always safe to use.
    complete: True if all zones succeeded. False if any zone failed
              (zonewise) or problem was infeasible (monolithic).
              Even when False, assigned may contain valid partial results.
    solved_workers: Workers that successfully solved. Empty on full failure.
                    Used by zonewise for conservative handoff tracking.
    """

    assigned: dict[int, list]
    complete: bool
    solved_workers: tuple[str, ...]
