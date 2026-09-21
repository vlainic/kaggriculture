"""Farmer planner — solver result → absolute tile board for Gantt (no agent/)."""

from __future__ import annotations

from collections.abc import Callable

from milos.wsp import data as wsp_data
from milos.wsp.farmer import solve
from milos.wsp.log import WspPlan
from milos.wsp.types import SolveResult
from milos.wsp.config import ANIMAL_NAMES, NUM_DAYS, PROFILE_SUFFIXES
from milos.zoning import FARMER, FARMER_TILES, NUM_TILES, WORKER_TILES, WORKERS

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


# --- submission game loop ---

import json

from milos import rollouts
from milos.flags import VERBOSE

CURRENT_SOLVER = "milos_farmer"
STARTING_MONEY = 3000
NUM_ACTIVE_HIRES = 0
BUY_LAND_DAY: int | None = None
DEAD_HANDS: set[str] = set()
_cached_queues: dict | None = None


def replan(obs: dict, tile_queues: dict, tile_state: dict | None = None) -> None:
    del obs, tile_queues, tile_state
    return


def is_buy_morning_locked(tile, idx: int, day: int, me: dict) -> bool:
    del tile, idx, day, me
    return False


def _parse_profile_key(profile_key: str) -> tuple[str, str]:
    for suffix in PROFILE_SUFFIXES:
        token = f"_{suffix}"
        if profile_key.endswith(token):
            return profile_key[: -len(token)], suffix
    raise ValueError(f"unknown profile key: {profile_key}")


def _occupancy_end(profile_key: str, start_day: int, horizon: int) -> int:
    label, profile_name = _parse_profile_key(profile_key)
    if label in ANIMAL_NAMES:
        return horizon
    return start_day + rollouts.tile_free_age(label, profile_name)


def _log_wsp_plan(
    day: int,
    horizon: int,
    result: SolveResult,
    assigned: dict[int, list],
) -> None:
    if not VERBOSE or not assigned:
        return
    payload = {str(k): v for k, v in assigned.items()}
    print(
        f"[wsp_plan] d={day} horizon={horizon} solver={CURRENT_SOLVER} "
        f"complete={int(result.complete)} assigned={json.dumps(payload)}",
        flush=True,
    )


def chain_to_queue_items(chain: list, horizon: int = NUM_DAYS) -> list:
    from milos.script import QueueItem

    if not chain:
        return []

    items = []
    for i, (profile_key, start_day) in enumerate(chain):
        label, profile_name = _parse_profile_key(profile_key)
        kind: str = "animal" if label in ANIMAL_NAMES else "crop"
        dig_before = (
            i > 0
            and _parse_profile_key(chain[i - 1][0])[0] == "STRAWBERRY"
            and label == "CARROT"
        )
        items.append(
            QueueItem(
                kind=kind,
                label=label,
                profile=profile_name,
                start_lag=start_day if i == 0 else 0,
                replant_gap=0,
                dig_before=dig_before,
            )
        )
        if i > 0:
            prev_key, prev_start = chain[i - 1]
            prev_end = _occupancy_end(prev_key, prev_start, horizon)
            items[i - 1] = QueueItem(
                kind=items[i - 1].kind,
                label=items[i - 1].label,
                profile=items[i - 1].profile,
                start_lag=items[i - 1].start_lag,
                replant_gap=max(0, start_day - prev_end),
                dig_before=items[i - 1].dig_before,
            )
    return items


def _build_from_solver() -> dict[int, list]:
    _board, result = build_day0(starting_money=STARTING_MONEY, max_time=20.0)
    if not result.solved_workers or result.solved_workers[0] != WORKERS[0]:
        active = ",".join(result.solved_workers) or "none"
        raise RuntimeError(f"day-0 {CURRENT_SOLVER} farmer failed: active={active}")

    queues = {idx: [] for idx in range(NUM_TILES)}
    for worker in result.solved_workers:
        for idx in WORKER_TILES[worker]:
            chain = result.assigned.get(idx, [])
            queues[idx] = chain_to_queue_items(chain, NUM_DAYS)

    if not result.complete:
        active = ",".join(result.solved_workers)
        print(f"[planner] day-0 partial active={active}", flush=True)
    _log_wsp_plan(0, NUM_DAYS, result, dict(result.assigned))
    return queues


def get_tile_queues(fallback: Callable[[], dict]) -> dict:
    global _cached_queues
    if _cached_queues is None:
        try:
            _cached_queues = _build_from_solver()
        except (RuntimeError, OSError, ValueError, KeyError, TypeError) as exc:
            print(f"[planner] fallback to script queues: {exc}", flush=True)
            _cached_queues = fallback()
    return _cached_queues
