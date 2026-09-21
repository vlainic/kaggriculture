"""SolveResult — milos copy of agent/solvers/types.py (self-contained WSP sandbox)."""

from __future__ import annotations

from dataclasses import dataclass, field


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
    zone_outcomes: Per-worker cascade outcome — ok / infeasible / picks0 / empty.
    """

    assigned: dict[int, list]
    complete: bool
    solved_workers: tuple[str, ...]
    buy_land: bool = False
    zone_outcomes: dict[str, str] = field(default_factory=dict)
