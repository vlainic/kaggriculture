"""CP-SAT solver dispatch — flip CURRENT_SOLVER to compare backends."""

from __future__ import annotations

from agent.solvers import monolithic, zonewise
from agent.solvers.types import SolveResult

CURRENT_SOLVER = "monolithic"  # or "zonewise"

_BACKENDS = {
    "monolithic": monolithic,
    "zonewise": zonewise,
}


def _backend():
    try:
        return _BACKENDS[CURRENT_SOLVER]
    except KeyError as exc:
        raise ValueError(
            f"unknown CURRENT_SOLVER {CURRENT_SOLVER!r}; "
            f"expected one of {sorted(_BACKENDS)}"
        ) from exc


def solve(
    chains: list,
    *,
    horizon: int,
    empty_tiles: list[int],
    empty_counts: dict[str, int],
    locked_by_worker: dict[str, dict],
    starting_money: int,
    max_time: float = 20.0,
    charge_hire_daily: bool = True,
    track_shed: bool = True,
) -> SolveResult:
    return _backend().solve(
        chains,
        horizon=horizon,
        empty_tiles=empty_tiles,
        empty_counts=empty_counts,
        locked_by_worker=locked_by_worker,
        starting_money=starting_money,
        max_time=max_time,
        charge_hire_daily=charge_hire_daily,
        track_shed=track_shed,
    )


def apply_replan(
    result: SolveResult,
    replan_tiles: list[int],
    tile_queues: dict,
    tile_state: dict | None,
    horizon: int,
    chain_to_queue_items,
) -> int:
    return _backend().apply_replan(
        result,
        replan_tiles,
        tile_queues,
        tile_state,
        horizon,
        chain_to_queue_items,
    )
