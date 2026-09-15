"""CP-SAT solver dispatch — flip CURRENT_SOLVER to compare backends."""

from __future__ import annotations

from collections.abc import Callable

from agent.solvers import monolithic, twoland_wsp, zonewise, zonewise_wsp
from agent.solvers.types import SolveResult

CURRENT_SOLVER = "twoland_wsp"  # "monolithic" | "zonewise" | "zonewise_wsp" | "twoland_wsp"

_BACKENDS = {
    "monolithic": monolithic,
    "zonewise": zonewise,
    "zonewise_wsp": zonewise_wsp,
    "twoland_wsp": twoland_wsp,
}


def _backend():
    try:
        return _BACKENDS[CURRENT_SOLVER]
    except KeyError as exc:
        raise ValueError(
            f"unknown CURRENT_SOLVER {CURRENT_SOLVER!r}; "
            f"expected one of {sorted(_BACKENDS)}"
        ) from exc


def _wsp_solver() -> bool:
    return CURRENT_SOLVER in ("zonewise_wsp", "twoland_wsp")


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
    w_open0: int = 0,
    f_open0: int = 0,
    cascade_reserve: bool = False,
    min_balance: int = 0,
    price_of: Callable[[str], int] | None = None,
    land_owned: bool = False,
    buy_morning: bool = False,
) -> SolveResult:
    kwargs = {
        "horizon": horizon,
        "empty_tiles": empty_tiles,
        "empty_counts": empty_counts,
        "locked_by_worker": locked_by_worker,
        "starting_money": starting_money,
        "max_time": max_time,
        "charge_hire_daily": charge_hire_daily,
        "track_shed": track_shed,
        "w_open0": w_open0,
        "f_open0": f_open0,
        "cascade_reserve": cascade_reserve,
        "min_balance": min_balance,
    }
    if price_of is not None:
        kwargs["price_of"] = price_of
    if CURRENT_SOLVER == "twoland_wsp":
        kwargs["land_owned"] = land_owned
        kwargs["buy_morning"] = buy_morning
    return _backend().solve(chains, **kwargs)


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
