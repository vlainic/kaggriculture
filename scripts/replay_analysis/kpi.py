"""Diagnostic KPIs for executor, market, and planner (single-game replay)."""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import animal_rollouts, rollouts  # noqa: E402
from agent.pricing import base_price  # noqa: E402
from agent.zoning import _fib_hire_cost  # noqa: E402

from replay_analysis.load import SEASON_DAYS, Replay, StepRecord
from replay_analysis.metrics import (
    _feed_count,
    _inventory_totals,
    _iter_unit_actions,
    _merge_inv,
    _submitted_sell_qty,
    _tile_kind,
    _total_private_stock,
)
from replay_analysis.sells import MAX_MARKET_ORDERS, _expand_sell_orders, _sellable_stock_before_market

MOVE_OPS = frozenset({"NORTH", "SOUTH", "EAST", "WEST"})
PRODUCTIVE_OPS = frozenset(
    {
        "PLANT",
        "WATER",
        "HARVEST",
        "FERTILIZE",
        "DIG",
        "FEED",
        "CARE",
        "COLLECT_FERTILIZER",
        "BUILD_COOP",
        "BUILD_PASTURE",
        "PICKUP",
        "DROP",
        "PLACE",
    }
)
TILE_OPS = frozenset(
    {
        "PLANT",
        "WATER",
        "HARVEST",
        "FERTILIZE",
        "DIG",
        "FEED",
        "CARE",
        "COLLECT_FERTILIZER",
        "BUILD_COOP",
        "BUILD_PASTURE",
    }
)
LAND_COSTS = {"NE": 1000, "SW": 2000, "SE": 4000}
QUADRANT_ORDER = ["NE", "SW", "SE"]
LIQUIDITY_FLOOR = 0  # conservative cascade floor (override if agent defines one)


def executor_kpis(replay: Replay) -> dict[int, dict[str, Any]]:
    n = len(replay.team_names)
    out: dict[int, dict[str, Any]] = {}
    for p in range(n):
        out[p] = _executor_for_player(replay, p)
    return out


def market_kpis(replay: Replay, sell_sim: dict[str, Any]) -> dict[int, dict[str, Any]]:
    n = len(replay.team_names)
    out: dict[int, dict[str, Any]] = {}
    for p in range(n):
        out[p] = _market_for_player(replay, p, sell_sim)
    return out


def planner_kpis(
    replay: Replay,
    sell_sim: dict[str, Any],
    tile_series: list[list[dict[str, int]]] | None = None,
) -> dict[int, dict[str, Any]]:
    n = len(replay.team_names)
    out: dict[int, dict[str, Any]] = {}
    for p in range(n):
        out[p] = _planner_for_player(replay, p, sell_sim, tile_series)
    return out


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _player_records(replay: Replay, player: int) -> list[StepRecord]:
    return list(replay.iter_player(player))


def _pre_obs(records: list[StepRecord], i: int) -> dict[str, Any]:
    if i <= 0:
        return records[0].observation
    return records[i - 1].observation


def _iter_tiles(farm: dict[str, Any]) -> Iterator[tuple[int, int, Any]]:
    for y, row in enumerate(farm.get("tiles") or []):
        for x, tile in enumerate(row):
            yield x, y, tile


def _worker_pos(farm: dict[str, Any], who: str) -> list[int]:
    if who == "farmer":
        return list(farm.get("farmer") or [0, 0])
    if who.startswith("hand"):
        idx = int(who[4:])
        hands = farm.get("hands") or []
        if idx < len(hands):
            return list(hands[idx])
    return [0, 0]


def _tile_at(farm: dict[str, Any], pos: list[int]) -> Any:
    x, y = int(pos[0]), int(pos[1])
    return farm["tiles"][y][x]


def _apply_move(pos: list[int], op: str) -> list[int]:
    x, y = pos
    if op == "NORTH":
        return [x, y - 1]
    if op == "SOUTH":
        return [x, y + 1]
    if op == "EAST":
        return [x + 1, y]
    if op == "WEST":
        return [x, y - 1]
    return pos


def _is_noop(
    who: str,
    action: list[Any],
    pre_farm: dict[str, Any],
    post_farm: dict[str, Any],
) -> bool:
    if not action:
        return False
    op = action[0]
    pre_pos = _worker_pos(pre_farm, who)
    post_pos = _worker_pos(post_farm, who)
    tile = _tile_at(pre_farm, pre_pos)

    if op in MOVE_OPS:
        return pre_pos == post_pos
    if op in TILE_OPS:
        if tile == "LOCKED":
            return True
        if not isinstance(tile, dict) and op not in ("BUILD_COOP", "BUILD_PASTURE", "DIG", "PLANT"):
            return True
        if op == "WATER" and isinstance(tile, dict) and tile.get("kind") == "PLANT":
            return bool(tile.get("watered_today"))
        if op == "FEED" and isinstance(tile, dict) and tile.get("animal"):
            return bool(tile.get("fed_today"))
        if op == "CARE" and isinstance(tile, dict) and tile.get("animal"):
            return bool(tile.get("cared_today"))
        if op == "HARVEST" and isinstance(tile, dict):
            return int(tile.get("yield_units") or 0) <= 0
        if op == "COLLECT_FERTILIZER" and isinstance(tile, dict):
            return not bool(tile.get("fertilizer_available"))
        if op == "PLANT" and tile is not None:
            return True
        if op in ("BUILD_COOP", "BUILD_PASTURE") and tile is not None:
            return True
        if op == "DIG" and not (isinstance(tile, dict) and tile.get("kind") == "WEED"):
            return True
    return False


def _land_cost_for_buy(pre_quadrants: list[str], post_quadrants: list[str]) -> int:
    pre = set(pre_quadrants or ["NW"])
    post = set(post_quadrants or ["NW"])
    new = post - pre
    total = 0
    for q in QUADRANT_ORDER:
        if q in new:
            total += LAND_COSTS[q]
    return total


def _order_spend(
    order: list[Any],
    obs: dict[str, Any],
    hires_before: int,
) -> tuple[int, int]:
    """Return (spend_amount, new_hires_today after this order)."""
    if not order or not isinstance(order, list):
        return 0, hires_before
    op = order[0]
    prices = (obs.get("market") or {}).get("prices") or {}
    if op == "BUY_SEED" and len(order) >= 3:
        return rollouts.seed_cost(str(order[1])) * int(order[2]), hires_before
    if op == "BUY_ANIMAL" and len(order) >= 3:
        return animal_rollouts.animal_cost(str(order[1])) * int(order[2]), hires_before
    if op == "BUY_PRODUCT" and len(order) >= 3:
        prod = str(order[1])
        unit = int(prices.get(prod, base_price(prod)))
        return unit * int(order[2]), hires_before
    if op == "HIRE":
        cost = _fib_hire_cost(hires_before + 1) - _fib_hire_cost(hires_before)
        return cost, hires_before + 1
    return 0, hires_before


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


def _executor_for_player(replay: Replay, player: int) -> dict[str, Any]:
    records = _player_records(replay, player)
    if not records:
        return {}

    action_hist: Counter[str] = Counter()
    by_worker: dict[str, Counter[str]] = defaultdict(Counter)
    noop_by_op: Counter[str] = Counter()
    noop_total = 0
    move_ops = 0
    productive_ops = 0
    pass_ops = 0
    passes_by_day: Counter[int] = Counter()
    workers_by_day: dict[int, int] = {}

    ripe_per_turn: list[int] = []
    ripe_by_day: Counter[int] = Counter()
    ripe_latencies: list[int] = []
    first_ripe: dict[tuple[int, int], int] = {}

    unwatered_eod = 0
    max_consecutive_unwatered = 0
    unfed_eod = 0
    uncared_eod = 0
    max_consecutive_unfed = 0
    uncollected_fert_turns = 0

    weed_appear: dict[tuple[int, int], int] = {}
    weed_dig_latencies: list[int] = []
    weed_tile_turns = 0

    for i, rec in enumerate(records):
        obs = rec.observation
        pre_obs = _pre_obs(records, i)
        pre_farm = pre_obs["farms"][player]
        post_farm = obs["farms"][player]
        day = int(obs.get("day", 0))
        hour = int(obs.get("hour", 0))
        step = rec.step_index

        if hour == 0 and day < SEASON_DAYS:
            farm = obs["farms"][player]
            workers_by_day[day] = 1 + len(farm.get("hands") or [])

        for who, action in _iter_unit_actions(rec):
            if not action:
                continue
            op = action[0]
            action_hist[op] += 1
            by_worker[who][op] += 1
            if op == "PASS":
                pass_ops += 1
                passes_by_day[day] += 1
            elif op in MOVE_OPS:
                move_ops += 1
            elif op in PRODUCTIVE_OPS:
                productive_ops += 1
            if _is_noop(who, action, pre_farm, post_farm):
                noop_total += 1
                noop_by_op[op] += 1

        farm = obs["farms"][player]
        ripe_count = 0
        for x, y, tile in _iter_tiles(farm):
            if isinstance(tile, dict) and int(tile.get("yield_units") or 0) > 0:
                ripe_count += 1
                key = (x, y)
                if key not in first_ripe:
                    first_ripe[key] = step
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                weed_tile_turns += 1
                key = (x, y)
                if key not in weed_appear:
                    weed_appear[key] = step
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                max_consecutive_unwatered = max(
                    max_consecutive_unwatered,
                    int(tile.get("consecutive_unwatered") or 0),
                )
                if hour == 23 and not tile.get("watered_today"):
                    unwatered_eod += 1
            if isinstance(tile, dict) and tile.get("animal"):
                max_consecutive_unfed = max(
                    max_consecutive_unfed,
                    int(tile.get("consecutive_unfed") or 0),
                )
                if hour == 23:
                    if not tile.get("fed_today"):
                        unfed_eod += 1
                    if not tile.get("cared_today"):
                        uncared_eod += 1
            if isinstance(tile, dict) and tile.get("fertilizer_available"):
                uncollected_fert_turns += 1

        ripe_per_turn.append(ripe_count)
        ripe_by_day[day] += ripe_count

        for who, action in _iter_unit_actions(rec):
            if action and action[0] == "HARVEST":
                pos = _worker_pos(pre_farm, who)
                key = (int(pos[0]), int(pos[1]))
                if key in first_ripe:
                    ripe_latencies.append(step - first_ripe.pop(key))

        for who, action in _iter_unit_actions(rec):
            if action and action[0] == "DIG":
                pos = _worker_pos(pre_farm, who)
                key = (int(pos[0]), int(pos[1]))
                if key in weed_appear:
                    weed_dig_latencies.append(step - weed_appear.pop(key))

    ops_util: list[float] = []
    for d in range(SEASON_DAYS):
        w = workers_by_day.get(d, workers_by_day.get(d - 1, 1))
        cap = w * 24
        passes = passes_by_day.get(d, 0)
        ops_util.append(1.0 - (passes / cap) if cap else 0.0)

    return {
        "action_histogram": dict(action_hist),
        "by_worker": {w: dict(c) for w, c in by_worker.items()},
        "move_ops": move_ops,
        "productive_ops": productive_ops,
        "pass_ops": pass_ops,
        "move_overhead": move_ops / productive_ops if productive_ops else 0.0,
        "ops_utilization_by_day": ops_util,
        "noop_ops": {"total": noop_total, "by_op": dict(noop_by_op)},
        "ripe_unharvested": {
            "total_tile_turns": sum(ripe_per_turn),
            "mean_per_turn": sum(ripe_per_turn) / len(ripe_per_turn) if ripe_per_turn else 0.0,
            "by_day": [int(ripe_by_day[d]) for d in range(SEASON_DAYS)],
            "mean_latency_turns": (
                sum(ripe_latencies) / len(ripe_latencies) if ripe_latencies else 0.0
            ),
            "n_harvested": len(ripe_latencies),
        },
        "care_compliance": {
            "unwatered_eod": unwatered_eod,
            "max_consecutive_unwatered": max_consecutive_unwatered,
            "unfed_eod": unfed_eod,
            "uncared_eod": uncared_eod,
            "max_consecutive_unfed": max_consecutive_unfed,
        },
        "uncollected_fertilizer_tile_turns": uncollected_fert_turns,
        "weed": {
            "tile_turns": weed_tile_turns,
            "mean_dig_latency_turns": (
                sum(weed_dig_latencies) / len(weed_dig_latencies)
                if weed_dig_latencies
                else 0.0
            ),
            "n_dug": len(weed_dig_latencies),
        },
    }


# ---------------------------------------------------------------------------
# Market
# ---------------------------------------------------------------------------


def _market_for_player(
    replay: Replay, player: int, sell_sim: dict[str, Any]
) -> dict[str, Any]:
    records = _player_records(replay, player)
    if not records:
        return {}

    spend: Counter[str] = Counter()
    spend_by_day: Counter[int] = Counter()
    revenue_by_day: Counter[int] = Counter()
    money_deltas: list[float] = []

    stock_limited: Counter[str] = Counter()
    demand_limited: Counter[str] = Counter()
    submitted_units: Counter[str] = Counter()
    filled_units: Counter[str] = Counter()

    orders_at_cap = 0
    market_turns = 0
    truncated_units: Counter[str] = Counter()

    quote_ratios: dict[str, list[float]] = defaultdict(list)
    batch_decay: dict[str, list[float]] = defaultdict(list)

    harvest_queue: dict[str, list[int]] = defaultdict(list)
    holding_times: list[int] = []

    sim = sell_sim.get("by_player", {}).get(player, {})
    for prod, qty in (sim.get("filled_units") or {}).items():
        filled_units[prod] += qty

    events_by_step: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for ev in sell_sim.get("events") or []:
        if int(ev.get("player", -1)) == player:
            events_by_step[int(ev["step"])].append(ev)

    prev_money = float(records[0].observation["farms"][player]["money"])

    for i, rec in enumerate(records):
        obs = rec.observation
        pre_obs = _pre_obs(records, i)
        day = int(obs.get("day", 0))
        farm = obs["farms"][player]
        money = float(farm["money"])
        money_deltas.append(money - prev_money)
        prev_money = money

        market_orders = (rec.action.get("market") or [])
        if market_orders:
            market_turns += 1
            if len(market_orders) >= MAX_MARKET_ORDERS:
                orders_at_cap += 1
            raw_sells = [
                o for o in market_orders if isinstance(o, list) and o and o[0] == "SELL"
            ]
            kept = raw_sells[:MAX_MARKET_ORDERS]
            dropped = raw_sells[MAX_MARKET_ORDERS:]
            for o in dropped:
                if len(o) >= 3:
                    truncated_units[str(o[1])] += int(o[2])

        hires_before = int(pre_obs["farms"][player].get("hires_today") or 0)
        turn_spend = 0
        for order in market_orders:
            if not isinstance(order, list) or not order:
                continue
            op = str(order[0])
            amt, hires_before = _order_spend(order, pre_obs, hires_before)
            if amt:
                spend[op] += amt
                turn_spend += amt
            if op == "BUY_LAND":
                pre_q = pre_obs["farms"][player].get("unlocked_quadrants") or ["NW"]
                post_q = farm.get("unlocked_quadrants") or pre_q
                land_cost = _land_cost_for_buy(pre_q, post_q)
                if land_cost:
                    spend["BUY_LAND"] += land_cost
                    turn_spend += land_cost

        if turn_spend:
            spend_by_day[day] += turn_spend

        step_events = events_by_step.get(rec.step_index, [])
        if step_events:
            rev = sum(int(ev["price"]) for ev in step_events)
            revenue_by_day[day] += rev

        sell_qty = _submitted_sell_qty(rec)
        stock = _sellable_stock_before_market(
            records[i - 1] if i > 0 else None, rec
        )
        for prod, qty in sell_qty.items():
            submitted_units[prod] += qty
            avail = int(stock.get(prod, 0))
            if qty > avail:
                stock_limited[prod] += qty - avail
            rem = min(qty, avail)
            filled_here = sum(1 for ev in step_events if ev["product"] == prod)
            if rem > filled_here:
                demand_limited[prod] += rem - filled_here

        prices = (pre_obs.get("market") or {}).get("prices") or {}
        step_prices = [int(ev["price"]) for ev in step_events]
        for ev in step_events:
            prod = str(ev["product"])
            quote = int(prices.get(prod, base_price(prod)))
            if quote > 0:
                quote_ratios[prod].append(int(ev["price"]) / quote)

        if len(step_events) >= 2:
            by_prod: dict[str, list[int]] = defaultdict(list)
            for ev in step_events:
                by_prod[str(ev["product"])].append(int(ev["price"]))
            for prod, ps in by_prod.items():
                if len(ps) >= 2:
                    q = int(prices.get(prod, base_price(prod)))
                    if q > 0:
                        batch_decay[prod].append((ps[0] - ps[-1]) / q)

        if i > 0:
            prev_stock = _total_private_stock(
                records[i - 1].observation.get("private") or {}
            )
            curr_stock = _total_private_stock(obs.get("private") or {})
            for prod in SELLABLE:
                inc = int(curr_stock.get(prod, 0)) - int(prev_stock.get(prod, 0))
                if prod == "WHEAT":
                    inc = max(0, inc - _feed_count(rec))
                for _ in range(max(0, inc)):
                    harvest_queue[prod].append(rec.step_index)

        for ev in step_events:
            prod = str(ev["product"])
            if harvest_queue[prod]:
                h_step = harvest_queue[prod].pop(0)
                holding_times.append(rec.step_index - h_step)

    total_revenue = sum(sim.get("revenue", {}).values()) if sim else 0
    total_spend = sum(spend.values())
    total_delta = sum(money_deltas)

    fill_rate: dict[str, dict[str, float | int]] = {}
    for prod in set(submitted_units) | set(filled_units):
        sub = submitted_units.get(prod, 0)
        fil = filled_units.get(prod, 0)
        fill_rate[prod] = {
            "submitted": sub,
            "filled": fil,
            "fill_rate": fil / sub if sub else 0.0,
            "stock_limited_units": stock_limited.get(prod, 0),
            "demand_limited_units": demand_limited.get(prod, 0),
        }

    realized_vs_quote = {
        p: sum(v) / len(v) if v else 0.0 for p, v in quote_ratios.items()
    }
    batch_price_decay = {
        p: sum(v) / len(v) if v else 0.0 for p, v in batch_decay.items()
    }

    return {
        "spend": dict(spend),
        "total_spend": total_spend,
        "total_revenue": total_revenue,
        "unexplained_delta": total_delta - (total_revenue - total_spend),
        "fill_rate": fill_rate,
        "order_slot_saturation": {
            "market_turns": market_turns,
            "at_cap_turns": orders_at_cap,
            "saturation_rate": orders_at_cap / market_turns if market_turns else 0.0,
            "truncated_units": dict(truncated_units),
        },
        "realized_vs_quote": realized_vs_quote,
        "batch_price_decay": batch_price_decay,
        "holding_time": {
            "mean_turns": sum(holding_times) / len(holding_times) if holding_times else 0.0,
            "median_turns": _median(holding_times),
            "n_units": len(holding_times),
        },
        "revenue_by_day": [int(revenue_by_day[d]) for d in range(SEASON_DAYS)],
        "spend_by_day": [int(spend_by_day[d]) for d in range(SEASON_DAYS)],
    }


SELLABLE = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
)


def _median(vals: list[int]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


def _planner_for_player(
    replay: Replay,
    player: int,
    sell_sim: dict[str, Any],
    tile_series: list[list[dict[str, int]]] | None,
) -> dict[str, Any]:
    records = _player_records(replay, player)
    if not records:
        return {}

    idle_tile_turns = 0
    empty_structure_turns = 0
    weed_turns = 0
    occupied_turns = 0
    unlocked_turns = 0
    crop_tile_days: Counter[str] = Counter()

    min_cash_by_day: dict[int, float] = {}
    days_below_floor = 0

    land_events: list[dict[str, Any]] = []
    hires_by_day: Counter[int] = Counter()
    hire_spend_by_day: Counter[int] = Counter()

    fert_collected = 0
    fert_applied = 0
    seeds_bought: Counter[str] = Counter()
    seeds_planted: Counter[str] = Counter()

    sim = sell_sim.get("by_player", {}).get(player, {})
    revenue_by_product = Counter(sim.get("revenue") or {})

    for i, rec in enumerate(records):
        obs = rec.observation
        pre_obs = _pre_obs(records, i)
        day = int(obs.get("day", 0))
        hour = int(obs.get("hour", 0))
        farm = obs["farms"][player]
        money = float(farm["money"])

        if day < SEASON_DAYS:
            cur_min = min_cash_by_day.get(day, money)
            min_cash_by_day[day] = min(cur_min, money)

        for x, y, tile in _iter_tiles(farm):
            kind = _tile_kind(tile)
            if kind == "locked":
                continue
            unlocked_turns += 1
            if kind == "empty":
                idle_tile_turns += 1
            elif kind == "occupied":
                occupied_turns += 1
                if isinstance(tile, dict):
                    if tile.get("kind") == "PLANT" and tile.get("crop"):
                        crop_tile_days[str(tile["crop"])] += 1
                    elif tile.get("animal"):
                        prod = animal_rollouts.product_for(str(tile["animal"]))
                        crop_tile_days[prod] += 1
            elif kind == "empty_structure":
                empty_structure_turns += 1
            elif kind == "weed":
                weed_turns += 1

        for who, action in _iter_unit_actions(rec):
            if not action:
                continue
            op = action[0]
            if op == "COLLECT_FERTILIZER":
                fert_collected += 1
            elif op == "FERTILIZE":
                fert_applied += 1
            elif op == "PLANT" and len(action) >= 2:
                seeds_planted[str(action[1])] += 1

        hires_today_local = int(pre_obs["farms"][player].get("hires_today") or 0)
        for order in (rec.action.get("market") or []):
            if isinstance(order, list) and len(order) >= 3 and order[0] == "BUY_SEED":
                seeds_bought[str(order[1])] += int(order[2])
            if isinstance(order, list) and order[0] == "HIRE":
                hires_by_day[day] += 1
                cost = _fib_hire_cost(hires_today_local + 1) - _fib_hire_cost(
                    hires_today_local
                )
                hire_spend_by_day[day] += cost
                hires_today_local += 1
            if isinstance(order, list) and order[0] == "BUY_LAND":
                pre_q = pre_obs["farms"][player].get("unlocked_quadrants") or ["NW"]
                post_q = farm.get("unlocked_quadrants") or pre_q
                new_q = list(set(post_q) - set(pre_q))
                cost = _land_cost_for_buy(pre_q, post_q)
                if cost and new_q:
                    land_events.append(
                        {"day": day, "quadrant": new_q[0], "cost": cost}
                    )

    min_cash_series = [
        float(min_cash_by_day.get(d, float("nan"))) for d in range(SEASON_DAYS)
    ]
    for v in min_cash_series:
        if v < LIQUIDITY_FLOOR:
            days_below_floor += 1

    utilization = occupied_turns / unlocked_turns if unlocked_turns else 0.0

    rev_per_tile_day: dict[str, float] = {}
    for crop, rev in revenue_by_product.items():
        animal = _product_to_crop_or_animal(crop)
        td = crop_tile_days.get(animal, 0)
        if td:
            rev_per_tile_day[crop] = rev / td

    end_priv = records[-1].observation.get("private") or {}
    end_shed = end_priv.get("shed") or {}
    end_seeds = end_priv.get("seeds") or {}

    total_hire_spend = sum(hire_spend_by_day.values())
    total_hires = sum(hires_by_day.values())

    sold_fert = 0
    bought_fert = 0
    for rec in records:
        for order in (rec.action.get("market") or []):
            if isinstance(order, list) and len(order) >= 3:
                if order[0] == "SELL" and order[1] == "FERTILIZER":
                    sold_fert += int(order[2])
                if order[0] == "BUY_PRODUCT" and order[1] == "FERTILIZER":
                    bought_fert += int(order[2])

    return {
        "idle_tile_days": {
            "empty": idle_tile_turns,
            "empty_structure": empty_structure_turns,
            "weed": weed_turns,
            "occupied": occupied_turns,
            "unlocked": unlocked_turns,
            "tile_day_utilization": utilization,
        },
        "revenue_per_tile_day_by_crop": rev_per_tile_day,
        "crop_tile_days": dict(crop_tile_days),
        "min_cash_by_day": min_cash_series,
        "days_below_floor": days_below_floor,
        "land_events": land_events,
        "hire_profile": {
            "hires_by_day": [int(hires_by_day[d]) for d in range(SEASON_DAYS)],
            "hire_spend_by_day": [int(hire_spend_by_day[d]) for d in range(SEASON_DAYS)],
            "total_hires": total_hires,
            "total_hire_spend": total_hire_spend,
            "ops_per_coin": (total_hires * 24) / total_hire_spend if total_hire_spend else 0.0,
        },
        "fert_ledger": {
            "collected": fert_collected,
            "applied": fert_applied,
            "sold": sold_fert,
            "bought": bought_fert,
            "end_stock": int(end_shed.get("FERTILIZER", 0)),
        },
        "seed_ledger": {
            "bought": dict(seeds_bought),
            "planted": dict(seeds_planted),
            "end_stock": {k: int(v) for k, v in end_seeds.items() if v},
        },
    }


def _product_to_crop_or_animal(product: str) -> str:
    for animal in ("GOOSE", "CHICKEN", "COW", "SHEEP"):
        try:
            if animal_rollouts.product_for(animal) == product:
                return animal
        except Exception:
            pass
    return product
