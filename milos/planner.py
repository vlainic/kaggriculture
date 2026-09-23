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

from milos import animal_rollouts, rollouts
from milos.flags import VERBOSE

SEASON_LAST_DAY = 29

CURRENT_SOLVER = "milos_farmer"
STARTING_MONEY = 3000
NUM_ACTIVE_HIRES = 0
BUY_LAND_DAY: int | None = None
DEAD_HANDS: set[str] = set()
_cached_queues: dict | None = None


def _opponent_product_tile_counts(opp_farm: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in opp_farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            kind = tile.get("kind")
            if kind == "PLANT":
                crop = tile.get("crop")
                if crop:
                    counts[crop] = counts.get(crop, 0) + 1
            elif kind in ("COOP", "PASTURE"):
                animal = tile.get("animal")
                if animal:
                    product = animal_rollouts.product_for(animal)
                    counts[product] = counts.get(product, 0) + 1
    return counts


def effective_price(
    product: str,
    market_prices: dict,
    shops: list[str],
    i0_prices: dict[str, int],
    opp_tile_counts: dict[str, int] | None = None,
) -> int:
    demand = rollouts.shop_demand_by_product(shops)
    quoted = int(market_prices.get(product, i0_prices.get(product, 0)) or 0)
    opp = (opp_tile_counts or {}).get(product, 0)
    opp_bonus = -opp / 10.0
    price_factor = 1 + demand.get(product, 0) + opp_bonus
    return int(quoted * max(0.1, price_factor))


def make_price_of(
    market_prices: dict,
    shops: list[str],
    i0_prices: dict[str, int],
    opp_tile_counts: dict[str, int] | None = None,
) -> Callable[[str], int]:
    def price_of(product: str) -> int:
        return effective_price(
            product, market_prices, shops, i0_prices, opp_tile_counts
        )

    return price_of


def apply_replan(
    result: SolveResult,
    replan_tiles: list[int],
    tile_queues: dict,
    tile_state: dict | None,
    horizon: int,
) -> int:
    if not result.solved_workers or result.solved_workers[0] != WORKERS[0]:
        return 0

    written = 0
    replan_set = set(replan_tiles)
    for worker in result.solved_workers:
        for idx in WORKER_TILES[worker]:
            if idx not in replan_set:
                continue
            chain = result.assigned.get(idx, [])
            if not chain and tile_queues.get(idx):
                continue
            tile_queues[idx] = chain_to_queue_items(chain, horizon)
            written += 1
            if tile_state is not None and chain:
                queue = tile_queues[idx]
                first_lag = queue[0].start_lag if queue else 0
                tile_state[idx] = {
                    "queue_idx": 0,
                    "lag": first_lag,
                    "gap": 0,
                    "pending_dig": False,
                    "dig_plant_ok": False,
                    "active": False,
                    "fert_today": False,
                }
    return written


def replan(obs: dict, tile_queues: dict, tile_state: dict | None = None) -> None:
    from milos.replan_lock import any_replan_eligible, build_replan_lock

    day = obs["day"]
    if day < 1 or day >= SEASON_LAST_DAY:
        return
    horizon = NUM_DAYS - day
    if horizon <= 0:
        return

    player = obs["player"]
    me = obs["farms"][player]
    st_map = tile_state or {}

    if not any_replan_eligible(me, st_map, tile_queues):
        return

    shops = obs.get("town", {}).get("unlocked_shops", [])
    market_prices = obs.get("market", {}).get("prices", {})
    i0 = wsp_data.i0_base_prices()
    opp_farm = obs["farms"][1 - player]
    opp_counts = _opponent_product_tile_counts(opp_farm)
    price_of = make_price_of(market_prices, shops, i0, opp_counts)

    replan_tiles, locked_by_worker, locked_tiles = build_replan_lock(
        me, day, horizon, tile_queues, st_map, price_of
    )

    if not replan_tiles:
        print(
            f"[planner] replan d={day} skip assign locked={locked_tiles}",
            flush=True,
        )
        return

    print(
        f"[planner] replan d={day} horizon={horizon} empty={len(replan_tiles)} "
        f"locked={locked_tiles}",
        flush=True,
    )

    result = solve(
        [],
        horizon=horizon,
        empty_tiles=replan_tiles,
        empty_counts={FARMER: len(replan_tiles)},
        locked_by_worker=locked_by_worker,
        starting_money=int(me["money"]),
        max_time=15.0,
        track_shed=False,
        min_balance=0,
        price_of=price_of,
    )

    if not result.complete or (
        not result.solved_workers or result.solved_workers[0] != WORKERS[0]
    ):
        print(
            f"[planner] replan d={day} INFEASIBLE keep={len(replan_tiles)} "
            f"active={','.join(result.solved_workers) or 'none'}",
            flush=True,
        )
        return

    apply_replan(result, replan_tiles, tile_queues, tile_state, horizon)

    samples = []
    for idx in replan_tiles[:5]:
        chain = result.assigned.get(idx)
        if chain is None:
            samples.append(f"t{idx + 1}:keep")
            continue
        if not chain:
            samples.append(f"t{idx + 1}:IDLE")
            continue
        pl = ",".join(f"{_parse_profile_key(k)[0]}@{s}" for k, s in chain)
        samples.append(f"t{idx + 1}:{pl}")
    print(f"[planner] replan assign {', '.join(samples)}", flush=True)
    _log_wsp_plan(day, horizon, result, dict(result.assigned))


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
