"""DP catalog + zone-count CP-SAT planner with dawn replan."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from agent import animal_rollouts, dp_catalog, rollouts, solvers, zoning
from agent.flags import VERBOSE
from agent.zoning import (
    LAND1_TILE_COUNT,
    LAND1_WORKERS,
    LAND2_TILE_COUNT,
    NUM_TILES,
    TILE_COORDS,
    WORKER_TILES,
    WORKERS,
    worker_for_tile,
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

NUM_DAYS = 30
SEASON_LAST_DAY = 29
STARTING_MONEY = 3000
NUM_ACTIVE_HIRES: int = 4
BUY_LAND_DAY: int | None = None
ZONE_SOLVE_STREAK: dict[str, int] = {}
DEAD_HANDS: set[str] = set()
STUCK_THRESHOLD = 3
_NE_TILES = tuple(range(LAND1_TILE_COUNT, LAND2_TILE_COUNT))
_SW_TILES = tuple(range(LAND2_TILE_COUNT, LAND2_TILE_COUNT + 25))
PROFILE_SUFFIXES = ("no_fert", "with_fert", "no_care", "with_care")
ANIMAL_NAMES = frozenset(animal_rollouts.animal_names())
CROP_PROFILE = "no_fert"
ANIMAL_PROFILE = "with_care"

ZERO_DAILY_KEYS = (
    "daily_tile_ops",
    "daily_wheat_pickup",
    "daily_animal_place",
    "daily_animal_active",
    "daily_fert_pickup",
    "daily_feed",
    "daily_fert",
    "daily_collect",
    "daily_wheat",
)

_cached_queues: dict | None = None


def _ne_owned(me: dict) -> bool:
    return "NE" in me.get("unlocked_quadrants", [])


def _sw_owned(me: dict) -> bool:
    return "SW" in me.get("unlocked_quadrants", [])


def _land2_owned(me: dict) -> bool:
    """Alias for NE owned (TwoLand callers)."""
    return _ne_owned(me)


def is_buy_morning_locked(tile, idx: int, day: int, me: dict) -> bool:
    """LOCKED expand tiles still read LOCKED at h0 on BUY_LAND morning."""
    if tile != "LOCKED" or BUY_LAND_DAY is None or day != BUY_LAND_DAY:
        return False
    if not _ne_owned(me):
        return idx in _NE_TILES
    if not _sw_owned(me):
        return idx in _SW_TILES
    return False


def is_buy_morning_ne_locked(tile, idx: int, day: int, me: dict | None = None) -> bool:
    """Back-compat wrapper; prefer is_buy_morning_locked with me."""
    if me is None:
        # Without me, only NE range (TwoLand-safe when SW not in NUM_TILES)
        return (
            tile == "LOCKED"
            and idx in _NE_TILES
            and BUY_LAND_DAY is not None
            and day == BUY_LAND_DAY
        )
    return is_buy_morning_locked(tile, idx, day, me)


def _zone_has_work(
    me: dict, worker: str, tile_queues: dict, assigned: dict[int, list]
) -> bool:
    for idx in WORKER_TILES[worker]:
        tile = _tile_at(me, idx)
        if isinstance(tile, dict) and tile.get("kind") in ("PLANT", "COOP", "PASTURE"):
            return True
        if assigned.get(idx):
            return True
        if tile_queues.get(idx):
            return True
    return False


def _load_json(name: str) -> dict | list:
    with (_DATA_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


def _i0_prices(crops_data: dict, animals_data: dict) -> dict[str, int]:
    prices = {crop: spec["base_price"] for crop, spec in crops_data["crops"].items()}
    for spec in animals_data["animals"].values():
        prices[spec["product"]] = spec["base_price"]
    return prices


def _opponent_product_tile_counts(opp_farm: dict) -> dict[str, int]:
    """Count opponent tiles producing each market product (visible farm only)."""
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
    # opp_bonus = 0.5 - opp / 10.0
    opp_bonus = - opp / 10.0

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


def _zero_daily(horizon: int) -> dict[str, list[int]]:
    return {key: [0] * horizon for key in ZERO_DAILY_KEYS}


def _parse_profile_key(profile_key: str) -> tuple[str, str]:
    for suffix in PROFILE_SUFFIXES:
        token = f"_{suffix}"
        if profile_key.endswith(token):
            return profile_key[: -len(token)], suffix
    raise ValueError(f"unknown profile key: {profile_key}")


def _log_wsp_plan(
    day: int,
    horizon: int,
    result,
    assigned: dict[int, list],
) -> None:
    if not VERBOSE or not assigned:
        return
    payload = {str(k): v for k, v in assigned.items()}
    print(
        f"[wsp_plan] d={day} horizon={horizon} solver={solvers.CURRENT_SOLVER} "
        f"complete={int(result.complete)} assigned={json.dumps(payload)}",
        flush=True,
    )


def _rollout_spec(label: str, profile_name: str, crops_data: dict, animals_data: dict):
    if label in crops_data["crops"]:
        spec = crops_data["crops"][label]
        return "crop", spec, spec[profile_name]
    if label in animals_data["animals"]:
        spec = animals_data["animals"][label]
        return "animal", spec, spec[profile_name]
    raise KeyError(label)


def _parse_age_maps(profile, label, kind):
    harvest_map = dict(zip(profile["harvest_ages"], profile["yield_per_harvest"]))
    feed_by_age = {}
    fert_use_by_age = {}
    collect_by_age = {}
    wheat_gain_by_age = {}
    for day in profile["days"]:
        age = day["age"]
        acts = day["actions"]
        feed_by_age[age] = 1 if "FEED" in acts else 0
        fert_use_by_age[age] = 1 if "FERTILIZE" in acts else 0
        collect_by_age[age] = 1 if "COLLECT_FERTILIZER" in acts else 0
        wheat_gain_by_age[age] = (
            harvest_map[age] if kind == "crop" and label == "WHEAT" and age in harvest_map else 0
        )
    return feed_by_age, fert_use_by_age, collect_by_age, wheat_gain_by_age


def _product_for_label(label: str, kind: str) -> str:
    if kind == "animal":
        return animal_rollouts.product_for(label)
    return label


def _build_cash_and_spend(
    start_day: int,
    setup_cost: int,
    unit_price: int,
    profile,
    horizon: int,
    *,
    min_age: int = 0,
    charge_setup: bool = True,
) -> tuple[list[int], list[int]]:
    cash = [0] * horizon
    spend = [0] * horizon
    if charge_setup and start_day < horizon:
        cash[start_day] -= setup_cost
        spend[start_day] -= setup_cost
    for age, yld in zip(profile["harvest_ages"], profile["yield_per_harvest"]):
        if age < min_age:
            continue
        hday = start_day + (age - min_age)
        if hday < horizon:
            cash[hday] += yld * unit_price
    return cash, spend


def _stamp_profile_segment(
    label: str,
    profile_name: str,
    rel_start: int,
    min_age: int,
    horizon: int,
    price_of: Callable[[str], int],
    crops_data: dict,
    animals_data: dict,
    *,
    charge_setup: bool,
):
    kind, spec, profile = _rollout_spec(label, profile_name, crops_data, animals_data)
    setup_cost = spec["seed_cost"] if kind == "crop" else spec["animal_cost"]
    unit_price = price_of(_product_for_label(label, kind))
    feed_by_age, fert_use_by_age, collect_by_age, wheat_gain_by_age = _parse_age_maps(
        profile, label, kind
    )

    out = _zero_daily(horizon)
    cash_by_day = [0] * horizon
    spend_by_day = [0] * horizon

    if kind == "crop":
        for day in profile["days"]:
            age = day["age"]
            if age < min_age:
                continue
            rel = rel_start + (age - min_age)
            if rel >= horizon:
                continue
            acts = day["actions"]
            out["daily_tile_ops"][rel] += len(acts)
            if "FERTILIZE" in acts:
                out["daily_fert_pickup"][rel] += 1
            out["daily_feed"][rel] += feed_by_age.get(age, 0)
            out["daily_fert"][rel] += fert_use_by_age.get(age, 0)
            out["daily_collect"][rel] += collect_by_age.get(age, 0)
            out["daily_wheat"][rel] += wheat_gain_by_age.get(age, 0)
    else:
        occupied = False
        for day in profile["days"]:
            age = day["age"]
            if age < min_age:
                continue
            rel = rel_start + (age - min_age)
            if rel >= horizon:
                break
            occupied = True
            acts = day["actions"]
            out["daily_tile_ops"][rel] += len(acts)
            if "FEED" in acts:
                out["daily_wheat_pickup"][rel] += 1
            if age == 0 and min_age == 0:
                out["daily_animal_place"][rel] = 1
            out["daily_animal_active"][rel] = 1
            out["daily_feed"][rel] += feed_by_age.get(age, 0)
            out["daily_fert"][rel] += fert_use_by_age.get(age, 0)
            out["daily_collect"][rel] += collect_by_age.get(age, 0)
            out["daily_wheat"][rel] += wheat_gain_by_age.get(age, 0)
        if not occupied:
            return None

    cash_by_day, spend_by_day = _build_cash_and_spend(
        rel_start,
        setup_cost,
        unit_price,
        profile,
        horizon,
        min_age=min_age,
        charge_setup=charge_setup,
    )
    return {
        "weight": sum(cash_by_day),
        "cash_by_day": cash_by_day,
        "spend_by_day": spend_by_day,
        **out,
    }


def _stamp_placement(
    profile_key: str,
    start_day: int,
    horizon: int,
    price_of: Callable[[str], int],
    crops_data: dict,
    animals_data: dict,
):
    label, profile_name = _parse_profile_key(profile_key)
    return _stamp_profile_segment(
        label,
        profile_name,
        start_day,
        0,
        horizon,
        price_of,
        crops_data,
        animals_data,
        charge_setup=True,
    )


def _add_daily(dst: list[int], src: list[int], horizon: int) -> None:
    for i in range(horizon):
        dst[i] += src[i]


def _stamp_chain(
    chain,
    chain_idx,
    horizon: int,
    price_of: Callable[[str], int],
    crops_data: dict,
    animals_data: dict,
):
    out = _zero_daily(horizon)
    cash_by_day = [0] * horizon
    spend_by_day = [0] * horizon
    skipped = []
    for profile_key, start_day in chain:
        seg = _stamp_placement(
            profile_key, start_day, horizon, price_of, crops_data, animals_data
        )
        if seg is None:
            skipped.append((profile_key, start_day))
            continue
        for key in ZERO_DAILY_KEYS:
            _add_daily(out[key], seg[key], horizon)
        _add_daily(cash_by_day, seg["cash_by_day"], horizon)
        _add_daily(spend_by_day, seg["spend_by_day"], horizon)
    return {
        "id": f"C{chain_idx}" if chain_idx >= 0 else "IDLE",
        "chain_idx": chain_idx,
        "raw_chain": chain,
        "weight": sum(cash_by_day),
        "cash_by_day": cash_by_day,
        "spend_by_day": spend_by_day,
        **out,
        "skipped": skipped,
    }


def _build_chains(
    crops_data: dict,
    animals_data: dict,
    handmade_chains: list,
    horizon: int,
    price_of: Callable[[str], int],
):
    chains = [
        _stamp_chain(chain, i, horizon, price_of, crops_data, animals_data)
        for i, chain in enumerate(handmade_chains)
    ]
    chains.append(_stamp_chain([], -1, horizon, price_of, crops_data, animals_data) | {"id": "IDLE"})
    return chains


def _tile_at(me: dict, idx: int):
    x, y = TILE_COORDS[idx]
    return me["tiles"][y][x]


def _profile_key_for_item(item) -> str:
    return f"{item.label}_{item.profile}"


def _queue_suffix_to_chain(
    queue: list,
    qi: int,
    lag: int,
    gap: int,
    from_day: int,
    horizon: int,
    me: dict,
    idx: int,
) -> list:
    """Handmade raw_chain on replan horizon for queue[qi:] after board/lag/gap."""
    from agent import tile_ops

    end_day = from_day + horizon
    cal = from_day
    tile = _tile_at(me, idx)
    chain: list = []

    if isinstance(tile, dict) and tile.get("kind") == "PLANT":
        crop = tile["crop"]
        item = queue[qi] if qi < len(queue) else None
        profile = item.profile if item and item.kind == "crop" else CROP_PROFILE
        free_day = tile["planted_day"] + rollouts.tile_free_age(crop, profile)
        cal = max(cal, free_day)
        if item is not None:
            qi, lag, gap, _ = tile_ops.on_lifecycle_end(idx, qi, item, False)
    elif isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
        if tile.get("animal"):
            return []

    while qi < len(queue) and cal < end_day:
        while lag > 0 and cal < end_day:
            cal += 1
            lag -= 1
        while gap > 0 and cal < end_day:
            cal += 1
            gap -= 1
        if cal >= end_day:
            break

        item = queue[qi]
        rel = cal - from_day
        if rel >= horizon:
            break
        chain.append([_profile_key_for_item(item), rel])
        if item.kind == "crop":
            cal += rollouts.tile_free_age(item.label, item.profile)
            qi += 1
            lag = queue[qi].start_lag if qi < len(queue) else 0
            gap = item.replant_gap
        else:
            break

    return chain


def _stamp_tile_commitment(
    idx: int,
    me: dict,
    st: dict,
    queue: list,
    day: int,
    horizon: int,
    price_of: Callable[[str], int],
    crops_data: dict,
    animals_data: dict,
):
    """Stamp board + remaining queue into replan-horizon daily vectors."""
    tile = _tile_at(me, idx)
    qi = st.get("queue_idx", 0)
    lag = st.get("lag", 0)
    gap = st.get("gap", 0)

    out = _zero_daily(horizon)
    cash_by_day = [0] * horizon
    spend_by_day = [0] * horizon

    if _tile_occupied_for_lock(tile):
        seg = _stamp_locked_tile(tile, day, horizon, price_of, crops_data, animals_data)
        if seg:
            for key in ZERO_DAILY_KEYS:
                _add_daily(out[key], seg[key], horizon)
            _add_daily(cash_by_day, seg["cash_by_day"], horizon)
            _add_daily(spend_by_day, seg["spend_by_day"], horizon)

    raw = _queue_suffix_to_chain(queue, qi, lag, gap, day, horizon, me, idx)
    if raw:
        suffix_seg = _stamp_chain(raw, -1, horizon, price_of, crops_data, animals_data)
        for key in ZERO_DAILY_KEYS:
            _add_daily(out[key], suffix_seg[key], horizon)
        _add_daily(cash_by_day, suffix_seg["cash_by_day"], horizon)
        _add_daily(spend_by_day, suffix_seg["spend_by_day"], horizon)

    if not any(cash_by_day) and not any(sum(out[k]) for k in ZERO_DAILY_KEYS):
        return None
    return {
        "weight": sum(cash_by_day),
        "cash_by_day": cash_by_day,
        "spend_by_day": spend_by_day,
        **out,
    }


def _stamp_locked_tile(
    tile: dict,
    day: int,
    horizon: int,
    price_of: Callable[[str], int],
    crops_data: dict,
    animals_data: dict,
):
    if tile.get("kind") == "PLANT":
        crop = tile["crop"]
        current_age = day - tile["planted_day"]
        return _stamp_profile_segment(
            crop,
            CROP_PROFILE,
            0,
            current_age,
            horizon,
            price_of,
            crops_data,
            animals_data,
            charge_setup=False,
        )
    if tile.get("kind") in ("COOP", "PASTURE"):
        animal = tile.get("animal")
        if not animal:
            empty = _zero_daily(horizon)
            return {
                "weight": 0,
                "cash_by_day": [0] * horizon,
                "spend_by_day": [0] * horizon,
                **empty,
            }
        current_age = day - tile["placed_day"]
        return _stamp_profile_segment(
            animal,
            ANIMAL_PROFILE,
            0,
            current_age,
            horizon,
            price_of,
            crops_data,
            animals_data,
            charge_setup=False,
        )
    empty = _zero_daily(horizon)
    return {
        "weight": 0,
        "cash_by_day": [0] * horizon,
        "spend_by_day": [0] * horizon,
        **empty,
    }


def _empty_locked(horizon: int) -> dict:
    return _zero_daily(horizon) | {
        "cash_by_day": [0] * horizon,
        "spend_by_day": [0] * horizon,
    }


def _aggregate_locked(
    locked_by_worker: dict[str, dict],
    worker: str,
    seg: dict,
    horizon: int,
) -> None:
    for key in ZERO_DAILY_KEYS:
        _add_daily(locked_by_worker[worker][key], seg[key], horizon)
    _add_daily(locked_by_worker[worker]["cash_by_day"], seg["cash_by_day"], horizon)
    _add_daily(locked_by_worker[worker]["spend_by_day"], seg["spend_by_day"], horizon)


def _occupancy_end(profile_key: str, start_day: int, horizon: int) -> int:
    label, profile_name = _parse_profile_key(profile_key)
    if label in ANIMAL_NAMES:
        return horizon
    return start_day + rollouts.tile_free_age(label, profile_name)


def _tile_empty_for_replan(tile) -> bool:
    return tile is None or (
        isinstance(tile, dict) and tile.get("kind") == "WEED"
    )


def _tile_occupied_for_lock(tile) -> bool:
    if not isinstance(tile, dict):
        return False
    if tile.get("kind") == "PLANT":
        return True
    if tile.get("kind") in ("COOP", "PASTURE"):
        return bool(tile.get("animal"))
    return False


def _replan_eligible(idx: int, tile, st: dict, queues: dict) -> bool:
    if st.get("pending_dig"):
        return False
    if not _tile_empty_for_replan(tile):
        return False
    qi = st.get("queue_idx", 0)
    queue = queues.get(idx, [])
    # Empty at dawn but plan not started yet (e.g. animal tile before PLACE).
    return not (qi == 0 and queue)


def chain_to_queue_items(chain: list, horizon: int = NUM_DAYS) -> list:
    from agent.script import QueueItem

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


def _wsp_solver() -> bool:
    return solvers._wsp_solver()


def _active_hand_hires(solved_workers: tuple[str, ...]) -> int:
    return sum(1 for w in solved_workers if w != "farmer")


def update_zone_streaks(
    day: int,
    empty_counts: dict[str, int],
    zone_outcomes: dict[str, str],
) -> None:
    """Ratchet: N consecutive non-ok solves with empties → DEAD_HANDS."""
    global ZONE_SOLVE_STREAK, DEAD_HANDS
    for worker, outcome in zone_outcomes.items():
        if worker == "farmer":
            continue
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


def replan(obs: dict, tile_queues: dict, tile_state: dict | None = None) -> None:
    global NUM_ACTIVE_HIRES, BUY_LAND_DAY
    day = obs["day"]
    if day == 0 or day >= SEASON_LAST_DAY:
        return
    if _wsp_solver() and day < 3:
        return
    horizon = NUM_DAYS - day
    if horizon <= 0:
        return

    player = obs["player"]
    me = obs["farms"][player]
    ne_owned = _ne_owned(me)
    sw_owned = _sw_owned(me)
    land_owned = ne_owned  # twoland kwargs alias
    next_land_missing = not ne_owned or (
        solvers.CURRENT_SOLVER == "threeland_wsp" and not sw_owned
    )
    # Buy day consumed (market already ran) — re-arm probe for the next quadrant.
    if BUY_LAND_DAY is not None and day > BUY_LAND_DAY:
        BUY_LAND_DAY = None
    buy_morning = (
        BUY_LAND_DAY is not None and day == BUY_LAND_DAY and next_land_missing
    )

    st_map = tile_state or {}

    if not buy_morning and not any(
        _replan_eligible(i, _tile_at(me, i), st_map.get(i, {}), tile_queues)
        for i in range(NUM_TILES)
    ):
        return

    shops = obs.get("town", {}).get("unlocked_shops", [])
    market_prices = obs.get("market", {}).get("prices", {})

    crops_data = _load_json("crop_rollouts.json")
    animals_data = animal_rollouts.data()
    i0 = _i0_prices(crops_data, animals_data)
    opp_farm = obs["farms"][1 - player]
    opp_counts = _opponent_product_tile_counts(opp_farm)
    price_of = make_price_of(market_prices, shops, i0, opp_counts)

    if _wsp_solver():
        chains = []
        catalog_n = 0
    else:
        handmade_chains = dp_catalog.build_catalog(horizon, price_of)
        chains = _build_chains(crops_data, animals_data, handmade_chains, horizon, price_of)
        catalog_n = len(handmade_chains)

    replan_tiles = []
    locked_tiles = 0
    force_ne = 0
    force_sw = 0
    empty_counts = {w: 0 for w in WORKERS}
    locked_by_worker = {w: _empty_locked(horizon) for w in WORKERS}

    buying_ne = buy_morning and not ne_owned
    buying_sw = buy_morning and ne_owned and not sw_owned

    for idx in range(NUM_TILES):
        tile = _tile_at(me, idx)
        worker = worker_for_tile(idx)
        st = st_map.get(idx, {})
        ne_force = buying_ne and idx in _NE_TILES and tile == "LOCKED"
        sw_force = buying_sw and idx in _SW_TILES and tile == "LOCKED"
        if ne_force:
            force_ne += 1
        if sw_force:
            force_sw += 1
        if ne_force or sw_force or _replan_eligible(idx, tile, st, tile_queues):
            replan_tiles.append(idx)
            empty_counts[worker] += 1
        else:
            seg = _stamp_tile_commitment(
                idx, me, st, tile_queues.get(idx, []), day, horizon,
                price_of, crops_data, animals_data,
            )
            if seg:
                _aggregate_locked(locked_by_worker, worker, seg, horizon)
                locked_tiles += 1

    if not replan_tiles:
        print(
            f"[planner] replan d={day} skip assign locked={locked_tiles}",
            flush=True,
        )
        return

    assert sum(empty_counts.values()) == len(replan_tiles)

    shed = obs["private"]["shed"]
    w_open0 = int(shed.get("WHEAT", 0))
    f_open0 = int(shed.get("FERTILIZER", 0))

    from agent import script

    wheat_feed = script.total_wheat_feed_need(me, tile_state or {}, obs["private"])
    wheat_price = int(obs["market"]["prices"].get("WHEAT", 0) or 25)
    hire_target = NUM_ACTIVE_HIRES
    hire_reserve = sum(
        zoning.HAND_DAILY_COST.get(w, 0)
        for w in zoning.HAND_WORKERS[:hire_target]
    ) - sum(
        zoning.HAND_DAILY_COST.get(w, 0)
        for w in zoning.HAND_WORKERS[: len(me["hands"])]
    )
    hire_reserve = max(0, hire_reserve)
    feed_reserve = wheat_feed * wheat_price
    liquidity_floor = hire_reserve + feed_reserve * 3
    replan_min_balance = 0 if _wsp_solver() else liquidity_floor

    print(
        f"[planner] lands d={day} ne_owned={int(ne_owned)} sw_owned={int(sw_owned)} "
        f"buy_morning={int(buy_morning)} BUY_LAND_DAY={BUY_LAND_DAY} "
        f"force_ne={force_ne} force_sw={force_sw} empty={len(replan_tiles)}",
        flush=True,
    )

    result = solvers.solve(
        chains,
        horizon=horizon,
        empty_tiles=replan_tiles,
        empty_counts=empty_counts,
        locked_by_worker=locked_by_worker,
        starting_money=int(me["money"]),
        max_time=15.0,
        w_open0=w_open0,
        f_open0=f_open0,
        min_balance=replan_min_balance,
        track_shed=not _wsp_solver(),
        price_of=price_of,
        land_owned=land_owned,
        buy_morning=buy_morning,
        ne_owned=ne_owned,
        sw_owned=sw_owned,
    )

    if not result.complete and (
        not result.solved_workers or result.solved_workers[0] != WORKERS[0]
    ):
        print(
            f"[planner] replan d={day} INFEASIBLE keep={len(replan_tiles)} "
            f"active={','.join(result.solved_workers) or 'none'}",
            flush=True,
        )
        return

    n_written = solvers.apply_replan(
        result,
        replan_tiles,
        tile_queues,
        tile_state,
        horizon,
        chain_to_queue_items,
    )

    if buy_morning:
        if buying_ne:
            written = any(tile_queues.get(idx) for idx in _NE_TILES)
            label = "NE"
        else:
            written = any(tile_queues.get(idx) for idx in _SW_TILES)
            label = "SW"
        if not written:
            print(
                f"[planner] d={day} buy-morning {label} unwritten -> abort buy",
                flush=True,
            )
            BUY_LAND_DAY = None
        # On success keep BUY_LAND_DAY through this day (market + is_buy_morning_locked).
        # Cleared at next dawn when day > BUY_LAND_DAY so SW can probe.
    elif next_land_missing and BUY_LAND_DAY is None and result.buy_land:
        BUY_LAND_DAY = day + 1
        print(
            f"[planner] d={day} probe OK -> BUY_LAND_DAY={BUY_LAND_DAY}",
            flush=True,
        )

    ordered_hands = [w for w in WORKERS if w in zoning.HAND_WORKERS]
    update_zone_streaks(day, empty_counts, getattr(result, "zone_outcomes", {}) or {})
    # Hire depth = max hand index+1 among healthy solved hands with work.
    hire_depth = 0
    for w in ordered_hands:
        if (
            w in result.solved_workers
            and w not in DEAD_HANDS
            and _zone_has_work(me, w, tile_queues, result.assigned)
        ):
            hire_depth = max(hire_depth, ordered_hands.index(w) + 1)
    NUM_ACTIVE_HIRES = max(4, hire_depth)
    dead_note = ",".join(sorted(DEAD_HANDS)) if DEAD_HANDS else ""
    print(
        f"[planner] hires active={hire_depth} "
        f"NUM_ACTIVE_HIRES={NUM_ACTIVE_HIRES} "
        f"solved={','.join(result.solved_workers) or 'none'}"
        + (f" dead={dead_note}" if dead_note else ""),
        flush=True,
    )

    if replan_tiles:
        samples = []
        for idx in replan_tiles[:5]:
            chain = result.assigned.get(idx)
            if chain is None:
                samples.append(f"t{idx + 1}:keep")
                continue
            if not chain:
                samples.append(f"t{idx + 1}:IDLE")
                continue
            pl = ",".join(
                f"{_parse_profile_key(k)[0]}@{s}" for k, s in chain
            )
            samples.append(f"t{idx + 1}:{pl}")
        suffix = "" if result.complete else f" partial={len(result.solved_workers)}"
        print(f"[planner] replan assign {', '.join(samples)}{suffix}", flush=True)

    sub = {idx: result.assigned.get(idx, []) for idx in replan_tiles}
    _log_wsp_plan(day, horizon, result, sub)

    opp_log = " ".join(
        f"opp_{p}={n}" for p, n in sorted(opp_counts.items()) if n > 0
    )
    print(
        f"[planner] replan d={day} solver={solvers.CURRENT_SOLVER} "
        f"shops={len(shops)} catalog={catalog_n} "
        f"assign={n_written} locked={locked_tiles}"
        + (f" {opp_log}" if opp_log else ""),
        flush=True,
    )


def _build_from_solver() -> dict[int, list]:
    if solvers.CURRENT_SOLVER in ("twoland_wsp", "threeland_wsp"):
        empty_tiles = list(range(LAND1_TILE_COUNT))
        empty_counts = {
            w: (len(WORKER_TILES[w]) if w in LAND1_WORKERS else 0) for w in WORKERS
        }
    else:
        empty_tiles = list(range(NUM_TILES))
        empty_counts = {w: len(WORKER_TILES[w]) for w in WORKERS}
    locked_by_worker = {w: _empty_locked(NUM_DAYS) for w in WORKERS}
    if _wsp_solver():
        chains = []
        cascade_reserve = False
    else:
        crops_data = _load_json("crop_rollouts.json")
        animals_data = animal_rollouts.data()
        i0 = _i0_prices(crops_data, animals_data)
        price_of = make_price_of({}, [], i0)
        handmade_chains = dp_catalog.build_catalog(NUM_DAYS, price_of)
        chains = _build_chains(crops_data, animals_data, handmade_chains, NUM_DAYS, price_of)
        cascade_reserve = True
    result = solvers.solve(
        chains,
        horizon=NUM_DAYS,
        empty_tiles=empty_tiles,
        empty_counts=empty_counts,
        locked_by_worker=locked_by_worker,
        starting_money=STARTING_MONEY,
        max_time=20.0,
        cascade_reserve=cascade_reserve,
    )
    if not result.solved_workers or result.solved_workers[0] != WORKERS[0]:
        active = ",".join(result.solved_workers) or "none"
        raise RuntimeError(
            f"day-0 {solvers.CURRENT_SOLVER} farmer failed: active={active}"
        )

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
            if zoning.CURRENT in (zoning.FIVE, zoning.TWO, zoning.THREE):
                raise RuntimeError(
                    f"day-0 solver failed on {zoning.CURRENT} layout (no empty fallback): {exc}"
                ) from exc
            print(f"[planner] fallback to script queues: {exc}", flush=True)
            _cached_queues = fallback()
    return _cached_queues
