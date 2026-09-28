"""Market orders for milos farmer-only agent."""

from __future__ import annotations

from collections import Counter

from milos import animal_rollouts, planner, pricing, rollouts, script, sell_dp, workers
from milos.script import TILE_QUEUES, QueueItem

MAX_ORDERS = 10
SELLABLE = frozenset(
    rollouts.CROP_NAMES + animal_rollouts.ANIMAL_PRODUCTS + ("FERTILIZER",)
)
LIVESTOCK = frozenset(animal_rollouts.animal_names())
PREMIUM_DRIP = frozenset(sell_dp.PREMIUM_PRODUCTS)
STAPLE_DUMP = frozenset(sell_dp.STAPLE_PRODUCTS)
DRIP_PER_HOUR = 1
FERT_SHED_CAP = 10


def _fert_reserve(
    me: dict, tile_state: dict, private: dict, day: int
) -> int:
    need = 0
    for w in workers.WORKERS:
        inv_idx = workers.inventory_index(w)
        invs = private.get("inventories", [])
        hand_inv = invs[inv_idx] if inv_idx < len(invs) else {}
        need += script.zone_fert_pickup_needed(
            me, w, tile_state, hand_inv, day=day
        )
    return max(FERT_SHED_CAP, need)


def _fert_dump_orders(shed: dict, reserve: int) -> list[list]:
    excess = int(shed.get("FERTILIZER", 0)) - reserve
    if excess <= 0:
        return []
    return [["SELL", "FERTILIZER", excess]]


def _make_room_sells(shed: dict, prices: dict, need: int) -> list[list]:
    if need <= 0:
        return []
    pool = sorted(
        (
            p
            for p, n in shed.items()
            if n > 0 and p in SELLABLE and p not in LIVESTOCK and p != "WHEAT"
        ),
        key=lambda p: int(prices.get(p, 0) or 0),
    )
    out: list[list] = []
    for product in pool:
        if need <= 0:
            break
        qty = min(need, int(shed.get(product, 0)))
        if qty <= 0:
            continue
        out.append(["SELL", product, qty])
        need -= qty
        shed[product] = shed.get(product, 0) - qty
    return out


def _tile_at(me: dict, idx: int):
    x, y = workers.TILE_COORDS[idx]
    return me["tiles"][y][x]


def _tile_empty(me: dict, idx: int, *, day: int) -> bool:
    tile = _tile_at(me, idx)
    if tile is None:
        return True
    if isinstance(tile, dict) and tile.get("kind") == "WEED":
        return True
    return planner.is_buy_morning_locked(tile, idx, day, me)


def _count_live_animals(me: dict) -> int:
    return sum(
        1
        for idx in range(workers.NUM_TILES)
        if isinstance(_tile_at(me, idx), dict) and _tile_at(me, idx).get("animal")
    )


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
    if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE") and not tile.get("animal"):
        return item
    return None


def needed_buys(
    me: dict,
    day: int,
    tile_state: dict,
    empty_at_dawn: set[int],
) -> tuple[Counter[str], Counter[str]]:
    """Return (seeds, animals) needed for today's queue heads."""
    seeds: Counter[str] = Counter()
    animals: Counter[str] = Counter()

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

    return seeds, animals


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

    needed_seeds, needed_animals = needed_buys(me, day, tile_state, dawn)
    wheat_feed_need = script.total_wheat_feed_need(me, tile_state, private, day=day)
    live_animals = _count_live_animals(me)
    wheat_reserve = max(wheat_feed_need, live_animals)

    seeds = private["seeds"]
    shed = private["shed"]
    money = int(me["money"])
    wheat_price = int(prices.get("WHEAT", 0) or 25)
    spendable = max(0, money - wheat_reserve * wheat_price)

    buy_land_reserved = 0
    if hour == 0 and day <= script.SEASON_LAST_DAY:
        if (
            planner.BUY_LAND_DAY is not None
            and day == planner.BUY_LAND_DAY
            and "NE" not in me.get("unlocked_quadrants", [])
        ):
            orders.append(["BUY_LAND"])
            buy_land_reserved = planner.NE_LAND_COST
            money = max(0, money - buy_land_reserved)
            spendable = max(0, money - wheat_reserve * wheat_price)
        for _ in range(planner.NUM_ACTIVE_HIRES):
            orders.append(["HIRE"])

    if (
        hour == 1
        and day <= script.SEASON_LAST_DAY
        and "NE" in me.get("unlocked_quadrants", [])
    ):
        for _ in range(len(planner.ACTIVE_NE)):
            orders.append(["HIRE"])

    shed_for_sells: dict | None = None
    if day < script.SEASON_LAST_DAY and hour in (0, 1):
        shed_plan = dict(shed)
        buy_orders: list[list] = []

        deficit = wheat_feed_need - int(shed_plan.get("WHEAT", 0))
        if deficit > 0:
            buy = min(deficit, money // wheat_price) if wheat_price else 0
            if buy > 0:
                buy_orders.append(["BUY_PRODUCT", "WHEAT", buy])
                money -= buy * wheat_price
                spendable = max(0, money - wheat_reserve * wheat_price)

        for animal, count in needed_animals.items():
            in_shed = shed_plan.get(animal, 0)
            in_inv = sum(inv.get(animal, 0) for inv in private["inventories"])
            deficit = count - in_shed - in_inv
            if deficit <= 0:
                continue
            cost = animal_rollouts.animal_cost(animal)
            buy = min(deficit, spendable // cost) if cost else 0
            if buy > 0:
                buy_orders.append(["BUY_ANIMAL", animal, buy])
                spendable -= buy * cost
                money -= buy * cost

        for crop, count in needed_seeds.items():
            deficit = count - seeds.get(crop, 0)
            if deficit <= 0:
                continue
            cost = rollouts.seed_cost(crop)
            buy = min(deficit, spendable // cost) if cost else 0
            if buy > 0:
                buy_orders.append(["BUY_SEED", crop, buy])
                spendable -= buy * cost
                money -= buy * cost

        deposit_units = sum(
            int(o[2])
            for o in buy_orders
            if o[0] in ("BUY_PRODUCT", "BUY_ANIMAL")
        )
        free = sell_dp.SHED_CAP - sum(shed_plan.values())
        if deposit_units > free:
            orders.extend(_make_room_sells(shed_plan, prices, deposit_units - free))

        orders.extend(buy_orders)
        shed_for_sells = shed_plan

    sells = _sell_orders(
        private,
        me,
        day,
        hour,
        wheat_reserve,
        prices,
        obs["market"]["inventory"],
        tile_state=tile_state,
        shed=shed_for_sells,
    )
    combined_len = len(orders) + len(sells)
    if combined_len > MAX_ORDERS:
        dropped = combined_len - MAX_ORDERS
        print(
            f"[market] overflow d={day} h={hour} dropped={dropped} "
            f"had={combined_len} cap={MAX_ORDERS}",
            flush=True,
        )
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
    skip_fertilizer: bool = False,
) -> list[list]:
    """Dump staples immediately when above price floor (wheat keeps feed reserve)."""
    shed = private["shed"]
    sells: list[list] = []
    for product, count in sorted(shed.items()):
        if count <= 0 or product not in STAPLE_DUMP or product in LIVESTOCK:
            continue
        if skip_fertilizer and product == "FERTILIZER":
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
    skip_fertilizer: bool = False,
) -> list[list]:
    """Legacy drip/dump when sell DP schedule is inactive."""
    return _staple_sell_orders(
        private,
        market_inv,
        day,
        wheat_feed_need,
        hour=hour,
        skip_fertilizer=skip_fertilizer,
    ) + _premium_sell_orders(private, day, wheat_feed_need, use_dp=False)


def _sell_orders(
    private: dict,
    me: dict,
    day: int,
    hour: int,
    wheat_feed_need: int = 0,
    prices: dict | None = None,
    market_inv: dict | None = None,
    *,
    tile_state: dict | None = None,
    shed: dict | None = None,
) -> list[list]:
    shed_work = dict(shed if shed is not None else private["shed"])
    private_adj = {**private, "shed": shed_work}
    sells: list[list] = []

    if day < script.SEASON_LAST_DAY and tile_state is not None:
        reserve = _fert_reserve(me, tile_state, private, day)
        fert = _fert_dump_orders(shed_work, reserve)
        sells.extend(fert)
        if fert:
            shed_work["FERTILIZER"] = shed_work.get("FERTILIZER", 0) - int(fert[0][2])
        private_adj = {**private, "shed": shed_work}
        skip_fert = True
    else:
        skip_fert = False

    if day >= script.SEASON_LAST_DAY:
        candidates = [
            (product, count)
            for product, count in shed_work.items()
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
        sells.extend(
            _drip_fallback_sell_orders(
                private_adj,
                inv,
                day,
                wheat_feed_need,
                hour=hour,
                skip_fertilizer=skip_fert,
            )
        )
        return sells

    sells.extend(
        _staple_sell_orders(
            private_adj,
            inv,
            day,
            wheat_feed_need,
            hour=hour,
            skip_fertilizer=skip_fert,
        )
    )
    sells.extend(
        _premium_sell_orders(private_adj, day, wheat_feed_need, use_dp=True)
    )
    return sells


def defer_farmer_hour0(hour: int, day: int) -> bool:
    """Engine runs farmer before market on h=0 — always PASS until market hour."""
    return hour == 0 and day < script.SEASON_LAST_DAY
