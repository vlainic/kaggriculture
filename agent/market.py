"""Market orders for scripted one-land agent."""

from __future__ import annotations

from collections import Counter

from agent import animal_rollouts, pricing, rollouts, script, sell_dp, workers, zoning
from agent.script import TILE_QUEUES, QueueItem

MAX_ORDERS = 10
SELLABLE = frozenset(
    rollouts.CROP_NAMES + animal_rollouts.ANIMAL_PRODUCTS + ("FERTILIZER",)
)
LIVESTOCK = frozenset(animal_rollouts.animal_names())
PREMIUM_DRIP = frozenset(sell_dp.PREMIUM_PRODUCTS)
STAPLE_DUMP = frozenset(sell_dp.STAPLE_PRODUCTS)
DRIP_PER_HOUR = 1
HIRE_COST = zoning.HIRE_DAILY_COST


def _tile_at(me: dict, idx: int):
    x, y = workers.TILE_COORDS[idx]
    return me["tiles"][y][x]


def _tile_empty(me: dict, idx: int) -> bool:
    tile = _tile_at(me, idx)
    return tile is None or (isinstance(tile, dict) and tile.get("kind") == "WEED")


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
    if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
        if not tile.get("animal"):
            return item
    return None


def _needs_build_today(
    idx: int,
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
        if crop and _tile_empty(me, idx):
            seeds[crop.label] += 1

        animal = _needs_animal_today(idx, day, me, qi, lag, gap)
        if animal:
            animals[animal.label] += 1

    wheat_need = script.total_wheat_feed_need(me, tile_state, private)

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

    if hour in (0, 1):
        hires_needed = min(2, workers.NUM_HIRES - len(me["hands"]))
        for _ in range(hires_needed):
            orders.append(["HIRE"])

    needed_seeds, needed_animals, wheat_need = needed_buys(
        me, private, day, tile_state, dawn
    )
    wheat_feed_need = script.total_wheat_feed_need(me, tile_state, private)
    live_animals = _count_live_animals(me)
    wheat_reserve = max(wheat_feed_need, live_animals)

    seeds = private["seeds"]
    shed = private["shed"]
    money = int(me["money"])
    wheat_price = int(prices.get("WHEAT", 0) or 25)
    feed_reserve = wheat_reserve * wheat_price
    hire_reserve = HIRE_COST * max(0, workers.NUM_HIRES - len(me["hands"]))
    spendable = max(0, money - feed_reserve - hire_reserve)

    if hour == 0 and day < script.SEASON_LAST_DAY:
        wheat_in_shed = shed.get("WHEAT", 0)
        placing_today = _count_animals_placing_today(me, day, tile_state)
        dawn_wheat_need = live_animals + placing_today
        if wheat_in_shed < dawn_wheat_need:
            deficit = dawn_wheat_need - wheat_in_shed
            cost = wheat_price
            buy = min(deficit, money // cost, MAX_ORDERS - len(orders)) if cost else 0
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

    return orders[:MAX_ORDERS]


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
        if order and order[0] in ("BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT", "HIRE"):
            return True
    return False
