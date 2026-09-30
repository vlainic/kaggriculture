"""Farmer planner — solver result → absolute tile board for Gantt (no agent/)."""

from __future__ import annotations

import os
from collections.abc import Callable

from milos.wsp import data as wsp_data
from milos.wsp.twoland import STAPLE_CROPS, solve
from milos.wsp.log import WspPlan
from milos.wsp.types import SolveResult
from milos.wsp.config import ANIMAL_NAMES, NUM_DAYS, PROFILE_SUFFIXES
from milos import fix_flags
from milos.zoning import (
    FARMER,
    HAND_DAILY_COST,
    NE_WORKERS,
    NUM_TILES,
    NW_HANDS,
    NW_WORKERS,
    SW_ENABLED,
    SW_WORKERS,
    TILE_COORDS,
    WORKER_TILES,
    WORKERS,
    is_threeland12,
)

PlanBoard = dict[int, list]


def _activation_crops_allowlist() -> frozenset[str] | None:
    if is_threeland12() and not fix_flags.abl_catalog_enabled():
        return STAPLE_CROPS
    return None


def _ne_accept_staple_flag() -> int:
    if is_threeland12() and not fix_flags.abl_catalog_enabled():
        return 1
    return 0


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


def _wsp_sink_opp(obs: dict, horizon: int) -> tuple[dict[str, int], dict[str, int]]:
    from milos.price_forecast import wsp_sink_and_opp_units

    return wsp_sink_and_opp_units(obs, horizon)


def _wsp_market_inv(obs: dict | None) -> dict[str, int]:
    if obs is None:
        return {}
    inv = obs.get("market", {}).get("inventory") or {}
    return {str(k): int(v) for k, v in inv.items()}


def _wsp_wheat_feed_units(
    me: dict,
    tile_state: dict | None,
    private: dict | None,
    day: int,
) -> int:
    from milos import script

    return script.total_wheat_feed_need(
        me, tile_state or {}, private or {}, day=day
    )


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

    from milos.price_forecast import wsp_sink_and_opp_day0

    sink_units, opp_units = wsp_sink_and_opp_day0(NUM_DAYS)

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
        sink_units=sink_units,
        opp_units=opp_units,
        market_inv={},
        wheat_feed_units=0,
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
NUM_ACTIVE_HIRES = NW_HANDS
BUY_LAND_DAY: int | None = None
DEAD_HANDS: set[str] = set()
STUCK_THRESHOLD = 3
ZONE_SOLVE_STREAK: dict[str, int] = {}
STAND_DOWN_UNTIL: dict[str, int] = {}
ACTIVE_NE: list[str] = []
NE_BOUND_TODAY: set[str] = set()
NE_HIRED_TODAY: tuple[str, ...] = ()
NE_DUE_DAY: dict[str, int] = {}
NE_LAND_COST = 1000
NE_BUY_MIN_CASH = 2000
NE_BUY_FIRST_DAY = 2
NE_BUY_LAST_DAY = 22
_cached_queues: dict | None = None
_BUY_REPLAN_DONE_DAY: int | None = None

SW_BUY_DAY: int | None = None
ACTIVE_SW: list[str] = []
SW_BOUND_TODAY: set[str] = set()
SW_HIRED_TODAY: tuple[str, ...] = ()
SW_DUE_DAY: dict[str, int] = {}
SW_LAND_COST = 2000
SW_BUY_MIN_CASH = 4000
SW_BUY_FIRST_DAY = 8
SW_BUY_LAST_DAY = 18
SW_MAX_ZONES = 5
SW_MIN_OVERAGE = 40.0
SW_OVERAGE_RESERVE = 12.0
SW_BUY_ZONE_TIME = 1.5
BUY_REPLAN_ZONE_TIME = 1.5
BUY_REPLAN_OVERAGE_RESERVE = 12.0
_SW_BUY_REPLAN_DONE_DAY: int | None = None
_SW_DUSK_SKIP_LOG_DAY: int | None = None
STAPLE_BOOTSTRAP_WORKERS: set[str] = set()


def _sw_buy_min_cash() -> int:
    return 3000 if is_threeland12() else SW_BUY_MIN_CASH


def _sw_min_overage() -> float:
    return 20.0 if is_threeland12() else SW_MIN_OVERAGE


def _sw_workers_cap() -> tuple[str, ...]:
    return SW_WORKERS[:SW_MAX_ZONES]


def active_workers() -> tuple[str, ...]:
    return NW_WORKERS + tuple(ACTIVE_NE) + tuple(ACTIVE_SW)


def _ne_owned(me: dict) -> bool:
    return "NE" in me.get("unlocked_quadrants", [])


def _sw_owned(me: dict) -> bool:
    quads = me.get("unlocked_quadrants", [])
    return "SW" in quads


def _sw_buy_allowed(me: dict) -> bool:
    quads = me.get("unlocked_quadrants", [])
    return len(quads) == 2 and "NE" in quads and "SW" not in quads


def _ne_full() -> bool:
    if len(ACTIVE_NE) != len(NE_WORKERS):
        return False
    return set(ACTIVE_NE) <= NE_BOUND_TODAY


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


def schedule_sw_buy_at_dusk(obs: dict, me: dict, day: int) -> None:
    """Schedule SW land buy for tomorrow when NE is full and cash crosses threshold."""
    global SW_BUY_DAY, _SW_DUSK_SKIP_LOG_DAY

    if not SW_ENABLED:
        return
    if not _ne_owned(me) or _sw_owned(me):
        return

    buy_day = day + 1
    overage = float(obs.get("remainingOverageTime") or 0)
    money = int(me["money"])

    def _skip(reason: str) -> None:
        global _SW_DUSK_SKIP_LOG_DAY
        if _SW_DUSK_SKIP_LOG_DAY == day:
            return
        _SW_DUSK_SKIP_LOG_DAY = day
        print(f"[sw] dusk_skip d={day} reason={reason}", flush=True)

    if SW_BUY_DAY is not None and SW_BUY_DAY > day:
        return
    if not _ne_full():
        _skip("ne_not_full")
        return
    if buy_day < SW_BUY_FIRST_DAY or buy_day > SW_BUY_LAST_DAY:
        _skip("window")
        return
    if money < _sw_buy_min_cash():
        _skip("cash")
        return
    if overage < _sw_min_overage():
        _skip("overage")
        return

    SW_BUY_DAY = buy_day
    print(
        f"[sw] dusk_trigger d={day} buy_day={buy_day} money={money} overage={overage}",
        flush=True,
    )


def dawn_sw_bound_handoff(
    me: dict,
    day: int,
    tile_queues: dict,
    tile_state: dict | None,
) -> None:
    """Rollback SW zones whose hire never bound yesterday."""
    global SW_BOUND_TODAY, SW_BUY_DAY, ACTIVE_SW

    if (
        SW_BUY_DAY is not None
        and day > SW_BUY_DAY
        and not _sw_owned(me)
    ):
        while ACTIVE_SW:
            _rollback_sw_zone(
                ACTIVE_SW[-1], me, day, tile_queues, tile_state, land_fail=True
            )
        SW_BUY_DAY = None
    elif SW_BUY_DAY is not None and day > SW_BUY_DAY:
        SW_BUY_DAY = None

    bound_yday = set(SW_BOUND_TODAY)
    for w in list(ACTIVE_SW):
        if SW_DUE_DAY.get(w, day) <= day - 1 and w not in bound_yday:
            _rollback_sw_zone(w, me, day, tile_queues, tile_state)

    SW_BOUND_TODAY.clear()


def _rollback_sw_zone(
    worker: str,
    me: dict,
    day: int,
    tile_queues: dict,
    tile_state: dict | None,
    *,
    land_fail: bool = False,
) -> None:
    global ACTIVE_SW
    if worker not in ACTIVE_SW and not land_fail:
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
    if worker in ACTIVE_SW:
        ACTIVE_SW.remove(worker)
    SW_DUE_DAY.pop(worker, None)
    reason = "land_fail" if land_fail else "hire_unbound"
    print(
        f"[sw] rollback d={day} zone={worker} reason={reason} cleared={cleared}",
        flush=True,
    )


def _write_sw_activation(
    worker: str,
    assigned: dict[int, list],
    horizon: int,
    tile_queues: dict,
    tile_state: dict | None,
    offset: int,
) -> None:
    global ACTIVE_SW

    st_map = tile_state or {}
    for idx, chain in assigned.items():
        if not chain:
            continue
        tile_queues[idx] = chain_to_queue_items(chain, horizon)
        queue = tile_queues[idx]
        first_lag = queue[0].start_lag if queue else 0
        st_map[idx] = _fresh_tile_state(first_lag + offset)

    ACTIVE_SW.append(worker)


def _try_activate_sw(
    worker: str,
    obs: dict,
    tile_queues: dict,
    tile_state: dict | None,
    price_of: Callable[..., int],
    money: int,
) -> tuple[bool, int]:
    day = obs["day"]
    player = obs["player"]
    me = obs["farms"][player]
    horizon = NUM_DAYS - day
    if horizon <= 0:
        return False, money

    zone_tiles: list[int] = []
    for idx in WORKER_TILES[worker]:
        tile = _tile_at(me, idx)
        if tile is None:
            zone_tiles.append(idx)
            continue
        if isinstance(tile, dict) and tile.get("kind") == "WEED":
            zone_tiles.append(idx)
    if not zone_tiles:
        return False, money

    sink_units, opp_units = _wsp_sink_opp(obs, horizon)
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
        sink_units=sink_units,
        opp_units=opp_units,
        market_inv=_wsp_market_inv(obs),
        wheat_feed_units=_wsp_wheat_feed_units(
            me, tile_state, obs.get("private"), day
        ),
        crops_allowlist=_activation_crops_allowlist(),
        calendar_day=day,
        new_zone_activation=True,
    )

    assigned = {k: v for k, v in result.assigned.items() if v}
    _, busy_any = _busy_counts(assigned)
    cost = _zone_plan_cost(assigned, horizon, worker, price_of)
    ok = int(worker in result.solved_workers)
    if not ok or busy_any < 1 or money < cost:
        print(
            f"[sw] reject d={day} zone={worker} ok={ok} "
            f"busy_any={busy_any} cost={cost} money={money}",
            flush=True,
        )
        return False, money

    if not _zone_activation_value_check(
        "sw", day, worker, result.zone_objectives.get(worker), horizon
    ):
        return False, money

    _write_sw_activation(worker, result.assigned, horizon, tile_queues, tile_state, 0)
    SW_DUE_DAY[worker] = day
    if is_threeland12():
        STAPLE_BOOTSTRAP_WORKERS.add(worker)
    print(
        f"[sw] accept d={day} zone={worker} busy_any={busy_any} "
        f"cost={cost} money={money} SW_BUY_DAY={SW_BUY_DAY}",
        flush=True,
    )
    return True, money - cost


def _activate_next_sw(
    obs: dict,
    tile_queues: dict,
    tile_state: dict | None,
    price_of: Callable[..., int],
) -> bool:
    cap = _sw_workers_cap()
    if len(ACTIVE_SW) >= len(cap):
        return False

    day = obs["day"]
    player = obs["player"]
    me = obs["farms"][player]
    if not _sw_owned(me):
        return False

    money = int(me["money"])
    accepted = False
    for worker in cap:
        if worker in ACTIVE_SW:
            continue
        if day < STAND_DOWN_UNTIL.get(worker, 0):
            continue
        ok, money = _try_activate_sw(
            worker, obs, tile_queues, tile_state, price_of, money
        )
        accepted = accepted or ok
    return accepted


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
    *,
    hire_days: int | None = None,
) -> int:
    from milos.replan_lock import _stamp_chain

    crops_data = wsp_data.crops()
    animals_data = wsp_data.animals()
    total_spend = 0
    for chain in assigned.values():
        if not chain:
            continue
        seg = _stamp_chain(chain, horizon, price_of, crops_data, animals_data)
        spend_by_day = seg.get("spend_by_day", [])
        for d in range(min(2, len(spend_by_day))):
            total_spend -= spend_by_day[d]
    hd = hire_days if hire_days is not None else 1
    hire = HAND_DAILY_COST.get(worker, 0) * hd
    return total_spend + hire


def _zone_gate_hire_cost(worker: str, horizon: int) -> int:
    hd = 1 if fix_flags.abl_cash_enabled() else horizon
    return HAND_DAILY_COST.get(worker, 0) * hd


def _zone_value_min_net() -> int:
    try:
        return int(os.environ.get("KAGGRI_ZONE_MIN_NET", "0"))
    except ValueError:
        return 0


def _zone_value_margin_ratio() -> float:
    try:
        return float(os.environ.get("KAGGRI_ZONE_MARGIN_RATIO", "0"))
    except ValueError:
        return 0.0


def _zone_value_ok(obj: int | float | None, hire_cost: int) -> tuple[bool, str]:
    """Fail open when obj is missing; obj already nets setup — gate on hire only."""
    if obj is None:
        return True, "value_unknown"
    net = float(obj) - float(hire_cost)
    min_net = _zone_value_min_net()
    ratio = _zone_value_margin_ratio()
    if ratio > 0 and hire_cost > 0:
        if float(obj) < (1.0 + ratio) * float(hire_cost):
            return False, "low_value"
    if net < min_net:
        return False, "low_value"
    return True, "ok"


def _zone_activation_value_check(
    tag: str,
    day: int,
    worker: str,
    obj: int | float | None,
    horizon: int,
) -> bool:
    hire_cost = _zone_gate_hire_cost(worker, horizon)
    ok, reason = _zone_value_ok(obj, hire_cost)
    if reason == "value_unknown":
        print(
            f"[{tag}] d={day} zone={worker} value_unknown hire={hire_cost}",
            flush=True,
        )
        return True
    if not ok:
        net = int(float(obj) - float(hire_cost))
        print(
            f"[{tag}] reject d={day} zone={worker} reason=low_value "
            f"obj={int(obj)} hire={hire_cost} net={net}",
            flush=True,
        )
        return False
    return True


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


def _try_activate_ne_staple(
    worker: str,
    obs: dict,
    tile_queues: dict,
    tile_state: dict | None,
    price_of: Callable[..., int],
    money: int,
) -> tuple[bool, int]:
    global STAPLE_BOOTSTRAP_WORKERS

    day = obs["day"]
    player = obs["player"]
    me = obs["farms"][player]
    horizon = NUM_DAYS - day
    if horizon <= 0:
        return False, money

    zone_tiles: list[int] = []
    for idx in WORKER_TILES[worker]:
        tile = _tile_at(me, idx)
        if tile is None:
            zone_tiles.append(idx)
            continue
        if isinstance(tile, dict) and tile.get("kind") == "WEED":
            zone_tiles.append(idx)
    if not zone_tiles:
        return False, money

    sink_units, opp_units = _wsp_sink_opp(obs, horizon)
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
        sink_units=sink_units,
        opp_units=opp_units,
        market_inv=_wsp_market_inv(obs),
        wheat_feed_units=_wsp_wheat_feed_units(
            me, tile_state, obs.get("private"), day
        ),
        crops_allowlist=_activation_crops_allowlist(),
        calendar_day=day,
        new_zone_activation=True,
    )

    assigned = {k: v for k, v in result.assigned.items() if v}
    _, busy_any = _busy_counts(assigned)
    cost = _zone_plan_cost(assigned, horizon, worker, price_of)
    ok = int(worker in result.solved_workers)
    if not ok or busy_any < 1 or money < cost:
        print(
            f"[ne] reject d={day} zone={worker} ok={ok} "
            f"busy_any={busy_any} cost={cost} money={money}",
            flush=True,
        )
        return False, money

    if not _zone_activation_value_check(
        "ne", day, worker, result.zone_objectives.get(worker), horizon
    ):
        return False, money

    _write_ne_activation(worker, result.assigned, horizon, tile_queues, tile_state, 0)
    NE_DUE_DAY[worker] = day
    if is_threeland12():
        STAPLE_BOOTSTRAP_WORKERS.add(worker)
    print(
        f"[ne] accept d={day} zone={worker} busy_any={busy_any} "
        f"cost={cost} money={money} staple={_ne_accept_staple_flag()}",
        flush=True,
    )
    return True, money - cost


def _fill_all_ne_day1(
    obs: dict,
    tile_queues: dict,
    tile_state: dict | None,
    price_of: Callable[..., int],
) -> None:
    if not _ne_owned(obs["farms"][obs["player"]]):
        return
    money = int(obs["farms"][obs["player"]]["money"])
    day = obs["day"]
    for worker in NE_WORKERS:
        if worker in ACTIVE_NE:
            continue
        if day < STAND_DOWN_UNTIL.get(worker, 0):
            continue
        _, money = _try_activate_ne_staple(
            worker, obs, tile_queues, tile_state, price_of, money
        )


def _activate_next_ne(
    obs: dict,
    tile_queues: dict,
    tile_state: dict | None,
    price_of: Callable[..., int],
) -> None:
    _fill_all_ne_day1(obs, tile_queues, tile_state, price_of)


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


def _stand_down_workers() -> tuple[str, ...]:
    return tuple(NE_WORKERS) + tuple(_sw_workers_cap())


def _zone_live_empty(me: dict, worker: str, day: int) -> int:
    n = 0
    for idx in WORKER_TILES.get(worker, ()):
        tile = _tile_at(me, idx)
        if tile is None:
            n += 1
            continue
        if isinstance(tile, dict) and tile.get("kind") == "WEED":
            n += 1
    return n


def update_zone_streaks(
    day: int,
    empty_counts: dict[str, int],
    zone_outcomes: dict[str, str],
) -> None:
    """NE/SW only: N consecutive bad solves with empties → DEAD_HANDS."""
    global ZONE_SOLVE_STREAK, DEAD_HANDS
    for worker in _stand_down_workers():
        outcome = zone_outcomes.get(worker, "ok")
        empty_n = int(empty_counts.get(worker, 0))
        if outcome == "ok":
            if worker in DEAD_HANDS or ZONE_SOLVE_STREAK.get(worker, 0) > 0:
                print(
                    f"[planner] zone_streak worker={worker} d={day} "
                    f"streak=0 status=recovered",
                    flush=True,
                )
            ZONE_SOLVE_STREAK[worker] = 0
            DEAD_HANDS.discard(worker)
            continue
        if empty_n <= 0 or outcome == "empty":
            continue
        streak = ZONE_SOLVE_STREAK.get(worker, 0) + 1
        ZONE_SOLVE_STREAK[worker] = streak
        if streak >= STUCK_THRESHOLD and worker not in DEAD_HANDS:
            DEAD_HANDS.add(worker)
            print(
                f"[planner] zone_streak worker={worker} d={day} "
                f"streak={streak} status=stuck",
                flush=True,
            )


def _apply_stand_downs(
    day: int,
    me: dict,
    tile_queues: dict,
    tile_state: dict | None,
) -> None:
    global STAND_DOWN_UNTIL
    for worker in list(DEAD_HANDS):
        if worker in ACTIVE_NE:
            _rollback_ne_zone(worker, me, day, tile_queues, tile_state)
            STAND_DOWN_UNTIL[worker] = day + 2
        elif worker in ACTIVE_SW:
            _rollback_sw_zone(worker, me, day, tile_queues, tile_state)
            STAND_DOWN_UNTIL[worker] = day + 2


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
    staple = (
        frozenset(STAPLE_BOOTSTRAP_WORKERS) if is_threeland12() else None
    )

    if not any_replan_eligible(
        me, st_map, tile_queues, staple_bootstrap_workers=staple
    ):
        return

    replan_tiles, locked_by_worker, locked_tiles = build_replan_lock(
        me,
        day,
        horizon,
        tile_queues,
        st_map,
        price_of,
        market_inv=_wsp_market_inv(obs),
        staple_bootstrap_workers=staple,
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

    sink_units, opp_units = _wsp_sink_opp(obs, horizon)
    from milos.replan_lock import committed_harvest_units

    committed = committed_harvest_units(locked_by_worker)

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
        sink_units=sink_units,
        opp_units=opp_units,
        market_inv=_wsp_market_inv(obs),
        wheat_feed_units=_wsp_wheat_feed_units(
            me, st_map, obs.get("private"), day
        ),
        calendar_day=day,
        committed_units=committed,
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

    empty_counts = {
        w: sum(1 for t in replan_tiles if t in WORKER_TILES[w]) for w in act
    }
    outcomes = getattr(result, "zone_outcomes", None) or {}
    update_zone_streaks(day, empty_counts, outcomes)
    _apply_stand_downs(day, me, tile_queues, tile_state)


def replan(obs: dict, tile_queues: dict, tile_state: dict | None = None) -> None:
    day = obs["day"]
    min_day = 1 if is_threeland12() else 2
    if day < min_day or day >= SEASON_LAST_DAY:
        return
    horizon = NUM_DAYS - day
    if horizon <= 0:
        return

    player = obs["player"]
    me = obs["farms"][player]
    st_map = tile_state or {}

    dawn_ne_bound_handoff(me, day, tile_queues, st_map)
    dawn_sw_bound_handoff(me, day, tile_queues, st_map)

    price_of = _safe_price_of(obs, tile_queues, st_map, day)

    if day == 1 and is_threeland12():
        if _ne_owned(me):
            _fill_all_ne_day1(obs, tile_queues, st_map, price_of)
        return

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
    if SW_ENABLED and SW_BUY_DAY != day:
        try:
            _activate_next_sw(obs, tile_queues, st_map, price_of)
        except Exception as exc:
            print(f"[planner] walk3 failed d={day}: {exc}", flush=True)


def replan_after_buy_sw(
    obs: dict,
    tile_queues: dict,
    tile_state: dict | None,
) -> None:
    global _SW_BUY_REPLAN_DONE_DAY

    day = obs["day"]
    player = obs["player"]
    me = obs["farms"][player]
    if (
        not SW_ENABLED
        or SW_BUY_DAY != day
        or not _sw_owned(me)
        or _SW_BUY_REPLAN_DONE_DAY == day
        or not (2 <= day < SEASON_LAST_DAY)
    ):
        return

    _SW_BUY_REPLAN_DONE_DAY = day
    st_map = tile_state or {}
    horizon = NUM_DAYS - day
    if horizon <= 0:
        return

    from milos.replan_lock import build_replan_lock, committed_harvest_units, empty_locked

    price_of = _safe_price_of(obs, tile_queues, st_map, day)
    sw_cap = _sw_workers_cap()
    sw_tile_set = {idx for w in sw_cap for idx in WORKER_TILES[w]}

    replan_tiles, locked_by_worker, locked_tiles = build_replan_lock(
        me, day, horizon, tile_queues, st_map, price_of,
        market_inv=_wsp_market_inv(obs),
    )
    sw_replan = [t for t in replan_tiles if t in sw_tile_set]
    sw_empty = len(sw_replan)

    money = int(me["money"])
    overage_before = float(obs.get("remainingOverageTime") or 0)
    land_w = sw_cap
    empty_counts = {
        w: sum(1 for t in sw_replan if t in WORKER_TILES[w]) for w in land_w
    }

    min_solve_time = BUY_REPLAN_ZONE_TIME * len(land_w)
    max_time = min(
        BUY_REPLAN_ZONE_TIME * len(land_w),
        overage_before - BUY_REPLAN_OVERAGE_RESERVE,
    )

    print(
        f"[sw] buy_replan start d={day} money={money} sw_empty={sw_empty} "
        f"max_time={max_time} overage={overage_before}",
        flush=True,
    )

    if max_time < min_solve_time:
        print(
            f"[sw] buy_replan skip overage={overage_before} need={min_solve_time}",
            flush=True,
        )
        return

    sink_units, opp_units = _wsp_sink_opp(obs, horizon)
    committed = committed_harvest_units(locked_by_worker)

    result = solve(
        [],
        horizon=horizon,
        empty_tiles=sw_replan,
        empty_counts=empty_counts,
        locked_by_worker={
            w: locked_by_worker.get(w) or empty_locked(horizon) for w in land_w
        },
        starting_money=money,
        max_time=max_time,
        track_shed=False,
        min_balance=0,
        price_of=price_of,
        workers=land_w,
        charge_hire_daily=True,
        committed_units=committed,
        sink_units=sink_units,
        opp_units=opp_units,
        market_inv=_wsp_market_inv(obs),
        wheat_feed_units=_wsp_wheat_feed_units(
            me, st_map, obs.get("private"), day
        ),
        crops_allowlist=_activation_crops_allowlist(),
        calendar_day=day,
    )

    overage_after = obs.get("remainingOverageTime")
    active: list[str] = []
    deferred: list[str] = []
    for worker in sw_cap:
        zone_assigned = {
            idx: result.assigned.get(idx, [])
            for idx in WORKER_TILES[worker]
            if result.assigned.get(idx)
        }
        if not zone_assigned:
            deferred.append(worker)
            break
        _, busy_any = _busy_counts(zone_assigned)
        if busy_any < 1 or worker not in result.solved_workers:
            deferred.append(worker)
            break
        if not _zone_activation_value_check(
            "sw", day, worker, result.zone_objectives.get(worker), horizon
        ):
            deferred.append(worker)
            break
        _write_sw_activation(
            worker, zone_assigned, horizon, tile_queues, st_map, 0
        )
        SW_DUE_DAY[worker] = day
        if is_threeland12():
            STAPLE_BOOTSTRAP_WORKERS.add(worker)
        active.append(worker)

    if len(active) < 2:
        print(
            f"[sw] buy_replan wasted_land d={day} n_active={len(active)}",
            flush=True,
        )

    print(
        f"[sw] buy_replan d={day} money={money} sw_empty={sw_empty} "
        f"active_sw={','.join(active) or 'none'} "
        f"deferred={','.join(deferred) or 'none'} overage={overage_after}",
        flush=True,
    )


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

    from milos.replan_lock import build_replan_lock, committed_harvest_units, empty_locked

    price_of = _safe_price_of(obs, tile_queues, st_map, day)
    nw_tile_set = {idx for w in NW_WORKERS for idx in WORKER_TILES[w]}
    ne_tile_set = {idx for w in NE_WORKERS for idx in WORKER_TILES[w]}

    replan_tiles, locked_by_worker, locked_tiles = build_replan_lock(
        me, day, horizon, tile_queues, st_map, price_of,
        market_inv=_wsp_market_inv(obs),
    )
    nw_empty = sum(1 for t in replan_tiles if t in nw_tile_set)
    ne_replan = [t for t in replan_tiles if t in ne_tile_set]
    ne_empty = len(ne_replan)

    money = int(me["money"])
    overage_before = float(obs.get("remainingOverageTime") or 0)
    land_w = NE_WORKERS
    empty_counts = {
        w: sum(1 for t in ne_replan if t in WORKER_TILES[w]) for w in land_w
    }
    min_solve_time = BUY_REPLAN_ZONE_TIME * len(land_w)
    max_time = min(
        BUY_REPLAN_ZONE_TIME * len(land_w),
        overage_before - BUY_REPLAN_OVERAGE_RESERVE,
    )

    print(
        f"[ne] buy_replan start d={day} money={money} nw_empty={nw_empty} "
        f"ne_empty={ne_empty} max_time={max_time} overage={overage_before}",
        flush=True,
    )

    if max_time < min_solve_time:
        print(
            f"[ne] buy_replan skip overage={overage_before} need={min_solve_time}",
            flush=True,
        )
        return

    sink_units, opp_units = _wsp_sink_opp(obs, horizon)
    committed = committed_harvest_units(locked_by_worker)

    result = solve(
        [],
        horizon=horizon,
        empty_tiles=ne_replan,
        empty_counts=empty_counts,
        locked_by_worker={
            w: locked_by_worker.get(w) or empty_locked(horizon) for w in land_w
        },
        starting_money=money,
        max_time=max_time,
        track_shed=False,
        min_balance=0,
        price_of=price_of,
        workers=land_w,
        charge_hire_daily=True,
        committed_units=committed,
        sink_units=sink_units,
        opp_units=opp_units,
        market_inv=_wsp_market_inv(obs),
        wheat_feed_units=_wsp_wheat_feed_units(
            me, st_map, obs.get("private"), day
        ),
        calendar_day=day,
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
            break
        _, busy_any = _busy_counts(zone_assigned)
        if busy_any < 1 or worker not in result.solved_workers:
            deferred.append(worker)
            break
        if not _zone_activation_value_check(
            "ne", day, worker, result.zone_objectives.get(worker), horizon
        ):
            deferred.append(worker)
            break
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


def _day0_plan_ok(result: SolveResult) -> bool:
    big = 0
    melons = 0
    for chain in result.assigned.values():
        if not chain:
            continue
        for key, start in chain:
            label, _ = _parse_profile_key(key)
            if label in ("COW", "SHEEP") and int(start) <= 1:
                big += 1
            if label == "MELON" and int(start) == 0:
                melons += 1
    return big >= 4 and melons >= 10


def _hardcoded_day0_queues() -> dict[int, list]:
    nw_tiles = sorted({idx for w in NW_WORKERS for idx in WORKER_TILES[w]})
    chains: dict[int, list] = {}
    for i, idx in enumerate(nw_tiles):
        if i < 10:
            chains[idx] = [("MELON_no_fert", 0)]
        elif i in (10, 11):
            chains[idx] = [("COW_with_care", 0)]
        elif i in (12, 13):
            chains[idx] = [("SHEEP_with_care", 0)]
        else:
            chains[idx] = [("WHEAT_no_fert", 0), ("WHEAT_no_fert", 5)]
    print("[planner] day0 hardcoded template", flush=True)
    return {
        idx: chain_to_queue_items(ch, NUM_DAYS)
        for idx, ch in chains.items()
    }


def _build_threeland12_day0() -> dict[int, list]:
    from pathlib import Path

    from milos.v55_opener import v55_opener_enabled

    global BUY_LAND_DAY

    if v55_opener_enabled():
        print(
            "[planner] day0 v55 opener tape (empty queues until d6 adopt)",
            flush=True,
        )
        return {idx: [] for idx in range(NUM_TILES)}

    BUY_LAND_DAY = 0
    path = Path(__file__).resolve().parent / "wsp" / "wsp4_prestart.json"
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    assigned = {int(k): list(v) for k, v in data["assigned"].items()}
    queues: dict[int, list] = {idx: [] for idx in range(NUM_TILES)}
    for idx, chain in assigned.items():
        queues[idx] = chain_to_queue_items(chain, NUM_DAYS)
    print(
        f"[planner] day0 wsp4 prestart tiles={len(assigned)} BUY_LAND_DAY=0",
        flush=True,
    )
    return queues


def _build_from_solver() -> dict[int, list]:
    if is_threeland12():
        return _build_threeland12_day0()

    import time

    t0 = time.monotonic()
    _board, result = build_day0(starting_money=STARTING_MONEY, max_time=20.0)
    ms = int((time.monotonic() - t0) * 1000)
    print(
        f"[planner] day0 live ms={ms} complete={result.complete} "
        f"solved={','.join(result.solved_workers) or 'none'}",
        flush=True,
    )
    if not result.solved_workers:
        active = ",".join(result.solved_workers) or "none"
        raise RuntimeError(f"day-0 {CURRENT_SOLVER} failed: active={active}")

    if ms > 20_000 or not _day0_plan_ok(result):
        return _hardcoded_day0_queues()

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
