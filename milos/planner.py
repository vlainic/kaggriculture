"""Farmer planner — solver result → absolute tile board for Gantt (no agent/)."""

from __future__ import annotations

from collections.abc import Callable

from milos.wsp import data as wsp_data
from milos.wsp.farmer import solve
from milos.wsp.log import WspPlan
from milos.wsp.types import SolveResult
from milos.zoning import FARMER, FARMER_TILES, NUM_DAYS

PlanBoard = dict[int, list]


def empty_board() -> PlanBoard:
    return {t: [] for t in FARMER_TILES}


def chains_to_absolute(replan_day: int, assigned_relative: dict[int, list]) -> PlanBoard:
    out: PlanBoard = {}
    for tile, chain in assigned_relative.items():
        out[tile] = [[pk, replan_day + int(start)] for pk, start in chain]
    return out


def board_for_plot(board: PlanBoard) -> PlanBoard:
    return {t: [list(pair) for pair in board.get(t, [])] for t in board}


def apply_solver_result(
    board: PlanBoard,
    replan_day: int,
    replan_tiles: list[int] | set[int],
    result: SolveResult,
) -> set[int]:
    """Write horizon-relative solver chains onto board as absolute starts."""
    delta: set[int] = set()
    tile_set = set(FARMER_TILES)
    for idx in replan_tiles:
        if idx not in tile_set:
            continue
        chain = result.assigned.get(idx)
        if chain is None:
            continue
        board[idx] = [[pk, replan_day + int(start)] for pk, start in chain]
        delta.add(idx)
    return delta


def merge_wsp_plan(
    board: PlanBoard,
    plan: WspPlan,
    *,
    tiles: set[int] | frozenset[int] | None = None,
) -> set[int]:
    """Apply one [wsp_plan] delta (relative starts) onto absolute board."""
    scope = set(tiles) if tiles is not None else set(FARMER_TILES)
    delta: set[int] = set()
    for tile, chain in plan.assigned.items():
        if tile not in scope:
            continue
        board[tile] = [[pk, plan.day + int(start)] for pk, start in chain]
        delta.add(tile)
    return delta


def build_day0(
    *,
    starting_money: int = 3000,
    max_time: float = 20.0,
    track_shed: bool = True,
    price_of: Callable[[str], int] | None = None,
    **kwargs,
) -> tuple[PlanBoard, SolveResult]:
    """Day-0 farmer solve → absolute board + raw SolveResult (relative chains)."""
    empty = list(FARMER_TILES)
    if price_of is None:
        base = wsp_data.i0_base_prices()
        price_of = lambda product, _base=base: _base[product]

    result = solve(
        [],
        horizon=NUM_DAYS,
        empty_tiles=empty,
        empty_counts={FARMER: len(empty)},
        starting_money=starting_money,
        max_time=max_time,
        track_shed=track_shed,
        price_of=price_of,
        **kwargs,
    )
    board = empty_board()
    apply_solver_result(board, 0, list(result.assigned), result)
    return board, result
