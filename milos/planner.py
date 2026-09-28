"""Farmer planner — solver result → absolute tile board for Gantt (no agent/)."""

from __future__ import annotations

from collections.abc import Callable

from milos.wsp import data as wsp_data
from milos.wsp.twoland import solve
from milos.wsp.log import WspPlan
from milos.wsp.types import SolveResult
from milos.wsp.config import ANIMAL_NAMES, NUM_DAYS, PROFILE_SUFFIXES
from milos.zoning import (
    FARMER,
    HAND_DAILY_COST,
    NE_WORKERS,
    NUM_TILES,
    NW_WORKERS,
    TILE_COORDS,
    WORKER_TILES,
    WORKERS,
)

PlanBoard = dict[int, list]


def empty_board() -> PlanBoard:
    return {t: [] for t in range(NUM_TILES)}


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
    tile_set = set(range(NUM_TILES))
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
    scope = set(tiles) if tiles is not None else set(range(NUM_TILES))
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
    nw_tiles = sorted({idx for w in NW_WORKERS for idx in WORKER_TILES[w]})
    if price_of is None:
        base = wsp_data.i0_base_prices()
        price_of = lambda product, rel_day=0, extra_units=0, _base=base: _base[
            product
        ]

    result = solve(
        [],
        horizon=NUM_DAYS,
        empty_tiles=nw_tiles,
        empty_counts={w: len(WORKER_TILES[w]) for w in NW_WORKERS},
        starting_money=starting_money,
        max_time=max_time,
        track_shed=track_shed,
        price_of=price_of,
        workers=NW_WORKERS,
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

CURRENT_SOLVER = "milos_twoland"
STARTING_MONEY = 3000
NUM_ACTIVE_HIRES = 5
BUY_LAND_DAY: int | None = None
DEAD_HANDS: set[str] = set()
ACTIVE_NE: list[str] = []
NE_BOUND_TODAY: set[str] = set()
NE_DUE_DAY: dict[str, int] = {}
NE_LAND_COST = 1000
NE_BUY_MIN_CASH = 3000
NE_BUY_FIRST_DAY = 2
NE_BUY_LAST_DAY = 22
_cached_queues: dict | None = None
_BUY_REPLAN_DONE_DAY: int | None = None


def active_workers() -> tuple[str, ...]:
    return NW_WORKERS + tuple(ACTIVE_NE)


def _ne_owned(me: dict) -> bool:
    return "NE" in me.get("unlocked_quadrants", [])


def _tile_at(me: dict, idx: int):
    x, y = TILE_COORDS[idx]
    return me["tiles"][y][x]


def dawn_ne_bound_handoff(
    me: dict,
    day: int,
    tile_queues: dict,
    tile_state: dict | None,
) -> None:
    """Rollback NE zones whose hire never bound yesterday."""
    global NE_BOUND_TODAY, BUY_LAND_DAY, ACTIVE_NE

    if (
        BUY_LAND_DAY is not None
        and day > BUY_LAND_DAY
        and not _ne_owned(me)
    ):
        while ACTIVE_NE:
            _rollback_ne_zone(
                ACTIVE_NE[-1], me, day, tile_queues, tile_state, land_fail=True
            )
        BUY_LAND_DAY = None
    elif BUY_LAND_DAY is not None and day > BUY_LAND_DAY:
        BUY_LAND_DAY = None

    bound_yday = set(NE_BOUND_TODAY)
    for w in list(ACTIVE_NE):
        if NE_DUE_DAY.get(w, day) <= day - 1 and w not in bound_yday:
            _rollback_ne_zone(w, me, day, tile_queues, tile_state)

    NE_BOUND_TODAY.clear()


def schedule_ne_buy_at_dusk(me: dict, day: int) -> None:
    """Schedule NE land buy for tomorrow when cash crosses threshold at dusk."""
    global BUY_LAND_DAY
    if _ne_owned(me):
        return
    buy_day = day + 1
    if buy_day < NE_BUY_FIRST_DAY or buy_day > NE_BUY_LAST_DAY:
        return
    if BUY_LAND_DAY is not None and BUY_LAND_DAY > day:
        return
    money = int(me["money"])
    if money < NE_BUY_MIN_CASH:
        return
    BUY_LAND_DAY = buy_day
    print(
        f"[ne] dusk_trigger d={day} buy_day={buy_day} money={money}",
        flush=True,
    )


def _fresh_tile_state(first_lag: int = 0) -> dict:
    return {
        "queue_idx": 0,
        "lag": first_lag,
        "gap": 0,
        "pending_dig": False,
        "dig_plant_ok": False,
        "active": False,
        "fert_today": False,
    }


def _rollback_ne_zone(
    worker: str,
    me: dict,
    day: int,
    tile_queues: dict,
    tile_state: dict | None,
    *,
    land_fail: bool = False,
) -> None:
    global ACTIVE_NE
    if worker not in ACTIVE_NE and not land_fail:
        return
    st_map = tile_state or {}
    cleared = 0
    for idx in WORKER_TILES.get(worker, ()):
        st = st_map.get(idx, {})
        if st.get("queue_idx", 0) != 0:
            continue
        tile = _tile_at(me, idx)
        if tile is None or tile == "LOCKED":
            tile_queues[idx] = []
            st_map[idx] = _fresh_tile_state()
            cleared += 1
    if worker in ACTIVE_NE:
        ACTIVE_NE.remove(worker)
    NE_DUE_DAY.pop(worker, None)
    reason = "land_fail" if land_fail else "hire_unbound"
    print(
        f"[ne] rollback d={day} zone={worker} reason={reason} cleared={cleared}",
        flush=True,
    )


def _zone_plan_cost(
    assigned: dict[int, list],
    horizon: int,
    worker: str,
    price_of: Callable[..., int],
) -> int:
    from milos.replan_lock import _stamp_chain

    crops_data = wsp_data.crops()
    animals_data = wsp_data.animals()
    total_spend = 0
    for chain in assigned.values():
        if not chain:
            continue
        seg = _stamp_chain(chain, horizon, price_of, crops_data, animals_data)
        total_spend -= sum(seg.get("spend_by_day", []))
    hire = HAND_DAILY_COST.get(worker, 0) * horizon
    return total_spend + hire


def _busy_counts(assigned: dict[int, list]) -> tuple[int, int]:
    busy_day0 = 0
    busy_any = 0
    for chain in assigned.values():
        if not chain:
            continue
        busy_any += 1
        if int(chain[0][1]) == 0:
            busy_day0 += 1
    return busy_day0, busy_any


def _write_ne_activation(
    worker: str,
    assigned: dict[int, list],
    horizon: int,
    tile_queues: dict,
    tile_state: dict | None,
    offset: int,
) -> None:
    global ACTIVE_NE, BUY_LAND_DAY

    st_map = tile_state or {}
    for idx, chain in assigned.items():
        if not chain:
            continue
        tile_queues[idx] = chain_to_queue_items(chain, horizon)
        queue = tile_queues[idx]
        first_lag = queue[0].start_lag if queue else 0
        st_map[idx] = _fresh_tile_state(first_lag + offset)

    ACTIVE_NE.append(worker)


def _activate_next_ne(
    obs: dict,
    tile_queues: dict,
    tile_state: dict | None,
    price_of: Callable[..., int],
) -> None:
    if len(ACTIVE_NE) >= len(NE_WORKERS):
        return

    day = obs["day"]
    player = obs["player"]
    me = obs["farms"][player]
    pending = [w for w in NE_WORKERS if w not in ACTIVE_NE]
    if not pending:
        return
    worker = pending[0]
    ne_owned = _ne_owned(me)

    if not ne_owned:
        return

    horizon = NUM_DAYS - day
    if horizon <= 0:
        return

    money = int(me["money"])
    zone_tiles: list[int] = []
    for idx in WORKER_TILES[worker]:
        tile = _tile_at(me, idx)
        if tile is None:
            zone_tiles.append(idx)
            continue
        if isinstance(tile, dict) and tile.get("kind") == "WEED":
            zone_tiles.append(idx)
    if not zone_tiles:
        return

    result = solve(
        [],
        horizon=horizon,
        empty_tiles=zone_tiles,
        empty_counts={worker: len(zone_tiles)},
        starting_money=money,
        max_time=15.0,
        track_shed=False,
        min_balance=0,
        price_of=price_of,
        workers=(worker,),
        charge_hire_daily=True,
    )

    assigned = {k: v for k, v in result.assigned.items() if v}
    busy_day0, busy_any = _busy_counts(assigned)
    cost = _zone_plan_cost(assigned, horizon, worker, price_of)

    ok = int(worker in result.solved_workers)
    if busy_day0 < 1 or money - cost < 0 or worker not in result.solved_workers:
        print(
            f"[ne] reject d={day} zone={worker} ok={ok} busy_day0={busy_day0} "
            f"busy_any={busy_any} cost={cost} money={money}",
            flush=True,
        )
        return

    _write_ne_activation(worker, result.assigned, horizon, tile_queues, tile_state, 0)
    NE_DUE_DAY[worker] = day
    print(
        f"[ne] accept d={day} zone={worker} busy_day0={busy_day0} "
        f"busy_any={busy_any} cost={cost} BUY_LAND_DAY={BUY_LAND_DAY}",
        flush=True,
    )


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


def _safe_price_of(
    obs: dict,
    tile_queues: dict,
    st_map: dict,
    day: int,
) -> Callable[..., int]:
    from milos.price_forecast import make_price_forecast

    from milos import pricing

    try:
        return make_price_forecast(obs, tile_queues, st_map)
    except Exception as exc:
        print(
            f"[fc] FORECAST FAILED d={day}: {type(exc).__name__}: {exc}",
            flush=True,
        )
        inv = (obs.get("market") or {}).get("inventory") or {}
        snap = {
            p: int(inv.get(p, pricing.I0_DEFAULT)) for p in pricing.MARKET_PARAMS
        }
        return lambda product, rel_day=0, extra_units=0, _i=snap: pricing.quoted(
            product, _i.get(product, pricing.I0_DEFAULT) + int(extra_units)
        )


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
    if not result.solved_workers:
        return 0

    written = 0
    replan_set = set(replan_tiles)
    for idx in replan_set:
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


def _replan_active(
    obs: dict,
    tile_queues: dict,
    tile_state: dict | None,
    price_of: Callable[..., int],
) -> None:
    from milos.replan_lock import any_replan_eligible, build_replan_lock

    day = obs["day"]
    horizon = NUM_DAYS - day
    player = obs["player"]
    me = obs["farms"][player]
    st_map = tile_state or {}
    act = active_workers()
    act_tile_set = {idx for w in act for idx in WORKER_TILES[w]}

    if not any_replan_eligible(me, st_map, tile_queues):
        return

    replan_tiles, locked_by_worker, locked_tiles = build_replan_lock(
        me, day, horizon, tile_queues, st_map, price_of
    )
    replan_tiles = [t for t in replan_tiles if t in act_tile_set]

    if not replan_tiles:
        print(
            f"[planner] replan d={day} skip assign locked={locked_tiles}",
            flush=True,
        )
        return

    print(
        f"[planner] replan d={day} horizon={horizon} empty={len(replan_tiles)} "
        f"locked={locked_tiles} workers={','.join(act)}",
        flush=True,
    )

    result = solve(
        [],
        horizon=horizon,
        empty_tiles=replan_tiles,
        empty_counts={
            w: sum(1 for t in replan_tiles if t in WORKER_TILES[w]) for w in act
        },
        locked_by_worker={w: locked_by_worker[w] for w in act},
        starting_money=int(me["money"]),
        max_time=15.0,
        track_shed=False,
        min_balance=0,
        price_of=price_of,
        workers=act,
    )

    if not result.solved_workers:
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


def replan(obs: dict, tile_queues: dict, tile_state: dict | None = None) -> None:
    day = obs["day"]
    if day < 2 or day >= SEASON_LAST_DAY:
        return
    horizon = NUM_DAYS - day
    if horizon <= 0:
        return

    player = obs["player"]
    me = obs["farms"][player]
    st_map = tile_state or {}

    dawn_ne_bound_handoff(me, day, tile_queues, st_map)

    price_of = _safe_price_of(obs, tile_queues, st_map, day)

    try:
        _replan_active(obs, tile_queues, st_map, price_of)
    except Exception as exc:
        print(f"[planner] walk1 failed d={day}: {exc}", flush=True)
    if BUY_LAND_DAY == day and not _ne_owned(me):
        return
    try:
        _activate_next_ne(obs, tile_queues, st_map, price_of)
    except Exception as exc:
        print(f"[planner] walk2 failed d={day}: {exc}", flush=True)


def replan_after_buy(
    obs: dict,
    tile_queues: dict,
    tile_state: dict | None,
) -> None:
    global _BUY_REPLAN_DONE_DAY

    day = obs["day"]
    player = obs["player"]
    me = obs["farms"][player]
    if (
        BUY_LAND_DAY != day
        or not _ne_owned(me)
        or _BUY_REPLAN_DONE_DAY == day
        or not (2 <= day < SEASON_LAST_DAY)
    ):
        return

    _BUY_REPLAN_DONE_DAY = day
    st_map = tile_state or {}
    horizon = NUM_DAYS - day
    if horizon <= 0:
        return

    from milos.replan_lock import build_replan_lock, empty_locked

    price_of = _safe_price_of(obs, tile_queues, st_map, day)
    nw_tile_set = {idx for w in NW_WORKERS for idx in WORKER_TILES[w]}
    ne_tile_set = {idx for w in NE_WORKERS for idx in WORKER_TILES[w]}

    replan_tiles, locked_by_worker, locked_tiles = build_replan_lock(
        me, day, horizon, tile_queues, st_map, price_of
    )
    nw_empty = sum(1 for t in replan_tiles if t in nw_tile_set)
    ne_replan = [t for t in replan_tiles if t in ne_tile_set]
    ne_empty = len(ne_replan)

    money = int(me["money"])
    overage_before = obs.get("remainingOverageTime")
    all_w = NW_WORKERS + NE_WORKERS
    empty_counts = {
        w: sum(1 for t in ne_replan if t in WORKER_TILES[w]) for w in all_w
    }

    print(
        f"[ne] buy_replan start d={day} money={money} nw_empty={nw_empty} "
        f"ne_empty={ne_empty} overage={overage_before}",
        flush=True,
    )

    result = solve(
        [],
        horizon=horizon,
        empty_tiles=ne_replan,
        empty_counts=empty_counts,
        locked_by_worker={
            w: locked_by_worker.get(w) or empty_locked(horizon) for w in all_w
        },
        starting_money=money,
        max_time=24.0,
        track_shed=False,
        min_balance=0,
        price_of=price_of,
        workers=all_w,
        charge_hire_daily=True,
    )

    overage_after = obs.get("remainingOverageTime")
    active: list[str] = []
    deferred: list[str] = []
    for worker in NE_WORKERS:
        zone_assigned = {
            idx: result.assigned.get(idx, [])
            for idx in WORKER_TILES[worker]
            if result.assigned.get(idx)
        }
        if not zone_assigned:
            deferred.append(worker)
            continue
        busy_day0, _ = _busy_counts(zone_assigned)
        if busy_day0 < 1 or worker not in result.solved_workers:
            deferred.append(worker)
            continue
        _write_ne_activation(
            worker, zone_assigned, horizon, tile_queues, st_map, 0
        )
        NE_DUE_DAY[worker] = day
        active.append(worker)

    print(
        f"[ne] buy_replan d={day} money={money} nw_empty={nw_empty} "
        f"ne_empty={ne_empty} active_ne={','.join(active) or 'none'} "
        f"deferred={','.join(deferred) or 'none'} overage={overage_after}",
        flush=True,
    )


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
    if not result.solved_workers:
        active = ",".join(result.solved_workers) or "none"
        raise RuntimeError(f"day-0 {CURRENT_SOLVER} failed: active={active}")

    queues = {idx: [] for idx in range(NUM_TILES)}
    for idx, chain in result.assigned.items():
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
