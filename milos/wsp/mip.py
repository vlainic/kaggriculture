"""Farmer-zone WSP patterns + CP-SAT (lifted from zonewise_wsp; no agent imports)."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable

from ortools.sat.python import cp_model

from milos.wsp import data as rollouts
from milos.wsp.common import decode_sort_key, parse_profile_key
from milos.wsp.config import (
    ANIMAL_NAMES,
    ANIMAL_PROFILES,
    CONCAVE_PRODUCTS,
    CROP_PROFILES,
    FARMER,
    FARMER_NET_TILE_OPS,
    FARMER_TILES,
    FERT_PRICE,
    GLUT_PRODUCTS,
    MAX_BUY,
    NUM_DAYS,
    OBJ_EARLY_STOP,
    WHEAT_PRICE,
)
from milos import pricing
from milos.zoning import HAND_DAILY_COST, HAND_WORKERS


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
            harvest_map[age]
            if kind == "crop" and label == "WHEAT" and age in harvest_map
            else 0
        )
    return feed_by_age, fert_use_by_age, collect_by_age, wheat_gain_by_age


def _harvest_product(label: str, kind: str, animals_data: dict) -> str:
    if kind == "animal":
        return animals_data["animals"][label]["product"]
    return label


def _empty_daily_harvest(horizon: int) -> dict[str, list[int]]:
    return {p: [0] * horizon for p in GLUT_PRODUCTS}


def _on_tile_ops_count(acts: list) -> int:
    return len([a for a in acts if a != "PICKUP"])


def _empty_daily_place(horizon: int) -> dict[str, list[int]]:
    return {name: [0] * horizon for name in ANIMAL_NAMES}


CONCAVE_BLOCK = 5
_CONTESTED_SINK = frozenset({"STRAWBERRY", "WOOL", "MILK"})
PRICE_FLOOR_RATIO = 0.5
_quote_market_inv: dict[str, int] | None = None


def set_quote_market_inv(market_inv: dict[str, int] | None) -> None:
    global _quote_market_inv
    _quote_market_inv = (
        {k: int(v) for k, v in market_inv.items()} if market_inv else None
    )


def quote_at(product: str, market_inv: dict[str, int], extra_units: int = 0) -> int:
    inv = int(market_inv.get(product, pricing.I0_DEFAULT)) + int(extra_units)
    return pricing.quoted(product, inv)


def harvest_price_for_cash(
    product: str, rel_day: int, price_of: Callable[..., int]
) -> int:
    if product in CONCAVE_PRODUCTS and _quote_market_inv is not None:
        return quote_at(product, _quote_market_inv, 0)
    return price_of(product, rel_day)


def _mean_harvest_rel_day(patterns: list, product: str, horizon: int) -> int:
    days: list[int] = []
    for pat in patterns:
        for prod, hday, yld in pat.get("harvest_lines", ()):
            if prod == product and int(yld) > 0:
                days.append(int(hday))
    if not days:
        return min(max(0, horizon - 1), max(0, horizon // 2))
    return min(max(0, horizon - 1), int(sum(days) / len(days)))


def _max_zone_product_units(patterns: list, zone_size: int, product: str) -> int:
    per_tile = max(
        (int(pat.get("harvest_units", {}).get(product, 0)) for pat in patterns),
        default=0,
    )
    return per_tile * zone_size


def build_revenue_curves(
    product: str,
    *,
    patterns: list,
    horizon: int,
    zone_size: int,
    market_inv: dict[str, int],
    locked_counts: dict[str, int] | None,
    sink_units: dict[str, int] | None,
    opp_units: dict[str, int] | None,
    carried: dict[str, int] | None,
    wheat_feed_units: int = 0,
) -> tuple[list[tuple[int, int]], dict[str, int]]:
    locked = int((locked_counts or {}).get(product, 0))
    carried_p = int((carried or {}).get(product, 0))
    d_total = int((sink_units or {}).get(product, 0))
    opp_p = int((opp_units or {}).get(product, 0))
    if opp_p <= 0 and product in _CONTESTED_SINK and d_total > 0:
        opp_p = max(opp_p, int(0.5 * d_total))
    d_remaining = max(0, d_total - carried_p - opp_p)

    rel_ref = _mean_harvest_rel_day(patterns, product, horizon)
    floor = pricing.price_floor(product, PRICE_FLOOR_RATIO)
    max_u = min(_max_zone_product_units(patterns, zone_size, product), 400)
    feed_reserve = 0
    if product == "WHEAT" and wheat_feed_units > 0:
        feed_reserve = min(int(wheat_feed_units), max_u)
    if max_u <= 0:
        return [], {
            "D": d_total,
            "carried": carried_p,
            "opp": opp_p,
            "D_remaining": d_remaining,
            "m0": 0,
            "mlast": 0,
        }

    segments: list[tuple[int, int]] = []
    prev_m = 10**9
    sold_virtual = 0
    quote0 = quote_at(product, market_inv, 0)

    if feed_reserve > 0:
        m_feed = max(floor, quote0)
        segments.append((feed_reserve, m_feed))
        prev_m = m_feed
        sold_virtual = feed_reserve

    if d_remaining > 0:
        flat_cap = min(d_remaining, max_u - sold_virtual)
        if flat_cap > 0:
            m0 = max(floor, min(quote0, prev_m))
            segments.append((flat_cap, m0))
            prev_m = m0
            sold_virtual += flat_cap

    while sold_virtual < max_u:
        block = min(CONCAVE_BLOCK, max_u - sold_virtual)
        extra = sold_virtual
        m = quote_at(product, market_inv, extra + block - 1)
        m = max(floor, min(m, prev_m))
        if m <= floor and sold_virtual > d_remaining + feed_reserve:
            break
        segments.append((block, m))
        prev_m = m
        sold_virtual += block
        if m <= floor:
            break

    if not segments:
        m = max(floor, quote0)
        segments.append((max_u, m))

    return segments, {
        "D": d_total,
        "carried": carried_p,
        "opp": opp_p,
        "D_remaining": d_remaining,
        "m0": segments[0][1],
        "mlast": segments[-1][1],
    }


def _pattern_weight(
    pat,
    locked_counts: dict[str, int],
    price_of: Callable[..., int],
) -> int:
    counts = dict(locked_counts or {})
    rev = 0
    for product, hday, yld in pat["harvest_lines"]:
        n = counts.get(product, 0)
        for _ in range(int(yld)):
            if product not in CONCAVE_PRODUCTS:
                rev += price_of(product, hday, n)
            n += 1
        counts[product] = n
    bonus = _animal_valuation_bonus(pat, price_of)
    return rev - pat["setup_cost"] + bonus


def _fert_credit_day(day: int) -> float:
    return 90.0 * max(0.2, (29 - day) / 29.0)


def _animal_valuation_bonus(pat, price_of: Callable[..., int]) -> int:
    key = pat.get("profile_key", "")
    if not any(a in key for a in ("COW", "SHEEP")):
        return 0
    horizon = len(pat.get("daily_feed") or [])
    bonus = 0
    for d in range(horizon):
        if pat["daily_collect"][d]:
            bonus += int(_fert_credit_day(d))
        if pat["daily_feed"][d]:
            try:
                bonus -= int(price_of("WHEAT", d))
            except TypeError:
                from milos.wsp.config import WHEAT_PRICE

                bonus -= WHEAT_PRICE
    return bonus


def _stamp_placement(
    profile_key: str,
    start_day: int,
    horizon: int,
    price_of: Callable[..., int],
    crops_data: dict,
    animals_data: dict,
):
    label, profile_name = parse_profile_key(profile_key)
    kind, spec, profile = _rollout_spec(label, profile_name, crops_data, animals_data)
    setup_cost = spec["seed_cost"] if kind == "crop" else spec["animal_cost"]
    feed_by_age, fert_use_by_age, collect_by_age, wheat_gain_by_age = _parse_age_maps(
        profile, label, kind
    )

    daily_tile_ops = [0] * horizon
    daily_animal_active = [0] * horizon
    daily_feed = [0] * horizon
    daily_fert = [0] * horizon
    daily_collect = [0] * horizon
    daily_wheat = [0] * horizon
    daily_place = _empty_daily_place(horizon)
    occupied: list[int] = []

    if kind == "crop":
        for day in profile["days"]:
            cal = start_day + day["age"]
            if cal >= horizon:
                return None
            occupied.append(cal)
            acts = day["actions"]
            daily_tile_ops[cal] += _on_tile_ops_count(acts)
            age = day["age"]
            daily_feed[cal] += feed_by_age.get(age, 0)
            daily_fert[cal] += fert_use_by_age.get(age, 0)
            daily_collect[cal] += collect_by_age.get(age, 0)
            daily_wheat[cal] += wheat_gain_by_age.get(age, 0)
    else:
        for day in profile["days"]:
            cal = start_day + day["age"]
            if cal >= horizon:
                break
            occupied.append(cal)
            acts = day["actions"]
            age = day["age"]
            daily_tile_ops[cal] += _on_tile_ops_count(acts)
            if "PLACE" in acts:
                daily_place[label][cal] = 1
            daily_animal_active[cal] = 1
            daily_feed[cal] += feed_by_age.get(age, 0)
            daily_fert[cal] += fert_use_by_age.get(age, 0)
            daily_collect[cal] += collect_by_age.get(age, 0)
            daily_wheat[cal] += wheat_gain_by_age.get(age, 0)
        if not occupied:
            return None

    daily_harvest = _empty_daily_harvest(horizon)
    harvest_lines = []
    harvest_units: dict[str, int] = {}
    for age, yld in zip(profile["harvest_ages"], profile["yield_per_harvest"]):
        hday = start_day + age
        if hday >= horizon:
            continue
        product = _harvest_product(label, kind, animals_data)
        harvest_lines.append((product, hday, yld))
        harvest_units[product] = harvest_units.get(product, 0) + yld
        if product in daily_harvest:
            daily_harvest[product][hday] += yld

    cash_by_day = [0] * horizon
    spend_by_day = [0] * horizon
    if start_day < horizon:
        cash_by_day[start_day] -= setup_cost
        spend_by_day[start_day] -= setup_cost
    for product, hday, yld in harvest_lines:
        if hday < horizon:
            cash_by_day[hday] += yld * harvest_price_for_cash(product, hday, price_of)

    return {
        "profile_key": profile_key,
        "start_day": start_day,
        "setup_cost": setup_cost,
        "harvest_lines": harvest_lines,
        "harvest_units": harvest_units,
        "cash_by_day": cash_by_day,
        "spend_by_day": spend_by_day,
        "occupied_days": frozenset(occupied),
        "daily_tile_ops": daily_tile_ops,
        "daily_animal_active": daily_animal_active,
        "daily_feed": daily_feed,
        "daily_fert": daily_fert,
        "daily_collect": daily_collect,
        "daily_wheat": daily_wheat,
        "daily_harvest": daily_harvest,
        "daily_place": daily_place,
    }


def build_patterns(
    horizon: int,
    price_of: Callable[..., int],
    *,
    crops_allowlist: frozenset[str] | None = None,
) -> list:
    crops_data = rollouts.crops()
    animals_data = rollouts.animals()
    patterns = []
    pid = 0
    for crop_name, crop_spec in crops_data["crops"].items():
        if crops_allowlist is not None and crop_name not in crops_allowlist:
            continue
        for profile_name in CROP_PROFILES:
            if profile_name not in crop_spec:
                continue
            if profile_name == "with_fert" and crop_name not in ("STRAWBERRY", "WHEAT"):
                continue
            profile_key = f"{crop_name}_{profile_name}"
            for start_day in range(horizon):
                seg = _stamp_placement(
                    profile_key, start_day, horizon, price_of, crops_data, animals_data
                )
                if seg is None:
                    continue
                patterns.append({"id": f"P{pid}", **seg})
                pid += 1

    if crops_allowlist is None:
        for animal_name, animal_spec in animals_data["animals"].items():
            if animal_name == "GOOSE":
                continue
            for profile_name in ANIMAL_PROFILES:
                if profile_name not in animal_spec:
                    continue
                profile_key = f"{animal_name}_{profile_name}"
                for start_day in range(horizon):
                    seg = _stamp_placement(
                        profile_key,
                        start_day,
                        horizon,
                        price_of,
                        crops_data,
                        animals_data,
                    )
                    if seg is None:
                        continue
                    patterns.append({"id": f"P{pid}", **seg})
                    pid += 1
    return patterns


class _ObjEarlyStop(cp_model.CpSolverSolutionCallback):
    def __init__(self, target: float):
        super().__init__()
        self.target = target
        self.stopped_early = False

    def on_solution_callback(self):
        if self.ObjectiveValue() >= self.target:
            self.stopped_early = True
            self.StopSearch()


def decode_wsp_assignment(
    empty_tiles: set[int],
    picked: list,
    *,
    tile_order: tuple[int, ...] = FARMER_TILES,
) -> dict[int, list]:
    remaining = [idx for idx in tile_order if idx in empty_tiles]
    if not remaining:
        return {}

    by_tile: dict[int, list] = defaultdict(list)
    for pick in picked:
        by_tile[pick["tile"]].append(pick)

    slots: list[list] = []
    for tile in remaining:
        picks = by_tile.get(tile, [])
        if not picks:
            continue
        chain = sorted(
            [[p["pattern"]["profile_key"], p["pattern"]["start_day"]] for p in picks],
            key=lambda pair: pair[1],
        )
        slots.append(chain)
    slots.sort(key=decode_sort_key)

    assigned: dict[int, list] = {}
    for i, idx in enumerate(remaining):
        assigned[idx] = slots[i] if i < len(slots) else []
    return assigned


def solve_zone(
    patterns: list,
    *,
    horizon: int,
    empty_tiles: list[int],
    locked: dict,
    locked_counts: dict[str, int],
    opening_balances: list[int],
    w_open: int,
    f_open: int,
    max_time: float,
    track_shed: bool,
    min_balance: int = 0,
    price_of: Callable[..., int] | None = None,
    worker: str = FARMER,
    net_tile_ops: int = FARMER_NET_TILE_OPS,
    charge_hire_daily: bool = False,
    product_caps: dict[str, int] | None = None,
    sink_units: dict[str, int] | None = None,
    opp_units: dict[str, int] | None = None,
    market_inv: dict[str, int] | None = None,
    wheat_feed_units: int = 0,
):
    zone_empty = list(empty_tiles)
    zsize = len(zone_empty)
    if zsize == 0:
        return None

    if price_of is None:
        base = rollouts.i0_base_prices()
        price_of = lambda product, rel_day=0, extra_units=0, _base=base: _base[
            product
        ]

    model = cp_model.CpModel()
    x: dict[tuple[int, int], cp_model.IntVar] = {}
    for pi, pat in enumerate(patterns):
        for tile in zone_empty:
            x[pi, tile] = model.NewBoolVar(f"x_{worker}_{pat['id']}_t{tile}")

    for product, cap_units in (product_caps or {}).items():
        if cap_units <= 0:
            continue
        terms = [
            x[pi, tile] * pat["harvest_units"][product]
            for pi, pat in enumerate(patterns)
            if pat["harvest_units"].get(product, 0) > 0
            for tile in zone_empty
        ]
        if terms:
            model.Add(sum(terms) <= cap_units)

    for tile in zone_empty:
        for day in range(horizon):
            covering = [
                x[pi, tile]
                for pi, pat in enumerate(patterns)
                if day in pat["occupied_days"]
            ]
            if covering:
                model.Add(sum(covering) <= 1)

    cap = net_tile_ops
    need_wheat = [model.NewBoolVar(f"need_w_{worker}_{d}") for d in range(horizon)]
    need_fert = [model.NewBoolVar(f"need_f_{worker}_{d}") for d in range(horizon)]
    need_place = {
        (d, an): model.NewBoolVar(f"need_p_{worker}_{d}_{an}")
        for d in range(horizon)
        for an in ANIMAL_NAMES
    }
    locked_place = locked.get("daily_place") or _empty_daily_place(horizon)

    for day in range(horizon):
        for pi, pat in enumerate(patterns):
            if pat["daily_feed"][day]:
                for tile in zone_empty:
                    model.Add(need_wheat[day] >= x[pi, tile])
            if pat["daily_fert"][day]:
                for tile in zone_empty:
                    model.Add(need_fert[day] >= x[pi, tile])
            pat_place = pat.get("daily_place") or {}
            for an in ANIMAL_NAMES:
                if pat_place.get(an, [0] * horizon)[day]:
                    for tile in zone_empty:
                        model.Add(need_place[(day, an)] >= x[pi, tile])

        terms = []
        for pi, pat in enumerate(patterns):
            n = pat["daily_tile_ops"][day]
            if not n:
                continue
            for tile in zone_empty:
                terms.append(x[pi, tile] * n)
        locked_ops = locked["daily_tile_ops"][day]
        locked_shed = 0
        if locked["daily_feed"][day] > 0:
            locked_shed += 1
        if locked["daily_fert"][day] > 0:
            locked_shed += 1
        for an in ANIMAL_NAMES:
            if locked_place.get(an, [0] * horizon)[day]:
                locked_shed += 1
        shed_terms = [
            need_wheat[day],
            need_fert[day],
            *[need_place[(day, an)] for an in ANIMAL_NAMES],
        ]
        model.Add(
            sum(terms) + locked_ops + sum(shed_terms) + locked_shed <= cap
        )

    buy_w: list = []
    buy_f: list = []
    buy_w_cost: list = []
    buy_f_cost: list = []

    if track_shed:
        w_vars = [model.NewIntVar(0, MAX_BUY, f"W_{worker}_{d}") for d in range(horizon + 1)]
        f_vars = [model.NewIntVar(0, MAX_BUY, f"F_{worker}_{d}") for d in range(horizon + 1)]
        model.Add(w_vars[0] == w_open)
        model.Add(f_vars[0] == f_open)

        for d in range(horizon):
            feed_d = locked["daily_feed"][d] + sum(
                x[pi, tile] * pat["daily_feed"][d]
                for pi, pat in enumerate(patterns)
                for tile in zone_empty
            )
            fert_d = locked["daily_fert"][d] + sum(
                x[pi, tile] * pat["daily_fert"][d]
                for pi, pat in enumerate(patterns)
                for tile in zone_empty
            )
            collect_d = locked["daily_collect"][d] + sum(
                x[pi, tile] * pat["daily_collect"][d]
                for pi, pat in enumerate(patterns)
                for tile in zone_empty
            )
            wheat_d = locked["daily_wheat"][d] + sum(
                x[pi, tile] * pat["daily_wheat"][d]
                for pi, pat in enumerate(patterns)
                for tile in zone_empty
            )
            bw = model.NewIntVar(0, MAX_BUY, f"buy_w_{worker}_{d}")
            bf = model.NewIntVar(0, MAX_BUY, f"buy_f_{worker}_{d}")
            buy_w.append(bw)
            buy_f.append(bf)
            buy_w_cost.append(WHEAT_PRICE * bw)
            buy_f_cost.append(FERT_PRICE * bf)
            model.Add(w_vars[d] >= feed_d)
            model.Add(f_vars[d] >= fert_d)
            model.Add(w_vars[d + 1] == w_vars[d] - feed_d + wheat_d + bw)
            model.Add(f_vars[d + 1] == f_vars[d] - fert_d + collect_d + bf)

    balance_vars: list = []
    conservative_vars: list = []
    for d in range(horizon):
        day_terms = [locked["cash_by_day"][d]]
        spend_terms = [locked["spend_by_day"][d]]
        for pi, pat in enumerate(patterns):
            cash = pat["cash_by_day"][d]
            if cash:
                for tile in zone_empty:
                    day_terms.append(x[pi, tile] * cash)
            spend = pat["spend_by_day"][d]
            if spend:
                for tile in zone_empty:
                    spend_terms.append(x[pi, tile] * spend)
        if track_shed:
            day_terms.append(-WHEAT_PRICE * buy_w[d])
            day_terms.append(-FERT_PRICE * buy_f[d])
            spend_terms.append(-WHEAT_PRICE * buy_w[d])
            spend_terms.append(-FERT_PRICE * buy_f[d])
        hire = HAND_DAILY_COST.get(worker, 0)
        if charge_hire_daily and worker in HAND_WORKERS:
            day_terms.append(-hire)
            spend_terms.append(-hire)

        if worker in HAND_WORKERS:
            prev = (
                opening_balances[d]
                if d < len(opening_balances)
                else opening_balances[-1]
            )
        elif d == 0:
            prev = opening_balances[0]
        else:
            prev = opening_balances[d] + (balance_vars[d - 1] - opening_balances[0])

        bal_floor = min_balance if min_balance > 0 else 0
        bal = model.NewIntVar(bal_floor, 200_000, f"balance_{worker}_{d}")
        model.Add(bal == prev + (sum(day_terms) if day_terms else 0))
        balance_vars.append(bal)

        if worker in HAND_WORKERS:
            start_d = prev
        elif d == 0:
            start_d = opening_balances[0]
        else:
            start_d = opening_balances[d] + (
                conservative_vars[d - 1] - opening_balances[0]
            )
        cons = model.NewIntVar(-200_000, 200_000, f"cons_{worker}_{d}")
        model.Add(cons == start_d + (sum(spend_terms) if spend_terms else 0))
        conservative_vars.append(cons)

    zone_weights = [_pattern_weight(pat, locked_counts, price_of) for pat in patterns]
    obj_terms = [
        zone_weights[pi] * x[pi, tile]
        for pi, _pat in enumerate(patterns)
        for tile in zone_empty
    ]
    concave_log_parts: list[str] = []
    concave_seg_vars: list[tuple[int, cp_model.IntVar]] = []

    if sink_units is not None and market_inv is not None:
        inv_map = {p: int(market_inv.get(p, pricing.I0_DEFAULT)) for p in CONCAVE_PRODUCTS}
        inv_map["WHEAT"] = int(market_inv.get("WHEAT", pricing.I0_DEFAULT))
        carried = locked_counts
        for product in CONCAVE_PRODUCTS:
            if not any(
                int(pat.get("harvest_units", {}).get(product, 0)) > 0
                for pat in patterns
            ):
                continue
            max_u = _max_zone_product_units(patterns, zsize, product)
            if max_u <= 0:
                continue
            segments, meta = build_revenue_curves(
                product,
                patterns=patterns,
                horizon=horizon,
                zone_size=zsize,
                market_inv=inv_map,
                locked_counts=locked_counts,
                sink_units=sink_units,
                opp_units=opp_units,
                carried=carried,
                wheat_feed_units=wheat_feed_units if product == "WHEAT" else 0,
            )
            if not segments:
                continue
            concave_log_parts.append(
                f"{product} D={meta['D']} carried={meta['carried']} "
                f"opp={meta['opp']} D_rem={meta['D_remaining']} "
                f"m0={meta['m0']} mlast={meta['mlast']}"
            )
            unit_terms = [
                x[pi, tile] * int(pat["harvest_units"][product])
                for pi, pat in enumerate(patterns)
                if int(pat["harvest_units"].get(product, 0)) > 0
                for tile in zone_empty
            ]
            if not unit_terms:
                continue
            u_total = model.NewIntVar(0, max_u, f"U_{worker}_{product}")
            model.Add(u_total == sum(unit_terms))
            seg_vars: list[cp_model.IntVar] = []
            for ki, (cap, marginal) in enumerate(segments):
                u_k = model.NewIntVar(0, cap, f"u_{worker}_{product}_{ki}")
                model.Add(u_k <= cap)
                obj_terms.append(marginal * u_k)
                concave_seg_vars.append((marginal, u_k))
                seg_vars.append(u_k)
            model.Add(sum(seg_vars) == u_total)

        if concave_log_parts:
            print(
                f"[concave] zone={worker} " + " | ".join(concave_log_parts),
                flush=True,
            )

    if track_shed:
        obj_terms.extend(-c for c in buy_w_cost)
        obj_terms.extend(-c for c in buy_f_cost)
    model.Maximize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 8
    solver.parameters.max_time_in_seconds = max_time
    early_target = OBJ_EARLY_STOP * horizon / NUM_DAYS
    callback = _ObjEarlyStop(early_target)
    t0 = time.perf_counter()
    status = solver.Solve(model, callback)
    elapsed = time.perf_counter() - t0

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(
            f"[milos/wsp] zone={worker} status={solver.StatusName(status)} "
            f"time={elapsed:.3f}s empty={zsize}",
            flush=True,
        )
        return None

    picked = []
    for pi, pat in enumerate(patterns):
        for tile in zone_empty:
            if solver.Value(x[pi, tile]) == 1:
                picked.append({"tile": tile, "pattern": pat})

    pattern_obj = sum(
        zone_weights[pi] * solver.Value(x[pi, tile])
        for pi, _pat in enumerate(patterns)
        for tile in zone_empty
    )
    concave_obj = sum(m * solver.Value(u) for m, u in concave_seg_vars)
    print(
        f"[concave_obj] zone={worker} pattern={pattern_obj:.0f} "
        f"concave={concave_obj:.0f} total={solver.ObjectiveValue():.0f}",
        flush=True,
    )

    print(
        f"[milos/wsp] zone={worker} {solver.StatusName(status)} "
        f"obj={solver.ObjectiveValue():.0f} time={elapsed:.3f}s "
        f"empty={zsize} picks={len(picked)}",
        flush=True,
    )

    return {
        "picked": picked,
        "balance": [int(solver.Value(b)) for b in balance_vars],
        "conservative": [int(solver.Value(c)) for c in conservative_vars],
        "objective": int(solver.ObjectiveValue()),
    }
