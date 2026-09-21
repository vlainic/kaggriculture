"""Daily per-product sell DP with dawn MPC replan (premium goods only)."""

from __future__ import annotations

import time

from milos import animal_rollouts, pricing, rollouts, tile_ops, workers

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
SHED_CAP = 100
SHOP_INTERVAL = 4
TOWN_CENTER_INTERVAL = 12
SHOP_UNLOCK_INTERVAL = 3
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

_schedule: dict | None = None
_prev_market_inv: dict[str, int] | None = None
_our_sells_yesterday: dict[str, int] = {p: 0 for p in SELL_PRODUCTS}
_opp_ema: dict[str, float] = {p: 0.0 for p in SELL_PRODUCTS}


def _log(msg: str) -> None:
    print(msg, flush=True)


def _inv_band(start_inv: int) -> tuple[int, int]:
    lo = max(pricing.I0_DEFAULT - 80, start_inv - INV_PAD_LO)
    hi = min(pricing.I0_DEFAULT + 400, start_inv + INV_PAD_HI)
    return lo, hi


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


def _known_shop_drain(unlocked_shops: list[str]) -> dict[str, float]:
    per_tick = rollouts.shop_demand_by_product(unlocked_shops)
    scale = 24 / SHOP_INTERVAL
    return {p: per_tick.get(p, 0) * scale for p in SELL_PRODUCTS}


def _town_center_drain(abs_day: int) -> dict[str, float]:
    units = _town_center_units(abs_day)
    scale = 24 / TOWN_CENTER_INTERVAL
    return {p: units * scale for p in _TOWN_CENTER_PRODUCTS}


def town_drain_by_day(obs: dict, horizon: int) -> list[dict[str, float]]:
    day = obs["day"]
    unlocked = list(obs.get("town", {}).get("unlocked_shops", []))
    locked = [s for s in _ALL_SHOPS if s not in unlocked]
    locked_demand = rollouts.shop_demand_by_product(locked)
    n_locked = len(locked)

    out: list[dict[str, float]] = []
    for rel in range(horizon):
        abs_day = day + rel
        drain = _known_shop_drain(unlocked)
        tc = _town_center_drain(abs_day)
        for p in _TOWN_CENTER_PRODUCTS:
            drain[p] = drain.get(p, 0.0) + tc.get(p, 0.0)
        if n_locked > 0 and abs_day > 0 and abs_day % SHOP_UNLOCK_INTERVAL == 0:
            scale = (24 / SHOP_INTERVAL) / n_locked
            for p in SELL_PRODUCTS:
                drain[p] = drain.get(p, 0.0) + locked_demand.get(p, 0) * scale
        out.append({p: drain.get(p, 0.0) for p in SELL_PRODUCTS})
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
                hold_penalty = HOLD_COST * (stock - sell)
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
    global _schedule, _prev_market_inv

    t0 = time.perf_counter()
    day = obs["day"]
    days_left = SEASON_LAST_DAY - day + 1
    if days_left <= 0:
        _schedule = None
        return

    horizon = min(DP_HORIZON, days_left)
    town = town_drain_by_day(obs, horizon)
    if day > 0:
        prev_town = _known_shop_drain(
            list(obs.get("town", {}).get("unlocked_shops", []))
        )
        tc = _town_center_drain(day - 1)
        for p in _TOWN_CENTER_PRODUCTS:
            prev_town[p] = prev_town.get(p, 0.0) + tc.get(p, 0.0)
        _update_opponent_residual(obs, prev_town)
    else:
        inv = obs["market"]["inventory"]
        _prev_market_inv = {p: int(inv.get(p, pricing.I0_DEFAULT)) for p in SELL_PRODUCTS}

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
        "sold": {p: 0 for p in PREMIUM_PRODUCTS},
        "active": True,
    }
    quota_s = " ".join(f"{k}={today_quota[k]}" for k in PREMIUM_PRODUCTS)
    clamp_s = f" clamped={' '.join(clamped)}" if clamped else ""
    _log(
        f"[sell_dp] d={day} ms={elapsed_ms:.0f} quota={quota_s}{clamp_s} "
        f"inv_melon={start_inv['MELON']}"
    )


def schedule_active(day: int) -> bool:
    return bool(_schedule and _schedule.get("active") and _schedule.get("day") == day)


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
    if _schedule and qty > 0 and product in PREMIUM_PRODUCTS:
        _schedule["sold"][product] = _schedule["sold"].get(product, 0) + qty
        record_sells({product: qty})
