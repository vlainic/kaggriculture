"""Market orders for scripted one-land agent."""

from __future__ import annotations

from collections import Counter

from agent import animal_rollouts, planner, pricing, rollouts, script, sell_dp, workers, zoning
from agent.script import TILE_QUEUES, QueueItem

MAX_ORDERS = 10
SELLABLE = frozenset(
    rollouts.CROP_NAMES + animal_rollouts.ANIMAL_PRODUCTS + ("FERTILIZER",)
)
LIVESTOCK = frozenset(animal_rollouts.animal_names())
PREMIUM_DRIP = frozenset(sell_dp.PREMIUM_PRODUCTS)
STAPLE_DUMP = frozenset(sell_dp.STAPLE_PRODUCTS)
DRIP_PER_HOUR = 1


def _ne_owned(me: dict) -> bool:
    return "NE" in me.get("unlocked_quadrants", [])


def _sw_owned(me: dict) -> bool:
    return "SW" in me.get("unlocked_quadrants", [])


def _land2_owned(me: dict) -> bool:
    return _ne_owned(me)


def _next_buy_cost(me: dict) -> int | None:
    if not _ne_owned(me):
        return zoning.LAND2_BUY_COST
    if zoning.USE_THREE and not _sw_owned(me):
        return zoning.LAND3_BUY_COST
    return None


def _target_hires(me: dict, day: int) -> int:
    del me, day
    return planner.NUM_ACTIVE_HIRES


def _hire_batches_land12(base: int) -> tuple[int, int]:
    """Split land1+2 hires (base ≤ 9) across h0/h1."""
    if base <= 2:
        return (base, 0)
    if base == 3:
        return (2, 1)
    if base == 4:
        return (2, 2)
    if base == 5:
        return (2, 3)
    if base == 7:
        return (3, 4)
    if base == 9:
        return (4, 5)
    h0 = base // 2
    h1 = base - h0
    return (h0, h1)


def _hire_batches(target: int) -> tuple[int, int, int]:
    """target = total hands to have today (NUM_ACTIVE_HIRES)."""
    base = min(target, 9)
    h0, h1 = _hire_batches_land12(base)
    h2 = max(0, target - 9)
    return h0, h1, h2


def _hires_this_hour(hour: int, target: int, current_hands: int) -> int:
    if current_hands >= target:
        return 0
    h0, h1, h2 = _hire_batches(target)
    if hour == 0:
        return min(h0, target - current_hands)
    if hour == 1:
        return min(h1, target - current_hands)
    if hour == 2:
        return min(h2, target - current_hands)
    return 0


def _active_hire_reserve(target_hires: int, current_hands: int) -> int:
    reserve = 0
    for i in range(current_hands, target_hires):
        if i < len(workers.HAND_WORKERS):
            reserve += zoning.HAND_DAILY_COST.get(workers.HAND_WORKERS[i], 0)
    return reserve


def _tile_at(me: dict, idx: int):
    x, y = workers.TILE_COORDS[idx]
    return me["tiles"][y][x]


def _tile_empty(me: dict, idx: int, *, day: int) -> bool:
    tile = _tile_at(me, idx)
    if tile is None:
        return True
    if isinstance(tile, dict) and tile.get("kind") == "WEED":
        return True
    if planner.is_buy_morning_locked(tile, idx, day, me):
        return True
    return False


def _count_live_animals(me: dict) -> int:
    return sum(
        1
        for idx in range(workers.NUM_TILES)
        if isinstance(_tile_at(me, idx), dict) and _tile_at(me, idx).get("animal")
    )


def _count_animals_placing_today(
    me: dict,
    day: int,
    tile_state: dict,
) -> int:
    n = 0
    for idx in range(workers.NUM_TILES):
        st = tile_state.get(idx, {})
        animal = _needs_animal_today(
            idx, day, me, st.get("queue_idx", 0), st.get("lag", 0), st.get("gap", 0)
        )
        if animal:
            n += 1
    return n


def _needs_plant_today(
    idx: int,
    queue_idx: int,
    lag: int,
    gap: int,
    pending_dig: bool,
    empty_at_dawn: set[int],
    dig_plant_ok: bool,
) -> QueueItem | None:
    if lag > 0 or gap > 0 or pending_dig:
        return None
    if not tile_ops_can_start(idx, empty_at_dawn, dig_plant_ok):
        return None
    queue = TILE_QUEUES.get(idx, [])
    if queue_idx >= len(queue):
        return None
    item = queue[queue_idx]
    if item.kind != "crop":
        return None
    return item


def tile_ops_can_start(idx: int, empty_at_dawn: set[int], dig_plant_ok: bool) -> bool:
    return idx in empty_at_dawn or dig_plant_ok


def _needs_animal_today(
    idx: int,
    day: int,
    me: dict,
    queue_idx: int,
    lag: int,
    gap: int,
) -> QueueItem | None:
    if lag > 0 or gap > 0:
        return None
    queue = TILE_QUEUES.get(idx, [])
    if queue_idx >= len(queue):
        return None
    item = queue[queue_idx]
    if item.kind != "animal":
        return None
    tile = _tile_at(me, idx)
    if tile is None:
        return item
    if planner.is_buy_morning_locked(tile, idx, day, me):
        return item
    if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
        if not tile.get("animal"):
            return item
    return None


def _needs_build_today(
    idx: int,
    me: dict,
    day: int,
    queue_idx: int,
    lag: int,
    gap: int,
) -> QueueItem | None:
    if lag > 0 or gap > 0:
        return None
    queue = TILE_QUEUES.get(idx, [])
    if queue_idx >= len(queue):
        return None
    item = queue[queue_idx]
    if item.kind != "animal":
        return None
    tile = _tile_at(me, idx)
    if tile is None:
        return item
    if planner.is_buy_morning_locked(tile, idx, day, me):
        return item
    return None


def needed_buys(
    me: dict,
    private: dict,
    day: int,
    tile_state: dict,
    empty_at_dawn: set[int],
) -> tuple[Counter[str], Counter[str], int]:
    """Return (seeds, animals, wheat_pickup_need)."""
    seeds: Counter[str] = Counter()
    animals: Counter[str] = Counter()
    wheat_need = 0

    for idx in range(workers.NUM_TILES):
        st = tile_state.get(idx, {})
        qi = st.get("queue_idx", 0)
        lag = st.get("lag", 0)
        gap = st.get("gap", 0)
        pending_dig = st.get("pending_dig", False)
        dig_plant_ok = st.get("dig_plant_ok", False)

        crop = _needs_plant_today(
            idx, qi, lag, gap, pending_dig, empty_at_dawn, dig_plant_ok
        )
        if crop and _tile_empty(me, idx, day=day):
            seeds[crop.label] += 1

        animal = _needs_animal_today(idx, day, me, qi, lag, gap)
        if animal:
            animals[animal.label] += 1

    wheat_need = script.total_wheat_feed_need(me, tile_state, private, day=day)

    return seeds, animals, wheat_need


def build_orders(
    obs: dict,
    me: dict,
    private: dict,
    day: int,
    hour: int,
    tile_state: dict,
    empty_at_dawn: set[int] | None = None,
) -> list[list]:
    prices = obs["market"]["prices"]
    orders: list[list] = []
    dawn = empty_at_dawn if empty_at_dawn is not None else set()

    target_hires = _target_hires(me, day)
    if hour in (0, 1, 2):
        if hour == 0:
            h0, h1, h2 = _hire_batches(target_hires)
            dead = ",".join(sorted(planner.DEAD_HANDS)) if planner.DEAD_HANDS else ""
            print(
                f"[market] hire_batches target={target_hires} "
                f"h0={h0} h1={h1} h2={h2}"
                + (f" dead={dead}" if dead else ""),
                flush=True,
            )
        hires_needed = _hires_this_hour(hour, target_hires, len(me["hands"]))
        for _ in range(hires_needed):
            orders.append(["HIRE"])

    buy_cost = _next_buy_cost(me)
    if (
        hour == 0
        and planner.BUY_LAND_DAY is not None
        and day == planner.BUY_LAND_DAY
        and buy_cost is not None
    ):
        orders.insert(0, ["BUY_LAND"])

    needed_seeds, needed_animals, wheat_need = needed_buys(
        me, private, day, tile_state, dawn
    )
    wheat_feed_need = script.total_wheat_feed_need(me, tile_state, private, day=day)
    live_animals = _count_live_animals(me)
    wheat_reserve = max(wheat_feed_need, live_animals)

    seeds = private["seeds"]
    shed = private["shed"]
    money = int(me["money"])
    buy_land_reserved = 0
    if (
        planner.BUY_LAND_DAY is not None
        and day == planner.BUY_LAND_DAY
        and buy_cost is not None
    ):
        buy_land_reserved = buy_cost
        money = max(0, money - buy_land_reserved)
    wheat_price = int(prices.get("WHEAT", 0) or 25)
    feed_reserve = wheat_reserve * wheat_price
    hire_reserve = _active_hire_reserve(target_hires, len(me["hands"]))
    spendable = max(0, money - feed_reserve - hire_reserve)

    if hour == 0 and day < script.SEASON_LAST_DAY:
        wheat_in_shed = shed.get("WHEAT", 0)
        dawn_wheat_need = wheat_feed_need
        if wheat_in_shed < dawn_wheat_need + 1:
            deficit = dawn_wheat_need + 1 - wheat_in_shed
            cost = wheat_price
            buy = min(deficit, money // cost) if cost else 0
            if buy > 0:
                orders.append(["BUY_PRODUCT", "WHEAT", buy])
                money -= buy * cost
                spendable = max(0, money - feed_reserve - hire_reserve)

    if day < script.SEASON_LAST_DAY:
        for crop, count in needed_seeds.items():
            deficit = count - seeds.get(crop, 0)
            if deficit <= 0:
                continue
            cost = rollouts.seed_cost(crop)
            buy = min(deficit, spendable // cost) if cost else 0
            if buy > 0:
                orders.append(["BUY_SEED", crop, buy])
                spendable -= buy * cost
                money -= buy * cost

        for animal, count in needed_animals.items():
            in_shed = shed.get(animal, 0)
            in_inv = sum(inv.get(animal, 0) for inv in private["inventories"])
            deficit = count - in_shed - in_inv
            if deficit <= 0:
                continue
            cost = animal_rollouts.animal_cost(animal)
            buy = min(deficit, spendable // cost) if cost else 0
            if buy > 0:
                orders.append(["BUY_ANIMAL", animal, buy])
                spendable -= buy * cost
                money -= buy * cost

        wheat_in_shed = shed.get("WHEAT", 0)
        if wheat_need > wheat_in_shed:
            deficit = wheat_need - wheat_in_shed
            cost = int(prices.get("WHEAT", 0) or 0)
            buy = min(deficit, money // cost) if cost else 0
            if buy > 0:
                orders.append(["BUY_PRODUCT", "WHEAT", buy])
                money -= buy * cost

    sells = _sell_orders(
        private, me, day, hour, wheat_reserve, prices, obs["market"]["inventory"]
    )
    if len(orders) + len(sells) > MAX_ORDERS:
        sells = sells[: max(0, MAX_ORDERS - len(orders))]
    orders.extend(sells)

    out = orders[:MAX_ORDERS]
    if hour == 0 and buy_land_reserved:
        wheat_buys = sum(
            o[2] for o in out if len(o) >= 3 and o[0] == "BUY_PRODUCT" and o[1] == "WHEAT"
        )
        capped = len(orders) > MAX_ORDERS
        print(
            f"[market] d={day} BUY_LAND reserved={buy_land_reserved} "
            f"wheat={wheat_buys} orders={len(out)}/{MAX_ORDERS}"
            + (" buys_capped_before_sells" if capped else ""),
            flush=True,
        )
    return out


def _staple_sell_orders(
    private: dict,
    market_inv: dict,
    day: int,
    wheat_feed_need: int = 0,
    *,
    hour: int = 0,
) -> list[list]:
    """Dump staples immediately when above price floor (wheat keeps feed reserve)."""
    shed = private["shed"]
    sells: list[list] = []
    for product, count in sorted(shed.items()):
        if count <= 0 or product not in STAPLE_DUMP or product in LIVESTOCK:
            continue
        if product == "WHEAT" and hour < 5:
            continue
        inv = int(market_inv.get(product, pricing.I0_DEFAULT))
        qty = pricing.allowed_sell_qty(
            product,
            inv,
            count,
            day,
            mode="dump",
            wheat_reserve=wheat_feed_need if product == "WHEAT" else 0,
            max_sell_per_day=sell_dp.MAX_SELL_PER_DAY,
            liquidate_from_day=sell_dp.LIQUIDATE_FROM_DAY,
            floor_ratio=sell_dp.PRICE_FLOOR_RATIO,
        )
        if qty > 0:
            sells.append(["SELL", product, qty])
    return sells


def _premium_sell_orders(
    private: dict,
    day: int,
    wheat_feed_need: int = 0,
    *,
    use_dp: bool,
) -> list[list]:
    shed = private["shed"]
    sells: list[list] = []
    for product in sorted(PREMIUM_DRIP):
        count = shed.get(product, 0)
        if count <= 0:
            continue
        qty: int | None
        if use_dp:
            qty = sell_dp.plan_sell_qty(
                product,
                day,
                count,
                wheat_feed_need,
                premium_drip=True,
            )
            if qty is None:
                qty = min(count, DRIP_PER_HOUR)
        else:
            qty = min(count, DRIP_PER_HOUR)
        if qty > 0:
            sells.append(["SELL", product, qty])
            if use_dp:
                sell_dp.commit_sell(product, qty)
    return sells


def _drip_fallback_sell_orders(
    private: dict,
    market_inv: dict,
    day: int,
    wheat_feed_need: int = 0,
    *,
    hour: int = 0,
) -> list[list]:
    """Legacy drip/dump when sell DP schedule is inactive."""
    return _staple_sell_orders(
        private, market_inv, day, wheat_feed_need, hour=hour
    ) + _premium_sell_orders(private, day, wheat_feed_need, use_dp=False)


def _sell_orders(
    private: dict,
    me: dict,
    day: int,
    hour: int,
    wheat_feed_need: int = 0,
    prices: dict | None = None,
    market_inv: dict | None = None,
) -> list[list]:
    shed = private["shed"]
    sells: list[list] = []

    if day >= script.SEASON_LAST_DAY:
        candidates = [
            (product, count)
            for product, count in shed.items()
            if count > 0 and product in SELLABLE and product not in LIVESTOCK
        ]
        if not candidates:
            return sells
        price_map = prices or {}
        candidates.sort(
            key=lambda x: x[1] * int(price_map.get(x[0], 0) or 0),
            reverse=True,
        )
        start = hour % len(candidates)
        rotated = candidates[start:] + candidates[:start]
        for product, count in rotated[:MAX_ORDERS]:
            sells.append(["SELL", product, count])
        return sells

    inv = market_inv if market_inv is not None else {}

    if not sell_dp.schedule_active(day):
        return _drip_fallback_sell_orders(
            private, inv, day, wheat_feed_need, hour=hour
        )

    sells = _staple_sell_orders(
        private, inv, day, wheat_feed_need, hour=hour
    )
    sells.extend(_premium_sell_orders(private, day, wheat_feed_need, use_dp=True))
    return sells


def defer_farmer_hour0(hour: int, orders: list[list], me: dict, day: int) -> bool:
    """Engine runs farmer before market on h=0 — PASS until buys execute."""
    if day >= script.SEASON_LAST_DAY:
        return False
    if hour != 0:
        return False
    if len(me["hands"]) < 2:
        return True
    for order in orders:
        if order and order[0] in (
            "BUY_SEED",
            "BUY_ANIMAL",
            "BUY_PRODUCT",
            "HIRE",
            "BUY_LAND",
        ):
            return True
    return False
