"""Daily per-product sell DP with dawn MPC replan (premium goods only)."""

from __future__ import annotations

import time

from milos import (
    animal_rollouts,
    drain_calib,
    envconfig,
    fix_flags,
    pricing,
    rollouts,
    tile_ops,
    workers,
)

SHED_CAP = 100  # default; live cap from envconfig.shed_capacity() after ingest

PREMIUM_PRODUCTS: tuple[str, ...] = ("MELON", "STRAWBERRY", "MILK", "WOOL")
STAPLE_PRODUCTS: tuple[str, ...] = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "EGG",
    "FERTILIZER",
)
SELL_PRODUCTS: tuple[str, ...] = PREMIUM_PRODUCTS + STAPLE_PRODUCTS

INV_PAD_LO = 40
INV_PAD_HI = 80
# Speculative future shop unlock credit (re-draws mean not every unlock is new).
P_NEW_SHOP = 0.35
OPP_EMA_ALPHA = 0.35
SEASON_LAST_DAY = 29
CROP_PROFILE = "no_fert"
ANIMAL_PROFILE = "with_care"
HOLD_COST = 2
DP_HORIZON = 8
MAX_SELL_PER_DAY = 24
REPLAN_TIME_BUDGET_S = 0.080
PRICE_FLOOR_RATIO = 0.5
LIQUIDATE_FROM_DAY = 27

_ALL_SHOPS = tuple(rollouts.SHOP_PRODUCT_DEMAND.keys())
_TOWN_CENTER_PRODUCTS = tuple(p for p in SELL_PRODUCTS if p != "FERTILIZER")

OPP_DUMP_THRESHOLD = 0.05
WOOL_SOFT_CAP = 20

_schedule: dict | None = None
_prev_market_inv: dict[str, int] | None = None
_prev_unlocked_shops: list[str] | None = None
_our_sells_yesterday: dict[str, int] = {p: 0 for p in SELL_PRODUCTS}
_opp_ema: dict[str, float] = {p: 0.0 for p in SELL_PRODUCTS}
_opp_last: dict[str, float] = {p: 0.0 for p in SELL_PRODUCTS}
_lead_suppress: dict = {"due_step": -1, "qty": {}}
_lead_carry: dict[str, int] = {p: 0 for p in PREMIUM_PRODUCTS}
_dawn_quote: dict[str, int] = {}
GREEDY_THETA = 0.85
GREEDY_THETA_LIQ = 0.3
GREEDY_THETA_BY_PRODUCT: dict[str, float] = {"MELON": 0.65}
GREEDY_TARGET_LO = 40
GREEDY_TARGET_HI = 70
GREEDY_TARGET_MARGIN = 10


def reset_episode() -> None:
    global _schedule, _prev_market_inv, _prev_unlocked_shops, _our_sells_yesterday
    global _opp_ema, _opp_last, _lead_suppress, _lead_carry, _dawn_quote
    _schedule = None
    _prev_market_inv = None
    _prev_unlocked_shops = None
    _our_sells_yesterday = {p: 0 for p in SELL_PRODUCTS}
    _opp_ema = {p: 0.0 for p in SELL_PRODUCTS}
    _opp_last = {p: 0.0 for p in SELL_PRODUCTS}
    _lead_suppress = {"due_step": -1, "qty": {}}
    _lead_carry = {p: 0 for p in PREMIUM_PRODUCTS}
    _dawn_quote = {}
    drain_calib.reset_episode()


def note_dawn_quotes(market_inv: dict, day: int, hour: int) -> None:
    """Capture dawn quotes for greedy THETA anchor (once per day at h=0)."""
    if hour != 0:
        return
    global _dawn_quote
    for product in PREMIUM_PRODUCTS:
        inv = int(market_inv.get(product, pricing.I0_DEFAULT))
        _dawn_quote[product] = pricing.quoted(product, inv)


def _greedy_shed_target(
    day: int,
    *,
    premium_inflow: dict[str, int] | None,
    hour: int = 0,
    hand_inv_units: int = 0,
) -> tuple[int, float]:
    cap = shed_cap()
    if day >= LIQUIDATE_FROM_DAY:
        return 0, GREEDY_THETA_LIQ
    extra = sum((premium_inflow or {}).values())
    target = cap - extra - GREEDY_TARGET_MARGIN
    target = max(GREEDY_TARGET_LO, min(GREEDY_TARGET_HI, target))
    if hour >= 12 and hand_inv_units > 0:
        harvest_room = max(0, cap - hand_inv_units - GREEDY_TARGET_MARGIN)
        target = min(target, harvest_room)
    return target, GREEDY_THETA


def _shed_total(shed: dict) -> int:
    return sum(int(v) for v in shed.values())


def _greedy_room_products(hour: int) -> tuple[str, ...]:
    staples: tuple[str, ...] = ("CARROT", "TOMATO", "EGG")
    if hour >= 5:
        return staples + ("WHEAT", "FERTILIZER")
    return staples + ("FERTILIZER",)


def greedy_premium_sells(
    shed: dict,
    market_inv: dict,
    day: int,
    *,
    premium_inflow: dict[str, int] | None = None,
    hour: int = 0,
    hand_inv_units: int = 0,
    fert_reserve: int = 10,
    wheat_reserve: int = 0,
) -> dict[str, int]:
    """Water-fill sells for this hour; mutates shed. One batch per product."""
    target, theta = _greedy_shed_target(
        day,
        premium_inflow=premium_inflow,
        hour=hour,
        hand_inv_units=hand_inv_units,
    )
    working = {k: int(v) for k, v in shed.items()}
    virtual_inv = {
        p: int(market_inv.get(p, pricing.I0_DEFAULT)) for p in SELL_PRODUCTS
    }
    out: dict[str, int] = {}
    max_steps = _shed_total(working)
    for _ in range(max_steps):
        total = _shed_total(working)
        room = total > target
        best_p: str | None = None
        best_m = -1
        products = list(PREMIUM_PRODUCTS)
        if room:
            products.extend(_greedy_room_products(hour))
        seen: set[str] = set()
        for product in products:
            if product in seen:
                continue
            seen.add(product)
            cnt = int(working.get(product, 0))
            if product == "FERTILIZER":
                cnt = max(0, cnt - fert_reserve)
            elif product == "WHEAT":
                cnt = max(0, cnt - wheat_reserve)
            if cnt <= 0:
                continue
            inv = virtual_inv.get(product, pricing.I0_DEFAULT)
            marginal = pricing.marginal_price(product, inv)
            floor = pricing.price_floor(product, PRICE_FLOOR_RATIO)
            if marginal < floor:
                continue
            base = pricing.base_price(product)
            theta_p = GREEDY_THETA_BY_PRODUCT.get(product, theta)
            good_price = marginal >= theta_p * base
            if product in PREMIUM_PRODUCTS:
                if not good_price and not room:
                    continue
            elif not room:
                continue
            if marginal > best_m:
                best_m = marginal
                best_p = product
        if best_p is None:
            break
        inv = virtual_inv[best_p]
        working[best_p] = int(working.get(best_p, 0)) - 1
        out[best_p] = out.get(best_p, 0) + 1
        price = pricing.marginal_price(best_p, inv)
        if price > 1:
            virtual_inv[best_p] = inv + 1
    for product, qty in out.items():
        shed[product] = int(shed.get(product, 0)) - qty
    return out


def _hold_cost() -> int:
    return 10 if fix_flags.fix_sell() else HOLD_COST


def _inv_pad_lo() -> int:
    return 120 if fix_flags.fix_sell() else INV_PAD_LO


def _inv_band(start_inv: int) -> tuple[int, int]:
    if fix_flags.fix_sell():
        lo = start_inv - _inv_pad_lo()
        hi = start_inv + INV_PAD_HI
        return lo, hi
    lo = max(pricing.I0_DEFAULT - 80, start_inv - INV_PAD_LO)
    hi = min(pricing.I0_DEFAULT + 400, start_inv + INV_PAD_HI)
    return lo, hi


def shed_cap() -> int:
    return envconfig.shed_capacity()


def _log(msg: str) -> None:
    print(msg, flush=True)


def _clip_inv(inv: int, inv_lo: int, inv_hi: int) -> int:
    return max(inv_lo, min(inv_hi, inv))


def _tile_at(me: dict, idx: int):
    x, y = workers.TILE_COORDS[idx]
    return me["tiles"][y][x]


def _town_center_units(abs_day: int) -> int:
    if abs_day >= 20:
        return 4
    if abs_day >= 10:
        return 2
    return 1


def _shop_ticks_per_day() -> float:
    return envconfig.turns_per_day() / envconfig.shop_interval()


def _town_ticks_per_day() -> float:
    return envconfig.turns_per_day() / envconfig.town_center_interval()


def _known_shop_drain(unlocked_shops: list[str]) -> dict[str, float]:
    per_tick = rollouts.shop_demand_by_product(unlocked_shops)
    scale = _shop_ticks_per_day()
    return {p: per_tick.get(p, 0) * scale for p in SELL_PRODUCTS}


def _town_center_drain(abs_day: int) -> dict[str, float]:
    units = _town_center_units(abs_day)
    scale = _town_ticks_per_day()
    return {p: units * scale for p in _TOWN_CENTER_PRODUCTS}


def town_drain_by_day(obs: dict, horizon: int) -> list[dict[str, float]]:
    from milos import town_drain

    day = obs["day"]
    unlocked = list(obs.get("town", {}).get("unlocked_shops", []))
    if fix_flags.fix_prior():
        return town_drain.build_drain_horizon(day, unlocked, horizon, use_prior=True)
    seen = set(unlocked)
    locked = [s for s in _ALL_SHOPS if s not in seen]
    locked_demand = rollouts.shop_demand_by_product(locked)
    n_locked = len(locked)
    unlock_iv = envconfig.shop_unlock_interval()

    out: list[dict[str, float]] = []
    for rel in range(horizon):
        abs_day = day + rel
        drain = _known_shop_drain(unlocked)
        tc = _town_center_drain(abs_day)
        for p in _TOWN_CENTER_PRODUCTS:
            drain[p] = drain.get(p, 0.0) + tc.get(p, 0.0)
        if n_locked > 0 and abs_day > 0 and abs_day % unlock_iv == 0:
            scale = _shop_ticks_per_day() / n_locked * P_NEW_SHOP
            for p in SELL_PRODUCTS:
                if p in PREMIUM_PRODUCTS:
                    continue
                drain[p] = drain.get(p, 0.0) + locked_demand.get(p, 0) * scale
        out.append(
            {
                p: drain.get(p, 0.0) * drain_calib.factor(p) for p in SELL_PRODUCTS
            }
        )
    return out


def _update_opponent_residual(obs: dict, town_yesterday: dict[str, float]) -> None:
    global _prev_market_inv, _opp_ema, _our_sells_yesterday
    inv = obs["market"]["inventory"]
    if _prev_market_inv is None:
        _prev_market_inv = {p: int(inv.get(p, pricing.I0_DEFAULT)) for p in SELL_PRODUCTS}
        _our_sells_yesterday = {p: 0 for p in SELL_PRODUCTS}
        return

    for p in SELL_PRODUCTS:
        cur = int(inv.get(p, pricing.I0_DEFAULT))
        prev = int(_prev_market_inv.get(p, pricing.I0_DEFAULT))
        delta = cur - prev
        our = _our_sells_yesterday.get(p, 0)
        town = town_yesterday.get(p, 0.0)
        residual = max(0.0, delta - our + town)
        _opp_last[p] = residual
        _opp_ema[p] = OPP_EMA_ALPHA * residual + (1.0 - OPP_EMA_ALPHA) * _opp_ema.get(p, 0.0)

    _prev_market_inv = {p: int(inv.get(p, pricing.I0_DEFAULT)) for p in SELL_PRODUCTS}
    _our_sells_yesterday = {p: 0 for p in SELL_PRODUCTS}


def opponent_sell_per_day(horizon: int) -> list[dict[str, float]]:
    per_day = _opp_ema.copy()
    return [{p: per_day.get(p, 0.0) for p in PREMIUM_PRODUCTS} for _ in range(horizon)]


def record_sells(sold: dict[str, int]) -> None:
    for p, n in sold.items():
        if n > 0:
            _our_sells_yesterday[p] = _our_sells_yesterday.get(p, 0) + n


def _stamp_crop_harvests(
    crop: str,
    profile: str,
    plant_day: int,
    from_day: int,
    inflow: dict[str, list[int]],
) -> None:
    ages = rollouts.harvest_ages(crop, profile)
    yields = rollouts.yield_per_harvest(crop, profile)
    for age, units in zip(ages, yields):
        hday = plant_day + age
        if hday < from_day or hday > SEASON_LAST_DAY:
            continue
        rel = hday - from_day
        if crop in inflow and rel < len(inflow[crop]):
            inflow[crop][rel] += units


def _stamp_animal_harvests(
    animal: str,
    profile: str,
    placed_day: int,
    from_day: int,
    inflow: dict[str, list[int]],
) -> None:
    product = animal_rollouts.product_for(animal)
    ages = animal_rollouts.harvest_ages(animal, profile)
    yields = animal_rollouts.yield_per_harvest(animal, profile)
    for age, units in zip(ages, yields):
        hday = placed_day + age
        if hday < from_day or hday > SEASON_LAST_DAY:
            continue
        rel = hday - from_day
        if product in inflow and rel < len(inflow[product]):
            inflow[product][rel] += units


def _simulate_queue_harvests(
    idx: int,
    me: dict,
    st: dict,
    from_day: int,
    inflow: dict[str, list[int]],
) -> None:
    from milos.script import TILE_QUEUES

    queue = TILE_QUEUES.get(idx, [])
    qi = st.get("queue_idx", 0)
    lag = st.get("lag", 0)
    gap = st.get("gap", 0)
    cal = from_day
    tile = _tile_at(me, idx)

    if isinstance(tile, dict) and tile.get("kind") == "PLANT":
        crop = tile["crop"]
        item = queue[qi] if qi < len(queue) else None
        profile = item.profile if item and item.kind == "crop" else CROP_PROFILE
        _stamp_crop_harvests(crop, profile, tile["planted_day"], from_day, inflow)
        free_day = tile["planted_day"] + rollouts.tile_free_age(crop, profile)
        cal = max(cal, free_day)
        if item is not None:
            qi, lag, gap, _ = tile_ops.on_lifecycle_end(idx, qi, item, False)
    elif isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
        if tile.get("animal"):
            animal = tile["animal"]
            item = queue[qi] if qi < len(queue) else None
            profile = item.profile if item and item.kind == "animal" else ANIMAL_PROFILE
            _stamp_animal_harvests(animal, profile, tile["placed_day"], from_day, inflow)
            return

    while qi < len(queue) and cal <= SEASON_LAST_DAY:
        while lag > 0 and cal <= SEASON_LAST_DAY:
            cal += 1
            lag -= 1
        while gap > 0 and cal <= SEASON_LAST_DAY:
            cal += 1
            gap -= 1
        if cal > SEASON_LAST_DAY:
            break

        item = queue[qi]
        if item.kind == "crop":
            _stamp_crop_harvests(item.label, item.profile, cal, from_day, inflow)
            cal += rollouts.tile_free_age(item.label, item.profile)
            qi += 1
            lag = queue[qi].start_lag if qi < len(queue) else 0
            gap = item.replant_gap
        else:
            _stamp_animal_harvests(item.label, item.profile, cal + 1, from_day, inflow)
            break


def harvest_inflow_by_day(
    obs: dict,
    tile_state: dict,
    horizon: int,
) -> dict[str, list[int]]:
    day = obs["day"]
    player = obs["player"]
    me = obs["farms"][player]
    inflow: dict[str, list[int]] = {p: [0] * horizon for p in PREMIUM_PRODUCTS}

    for idx in range(workers.NUM_TILES):
        st = tile_state.get(idx, {})
        _simulate_queue_harvests(idx, me, st, day, inflow)

    return inflow


def _floor_active(abs_day: int) -> bool:
    return abs_day < LIQUIDATE_FROM_DAY


def _premium_daily_cap(product: str) -> int:
    if product == "WOOL":
        return max(4, pricing.MARKET_PARAMS["WOOL"].t // 8)
    return MAX_SELL_PER_DAY


def _max_sell_for_day(product: str, inv: int, stock: int, abs_day: int) -> int:
    max_sell = min(stock, _premium_daily_cap(product))
    if _floor_active(abs_day):
        max_sell = min(
            max_sell,
            pricing.max_units_above_floor(
                product, inv, max_sell, PRICE_FLOOR_RATIO
            ),
        )
    return max_sell


def _staple_dump(stock: int, product: str, wheat_reserve: int) -> int:
    if product == "WHEAT":
        return max(0, stock - wheat_reserve)
    return stock


def _solve_product(
    product: str,
    start_inv: int,
    start_stock: int,
    harvest: list[int],
    town: list[float],
    opp: list[float],
    day_start: int,
    horizon: int,
) -> list[int]:
    inv_lo, inv_hi = _inv_band(start_inv)
    stock_max = min(SHED_CAP, start_stock + sum(harvest))
    if stock_max <= 0 and start_stock <= 0:
        return [0] * horizon

    def transition(inv: int, stock: int, sell: int, d: int) -> tuple[int, int]:
        table = pricing.sell_prefix_table(product, inv, sell)
        _, next_inv = table[sell]
        next_inv = _clip_inv(int(round(next_inv + opp[d] - town[d])), inv_lo, inv_hi)
        next_stock = min(stock_max, stock - sell + harvest[d])
        return next_inv, next_stock

    dp: list[dict[tuple[int, int], float]] = [dict() for _ in range(horizon + 1)]
    choice: list[dict[tuple[int, int], int]] = [dict() for _ in range(horizon)]

    start_key = (_clip_inv(start_inv, inv_lo, inv_hi), min(stock_max, start_stock))
    reachable: list[set[tuple[int, int]]] = [set() for _ in range(horizon + 1)]
    reachable[0].add(start_key)
    for d in range(horizon):
        abs_day = day_start + d
        for inv, stock in reachable[d]:
            if abs_day >= SEASON_LAST_DAY:
                reachable[d + 1].add((inv, 0))
                continue
            max_sell = _max_sell_for_day(product, inv, stock, abs_day)
            for sell in range(max_sell + 1):
                reachable[d + 1].add(transition(inv, stock, sell, d))

    for inv, stock in reachable[horizon]:
        dp[horizon][(inv, stock)] = 0.0

    for d in range(horizon - 1, -1, -1):
        abs_day = day_start + d
        for inv, stock in reachable[d]:
            if abs_day >= SEASON_LAST_DAY:
                table = pricing.sell_prefix_table(product, inv, stock)
                dp[d][(inv, stock)] = float(table[stock][0])
                choice[d][(inv, stock)] = stock
                continue

            best_val = -10.0**18
            best_sell = 0
            max_sell = _max_sell_for_day(product, inv, stock, abs_day)
            for sell in range(max_sell, -1, -1):
                table = pricing.sell_prefix_table(product, inv, sell)
                rev = table[sell][0]
                next_inv, next_stock = transition(inv, stock, sell, d)
                hold_penalty = _hold_cost() * (stock - sell)
                future = dp[d + 1].get((next_inv, next_stock), -10.0**18)
                val = rev + future - hold_penalty
                if val >= best_val:
                    best_val = val
                    best_sell = sell

            dp[d][(inv, stock)] = best_val
            choice[d][(inv, stock)] = best_sell

    sells = [0] * horizon
    inv, stock = start_key
    for d in range(horizon):
        sell = choice[d].get((inv, stock), 0)
        sells[d] = sell
        inv, stock = transition(inv, stock, sell, d)
    return sells


def _trim_shed(
    sells: dict[str, list[int]],
    start_stocks: dict[str, int],
    harvest: dict[str, list[int]],
    start_inv: dict[str, int],
    horizon: int,
    wheat_reserve: int,
    day_start: int,
) -> None:
    inv_paths: dict[str, list[int]] = {}
    for p in PREMIUM_PRODUCTS:
        lo, hi = _inv_band(start_inv[p])
        inv_paths[p] = [_clip_inv(start_inv[p], lo, hi)]

    for _ in range(SHED_CAP * horizon):
        stocks: dict[str, int] = dict(start_stocks)
        overcrowded_day = -1
        for d in range(horizon):
            total = 0
            for p in SELL_PRODUCTS:
                if p in STAPLE_PRODUCTS:
                    sell = _staple_dump(stocks.get(p, 0), p, wheat_reserve)
                else:
                    sell = sells[p][d]
                h = harvest.get(p, [0] * horizon)[d] if p in harvest else 0
                after = stocks.get(p, 0) - sell + h
                total += max(0, after)
            if total > SHED_CAP:
                overcrowded_day = d
                break
            for p in SELL_PRODUCTS:
                if p in STAPLE_PRODUCTS:
                    sell = _staple_dump(stocks.get(p, 0), p, wheat_reserve)
                    h = 0
                else:
                    sell = sells[p][d]
                    h = harvest[p][d]
                    inv = inv_paths[p][-1]
                    _, inv_paths[p][-1] = pricing.sell_revenue_and_next_inv(p, inv, sell)
                stocks[p] = max(0, stocks.get(p, 0) - sell + h)

        if overcrowded_day < 0:
            return

        d = overcrowded_day
        abs_day = day_start + d
        worst_p = None
        worst_price = 10**9
        for p in PREMIUM_PRODUCTS:
            if sells[p][d] >= stocks.get(p, 0):
                continue
            if sells[p][d] >= MAX_SELL_PER_DAY:
                continue
            inv = inv_paths[p][-1]
            if _floor_active(abs_day):
                headroom = pricing.max_units_above_floor(
                    p, inv, stocks.get(p, 0) - sells[p][d], PRICE_FLOOR_RATIO
                )
                if headroom <= 0:
                    continue
            mp = pricing.marginal_price(p, inv)
            if mp < worst_price:
                worst_price = mp
                worst_p = p
        if worst_p is None:
            return
        sells[worst_p][d] += 1


def _drip_quota(stock: int) -> int:
    return min(stock, MAX_SELL_PER_DAY)


def replan(obs: dict, tile_state: dict, wheat_feed_reserve: int = 0) -> None:
    global _schedule, _prev_market_inv, _prev_unlocked_shops
    from milos import town_drain

    t0 = time.perf_counter()
    day = obs["day"]
    days_left = SEASON_LAST_DAY - day + 1
    if days_left <= 0:
        _schedule = None
        return

    horizon = min(DP_HORIZON, days_left)
    town = town_drain_by_day(obs, horizon)
    unlocked = list(obs.get("town", {}).get("unlocked_shops", []))
    if day > 0:
        if fix_flags.fix_sell():
            prev_town = town_drain.town_drain_yesterday(
                _prev_unlocked_shops,
                unlocked,
                day - 1,
            )
        else:
            prev_town = _known_shop_drain(unlocked)
            tc = _town_center_drain(day - 1)
            for p in _TOWN_CENTER_PRODUCTS:
                prev_town[p] = prev_town.get(p, 0.0) + tc.get(p, 0.0)
        _update_opponent_residual(obs, prev_town)
    else:
        inv = obs["market"]["inventory"]
        _prev_market_inv = {p: int(inv.get(p, pricing.I0_DEFAULT)) for p in SELL_PRODUCTS}
    _prev_unlocked_shops = list(unlocked)

    opp = opponent_sell_per_day(horizon)
    harvest = harvest_inflow_by_day(obs, tile_state, horizon)
    market_inv = obs["market"]["inventory"]
    shed = obs["private"]["shed"]

    sells: dict[str, list[int]] = {p: [0] * horizon for p in PREMIUM_PRODUCTS}
    start_stocks = {p: int(shed.get(p, 0)) for p in SELL_PRODUCTS}
    start_inv = {p: int(market_inv.get(p, pricing.I0_DEFAULT)) for p in SELL_PRODUCTS}
    reserve = wheat_feed_reserve if day < SEASON_LAST_DAY else 0

    for p in PREMIUM_PRODUCTS:
        if time.perf_counter() - t0 > REPLAN_TIME_BUDGET_S:
            if start_stocks[p] > 0:
                sells[p][0] = _drip_quota(start_stocks[p])
            continue
        future_harvest = sum(harvest[p])
        if start_stocks[p] <= 0 and future_harvest <= 0:
            continue
        sells[p] = _solve_product(
            p,
            start_inv[p],
            start_stocks[p],
            harvest[p],
            [t[p] for t in town],
            [o[p] for o in opp],
            day,
            horizon,
        )

    _trim_shed(sells, start_stocks, harvest, start_inv, horizon, reserve, day)

    raw_quota = {p: sells[p][0] for p in PREMIUM_PRODUCTS}
    today_quota: dict[str, int] = {}
    clamped: list[str] = []
    for p in PREMIUM_PRODUCTS:
        qty = pricing.allowed_sell_qty(
            p,
            start_inv[p],
            start_stocks[p],
            day,
            dp_quota=raw_quota[p],
            mode="drip",
            max_sell_per_day=MAX_SELL_PER_DAY,
            liquidate_from_day=LIQUIDATE_FROM_DAY,
            floor_ratio=PRICE_FLOOR_RATIO,
        )
        today_quota[p] = qty
        if qty > raw_quota[p]:
            clamped.append(f"{p}={qty}(from {raw_quota[p]})")

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    _schedule = {
        "day": day,
        "quota": today_quota,
        "sold": {p: _lead_carry.get(p, 0) for p in PREMIUM_PRODUCTS},
        "active": True,
        "next_quota": {p: sells[p][1] if len(sells[p]) > 1 else 0 for p in PREMIUM_PRODUCTS},
    }
    quota_s = " ".join(f"{k}={today_quota[k]}" for k in PREMIUM_PRODUCTS)
    clamp_s = f" clamped={' '.join(clamped)}" if clamped else ""
    _log(
        f"[sell_dp] d={day} ms={elapsed_ms:.0f} quota={quota_s}{clamp_s} "
        f"inv_melon={start_inv['MELON']}"
    )


def schedule_active(day: int) -> bool:
    return bool(_schedule and _schedule.get("active") and _schedule.get("day") == day)
    # return False


def plan_sell_qty(
    product: str,
    day: int,
    shed_count: int,
    wheat_feed_need: int,
    *,
    premium_drip: bool,
) -> int | None:
    if product in STAPLE_PRODUCTS:
        return None
    if not schedule_active(day):
        return None
    if product not in PREMIUM_PRODUCTS:
        return None

    quota = int(_schedule["quota"].get(product, 0))
    sold = int(_schedule["sold"].get(product, 0))
    remaining = quota - sold
    if remaining <= 0 or shed_count <= 0:
        return 0

    if premium_drip:
        return min(1, remaining, shed_count)
    return min(remaining, shed_count)


def commit_sell(product: str, qty: int) -> None:
    if qty <= 0 or product not in PREMIUM_PRODUCTS:
        return
    if _schedule:
        _schedule["sold"][product] = _schedule["sold"].get(product, 0) + qty
    record_sells({product: qty})


def projected_premium_inflow_today(obs: dict, tile_state: dict) -> dict[str, int]:
    rows = harvest_inflow_by_day(obs, tile_state, 1)
    return {p: int(rows[p][0]) for p in PREMIUM_PRODUCTS}


def clearable_sell_units_today(
    day: int,
    market_inv: dict,
    shed: dict,
    prices: dict,
    wheat_feed_need: int,
) -> int:
    total = 0
    for product in PREMIUM_PRODUCTS + STAPLE_PRODUCTS:
        count = int(shed.get(product, 0))
        if count <= 0:
            continue
        inv = int(market_inv.get(product, pricing.I0_DEFAULT))
        dump = pricing.allowed_sell_qty(
            product,
            inv,
            count,
            day,
            mode="dump",
            wheat_reserve=wheat_feed_need if product == "WHEAT" else 0,
            max_sell_per_day=MAX_SELL_PER_DAY,
            liquidate_from_day=LIQUIDATE_FROM_DAY,
            floor_ratio=PRICE_FLOOR_RATIO,
        )
        dp_rem = 0
        if schedule_active(day) and product in PREMIUM_PRODUCTS and _schedule:
            quota = int(_schedule["quota"].get(product, 0))
            sold = int(_schedule["sold"].get(product, 0))
            dp_rem = max(0, quota - sold)
        total += max(int(dump), dp_rem)
    return total


def clearable_units_by_product(
    day: int,
    market_inv: dict,
    shed: dict,
    wheat_feed_need: int,
) -> dict[str, int]:
    out: dict[str, int] = {}
    for product in PREMIUM_PRODUCTS + STAPLE_PRODUCTS:
        count = int(shed.get(product, 0))
        if count <= 0 and not (
            schedule_active(day) and product in PREMIUM_PRODUCTS and _schedule
        ):
            out[product] = 0
            continue
        inv = int(market_inv.get(product, pricing.I0_DEFAULT))
        dump = 0
        if count > 0:
            dump = int(
                pricing.allowed_sell_qty(
                    product,
                    inv,
                    count,
                    day,
                    mode="dump",
                    wheat_reserve=wheat_feed_need if product == "WHEAT" else 0,
                    max_sell_per_day=MAX_SELL_PER_DAY,
                    liquidate_from_day=LIQUIDATE_FROM_DAY,
                    floor_ratio=PRICE_FLOOR_RATIO,
                )
            )
        dp_rem = 0
        if schedule_active(day) and product in PREMIUM_PRODUCTS and _schedule:
            quota = int(_schedule["quota"].get(product, 0))
            sold = int(_schedule["sold"].get(product, 0))
            dp_rem = max(0, quota - sold)
        out[product] = max(dump, dp_rem)
    return out


def disposal_weight(product: str) -> float:
    above = pricing.MARKET_PARAMS[product].above_target
    if above >= 3.0:
        return 2.0
    if above >= 1.0:
        return 1.0
    return 0.5


def opp_recent_pressure(product: str) -> float:
    t = max(1, pricing.MARKET_PARAMS[product].t)
    return max(_opp_last.get(product, 0.0), _opp_ema.get(product, 0.0)) / float(t)


def apply_lead_suppression(step: int, product: str, qty: int) -> int:
    if not fix_flags.fix_sell_lead():
        return qty
    if _lead_suppress.get("due_step") != step:
        return qty
    suppress = int(_lead_suppress.get("qty", {}).get(product, 0))
    return max(0, qty - suppress)


def register_lead_suppression(next_step: int, sold: dict[str, int]) -> None:
    if not sold:
        return
    _lead_suppress["due_step"] = next_step
    merged = dict(_lead_suppress.get("qty") or {})
    for p, n in sold.items():
        if n > 0:
            merged[p] = merged.get(p, 0) + int(n)
    _lead_suppress["qty"] = merged


def remaining_quota(product: str, day: int) -> int:
    if not schedule_active(day) or not _schedule:
        return 0
    q = int(_schedule["quota"].get(product, 0))
    s = int(_schedule["sold"].get(product, 0))
    return max(0, q - s)


def next_hour_lead_qty(
    product: str,
    shed_count: int,
    *,
    drip: bool,
    remaining_quota: int,
) -> int:
    del product
    if shed_count <= 0 or remaining_quota <= 0:
        return 0
    if drip:
        return min(1, remaining_quota, shed_count)
    return min(remaining_quota, shed_count)


def sell_lead_allowed(step: int, product: str) -> bool:
    if not fix_flags.fix_sell_lead():
        return False
    if product in ("WHEAT", "FERTILIZER"):
        return False
    tpd = envconfig.turns_per_day()
    if step % envconfig.shop_interval() == 0:
        return False
    nxt = step + 1
    unlock_period = envconfig.shop_unlock_interval() * tpd
    if nxt >= tpd * (SEASON_LAST_DAY + 1):
        return False
    if nxt % unlock_period == 0:
        return False
    return True


def premium_lead_at_boundary(
    day: int,
    hour: int,
    step: int,
    product: str,
    shed_count: int,
) -> int:
    """Lead one unit of tomorrow's DP plan at h23."""
    if not fix_flags.fix_sell_lead() or hour != 23 or shed_count <= 0:
        return 0
    if not _schedule or not schedule_active(day):
        return 0
    nq = int((_schedule.get("next_quota") or {}).get(product, 0))
    if nq <= 0:
        return 0
    lead = min(1, nq, shed_count)
    if lead <= 0:
        return 0
    _lead_carry[product] = _lead_carry.get(product, 0) + lead
    register_lead_suppression(step + 1, {product: lead})
    return lead
