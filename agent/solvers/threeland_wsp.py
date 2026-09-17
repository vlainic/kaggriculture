"""ThreeLand WSP: land1 prestart + NE@1k hire5 probe + SW@2k hire10 probe + cascade."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from ortools.sat.python import cp_model

from agent import animal_rollouts
from agent.solvers.common import decode_sort_key
from agent.solvers.types import SolveResult
from agent.zoning import (
    HAND_DAILY_COST,
    HAND_WORKERS,
    LAND1_TILE_COUNT,
    LAND1_WORKERS,
    LAND2_BUY_COST,
    LAND2_WORKERS,
    LAND3_BUY_COST,
    LAND3_WORKERS,
    NET_TILE_OPS,
    NUM_TILES,
    WORKER_TILES,
    WORKERS,
)

NEW_ZONE_MIN_DAY0_STARTS = 2
LAND2_PROBE_WORKER = LAND2_WORKERS[0]
LAND3_PROBE_WORKER = LAND3_WORKERS[0]
# CURRENT may be TWO; include catalog LAND3 hands for hire cost / preamble ops.
_ALL_HANDS = frozenset(HAND_WORKERS) | frozenset(LAND3_WORKERS)

NUM_DAYS = 30
WHEAT_PRICE = 25
FERT_PRICE = 100
MAX_BUY = NUM_TILES * NUM_DAYS
OBJ_EARLY_STOP = 5_000

CROP_PROFILES = ("no_fert", "with_fert")
ANIMAL_PROFILES = ("no_care", "with_care")
PROFILE_SUFFIXES = ("no_fert", "with_fert", "no_care", "with_care")
GLUT_CAPS = {
    "MELON": {"count_div": 52},
    "STRAWBERRY": {"count_div": 20},
    "MILK": {"count_div": 25},
    "WOOL": {"count_div": 19},
}
GLUT_PRODUCTS = tuple(GLUT_CAPS)
GLUT_FACTOR_MIN = 0.01

_PRESTART_PATH = Path(__file__).resolve().parent / "wsp_prestart.json"
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _load_json(name: str) -> dict:
    with (_DATA_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _i0_base_prices() -> dict[str, int]:
    crops_data = _load_json("crop_rollouts.json")
    animals_data = animal_rollouts.data()
    prices = {crop: spec["base_price"] for crop, spec in crops_data["crops"].items()}
    for spec in animals_data["animals"].values():
        prices[spec["product"]] = spec["base_price"]
    return prices


@lru_cache(maxsize=1)
def _load_prestart() -> tuple[dict[int, list], bool, tuple[str, ...]]:
    with _PRESTART_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    assigned = {int(k): list(v) for k, v in data["assigned"].items()}
    complete = bool(data.get("complete", True))
    solved = tuple(data.get("solved_workers", WORKERS))
    return assigned, complete, solved


def _locked_conservative_handoff(
    opening: list[int],
    locked: dict,
    horizon: int,
    worker: str,
    *,
    charge_hire_daily: bool,
) -> list[int]:
    conservative: list[int] = []
    hire = HAND_DAILY_COST.get(worker, 0) if charge_hire_daily else 0
    locked_spend = locked.get("spend_by_day", [0] * horizon)
    for d in range(horizon):
        if worker in _ALL_HANDS:
            start_d = opening[d] if d < len(opening) else opening[-1]
        elif d == 0:
            start_d = opening[0]
        else:
            start_d = opening[d] + (conservative[d - 1] - opening[0])
        spend_d = locked_spend[d]
        if charge_hire_daily and worker in _ALL_HANDS:
            spend_d -= hire
        conservative.append(start_d + spend_d)
    return conservative


def _is_prestart_solve(
    horizon: int,
    empty_tiles: list[int],
    empty_counts: dict[str, int],
) -> bool:
    if horizon != NUM_DAYS or len(empty_tiles) != LAND1_TILE_COUNT:
        return False
    if any(empty_counts.get(w, 0) != len(WORKER_TILES[w]) for w in LAND1_WORKERS):
        return False
    if any(empty_counts.get(w, 0) != 0 for w in LAND2_WORKERS):
        return False
    return all(empty_counts.get(w, 0) == 0 for w in LAND3_WORKERS)


def _count_day0_starts(picked: list) -> int:
    return sum(1 for p in picked if p["pattern"]["start_day"] == 0)


def _empty_locked_dict(horizon: int) -> dict:
    z = [0] * horizon
    return {
        "daily_tile_ops": list(z),
        "daily_feed": list(z),
        "daily_fert": list(z),
        "daily_collect": list(z),
        "daily_wheat": list(z),
        "daily_animal_active": list(z),
        "cash_by_day": list(z),
        "spend_by_day": list(z),
    }


def _probe_buy_ne(
    patterns,
    horizon,
    opening,
    price_of,
    *,
    max_time,
    charge_hire_daily,
) -> bool:
    """Throwaway hire5 solve; signal only (no assignment write)."""
    probe_opening = list(opening)
    probe_opening[0] -= LAND2_BUY_COST
    res = _solve_zone(
        LAND2_PROBE_WORKER,
        patterns,
        horizon=horizon,
        empty_tiles=list(WORKER_TILES[LAND2_PROBE_WORKER]),
        locked=_empty_locked_dict(horizon),
        locked_counts={},
        opening_balances=probe_opening,
        w_open=0,
        f_open=0,
        max_time=max_time,
        charge_hire_daily=charge_hire_daily,
        track_shed=False,
        min_balance=0,
        price_of=price_of,
    )
    if res is None:
        print("[planner] threeland probe hire5 INFEASIBLE defer", flush=True)
        return False
    day0 = _count_day0_starts(res["picked"])
    ok = day0 >= NEW_ZONE_MIN_DAY0_STARTS
    print(
        f"[planner] threeland probe hire5 day0={day0} "
        f"{'buy_land tomorrow' if ok else 'defer'}",
        flush=True,
    )
    return ok


def _probe_buy_sw(
    patterns,
    horizon,
    opening,
    price_of,
    *,
    max_time,
    charge_hire_daily,
) -> bool:
    """Throwaway hire10 solve @ $2k; signal only (no assignment write)."""
    probe_opening = list(opening)
    probe_opening[0] -= LAND3_BUY_COST
    res = _solve_zone(
        LAND3_PROBE_WORKER,
        patterns,
        horizon=horizon,
        empty_tiles=list(WORKER_TILES[LAND3_PROBE_WORKER]),
        locked=_empty_locked_dict(horizon),
        locked_counts={},
        opening_balances=probe_opening,
        w_open=0,
        f_open=0,
        max_time=max_time,
        charge_hire_daily=charge_hire_daily,
        track_shed=False,
        min_balance=0,
        price_of=price_of,
    )
    if res is None:
        print("[planner] threeland probe hire10 INFEASIBLE defer", flush=True)
        return False
    day0 = _count_day0_starts(res["picked"])
    ok = day0 >= NEW_ZONE_MIN_DAY0_STARTS
    print(
        f"[planner] threeland probe hire10 day0={day0} "
        f"{'buy_land tomorrow' if ok else 'defer'}",
        flush=True,
    )
    return ok


def _parse_profile_key(profile_key: str) -> tuple[str, str]:
    for suffix in PROFILE_SUFFIXES:
        token = f"_{suffix}"
        if profile_key.endswith(token):
            return profile_key[: -len(token)], suffix
    raise ValueError(f"unknown profile key: {profile_key}")


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


def _harvest_product(label: str, kind: str, animals_data: dict) -> str:
    if kind == "animal":
        return animals_data["animals"][label]["product"]
    return label


def _empty_daily_harvest(horizon: int) -> dict[str, list[int]]:
    return {p: [0] * horizon for p in GLUT_PRODUCTS}


def _glut_price_factor(product: str, count: int) -> float:
    spec = GLUT_CAPS.get(product)
    if spec is None:
        return 1.0
    return max(GLUT_FACTOR_MIN, 1.0 - count / spec["count_div"])


def _glut_unit_price(base: int, product: str, count: int) -> int:
    return max(1, int(round(base * _glut_price_factor(product, count))))


def _pattern_weight(
    pat,
    locked_counts: dict[str, int],
    price_of: Callable[[str], int],
) -> int:
    rev = 0
    for product, _hday, yld in pat["harvest_lines"]:
        count = locked_counts.get(product, 0)
        unit = _glut_unit_price(price_of(product), product, count)
        rev += yld * unit
    return rev - pat["setup_cost"]


def _stamp_placement(
    profile_key: str,
    start_day: int,
    horizon: int,
    price_of: Callable[[str], int],
    crops_data: dict,
    animals_data: dict,
):
    label, profile_name = _parse_profile_key(profile_key)
    kind, spec, profile = _rollout_spec(label, profile_name, crops_data, animals_data)
    setup_cost = spec["seed_cost"] if kind == "crop" else spec["animal_cost"]
    unit_price = price_of(_harvest_product(label, kind, animals_data))
    feed_by_age, fert_use_by_age, collect_by_age, wheat_gain_by_age = _parse_age_maps(
        profile, label, kind
    )

    daily_tile_ops = [0] * horizon
    daily_animal_active = [0] * horizon
    daily_feed = [0] * horizon
    daily_fert = [0] * horizon
    daily_collect = [0] * horizon
    daily_wheat = [0] * horizon
    occupied: list[int] = []

    if kind == "crop":
        for day in profile["days"]:
            cal = start_day + day["age"]
            if cal >= horizon:
                return None
            occupied.append(cal)
            acts = day["actions"]
            daily_tile_ops[cal] += len(acts)
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
            daily_tile_ops[cal] += len(acts)
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
    for _product, hday, yld in harvest_lines:
        if hday < horizon:
            cash_by_day[hday] += yld * unit_price

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
    }


def build_patterns(horizon: int, price_of: Callable[[str], int]) -> list:
    crops_data = _load_json("crop_rollouts.json")
    animals_data = animal_rollouts.data()
    patterns = []
    pid = 0
    for crop_name, crop_spec in crops_data["crops"].items():
        for profile_name in CROP_PROFILES:
            if profile_name not in crop_spec:
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

    for animal_name, animal_spec in animals_data["animals"].items():
        for profile_name in ANIMAL_PROFILES:
            if profile_name not in animal_spec:
                continue
            profile_key = f"{animal_name}_{profile_name}"
            for start_day in range(horizon):
                seg = _stamp_placement(
                    profile_key, start_day, horizon, price_of, crops_data, animals_data
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


def _decode_wsp_assignment(
    worker: str,
    empty_tiles: set[int],
    picked: list,
) -> dict[int, list]:
    remaining = [idx for idx in WORKER_TILES[worker] if idx in empty_tiles]
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


def _solve_zone(
    worker: str,
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
    charge_hire_daily: bool,
    track_shed: bool,
    min_balance: int = 0,
    price_of: Callable[[str], int] | None = None,
):
    zone_empty = list(empty_tiles)
    zsize = len(zone_empty)
    if zsize == 0:
        return None

    hire = HAND_DAILY_COST.get(worker, 0) if charge_hire_daily else 0
    model = cp_model.CpModel()
    x: dict[tuple[int, int], cp_model.IntVar] = {}
    for pi, pat in enumerate(patterns):
        for tile in zone_empty:
            x[pi, tile] = model.NewBoolVar(f"x_{worker}_{pat['id']}_t{tile}")

    for tile in zone_empty:
        for day in range(horizon):
            covering = [
                x[pi, tile]
                for pi, pat in enumerate(patterns)
                if day in pat["occupied_days"]
            ]
            if covering:
                model.Add(sum(covering) <= 1)

    cap = NET_TILE_OPS[worker]
    for day in range(horizon):
        terms = []
        for pi, pat in enumerate(patterns):
            n = pat["daily_tile_ops"][day]
            if not n:
                continue
            for tile in zone_empty:
                terms.append(x[pi, tile] * n)
        locked_ops = locked["daily_tile_ops"][day]
        if worker in _ALL_HANDS:
            animal_terms = [
                x[pi, tile]
                for pi, pat in enumerate(patterns)
                if pat["daily_animal_active"][day]
                for tile in zone_empty
            ]
            if animal_terms:
                preamble = model.NewBoolVar(f"preamble_{worker}_{day}")
                animal_count = sum(animal_terms)
                model.Add(preamble <= animal_count)
                model.Add(animal_count <= preamble * max(1, zsize))
                terms.append(preamble)
            elif locked["daily_animal_active"][day] > 0:
                locked_ops += 1
        if terms or locked_ops:
            model.Add(sum(terms) + locked_ops <= cap)

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
        if charge_hire_daily and worker in _ALL_HANDS:
            day_terms.append(-hire)
            spend_terms.append(-hire)

        if worker in _ALL_HANDS:
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

        if worker in _ALL_HANDS:
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
            f"[planner] wsp zone={worker} status={solver.StatusName(status)} "
            f"time={elapsed:.3f}s empty={zsize} "
            f"open0={opening_balances[0] if opening_balances else 'N/A'}",
            flush=True,
        )
        return None

    picked = []
    for pi, pat in enumerate(patterns):
        for tile in zone_empty:
            if solver.Value(x[pi, tile]) == 1:
                picked.append({"tile": tile, "pattern": pat})

    print(
        f"[planner] wsp zone={worker} {solver.StatusName(status)} "
        f"obj={solver.ObjectiveValue():.0f} time={elapsed:.3f}s "
        f"close0={int(solver.Value(balance_vars[0]))} "
        f"cons0={int(solver.Value(conservative_vars[0]))} "
        f"open0={opening_balances[0] if opening_balances else 'N/A'} "
        f"empty={zsize} picks={len(picked)}",
        flush=True,
    )

    return {
        "picked": picked,
        "balance": [int(solver.Value(b)) for b in balance_vars],
        "conservative": [int(solver.Value(c)) for c in conservative_vars],
    }


def solve(
    chains: list,
    *,
    horizon: int,
    empty_tiles: list[int],
    empty_counts: dict[str, int],
    locked_by_worker: dict[str, dict],
    starting_money: int,
    max_time: float = 20.0,
    charge_hire_daily: bool = True,
    track_shed: bool = True,
    w_open0: int = 0,
    f_open0: int = 0,
    cascade_reserve: bool = False,
    min_balance: int = 0,
    price_of: Callable[[str], int] | None = None,
    ne_owned: bool = False,
    sw_owned: bool = False,
    buy_morning: bool = False,
) -> SolveResult:
    del chains, cascade_reserve
    if _is_prestart_solve(horizon, empty_tiles, empty_counts):
        assigned, complete, solved_workers = _load_prestart()
        print(
            f"[planner] threeland prestart tiles={len(assigned)} complete={complete}",
            flush=True,
        )
        return SolveResult(assigned, complete, solved_workers)

    if price_of is None:
        base = _i0_base_prices()
        price_of = lambda product, _base=base: _base[product]

    ne_active = ne_owned or (buy_morning and not ne_owned)
    sw_active = sw_owned or (buy_morning and ne_owned and not sw_owned)
    worker_list = (
        LAND1_WORKERS
        + (LAND2_WORKERS if ne_active else ())
        + (LAND3_WORKERS if sw_active else ())
    )

    empty_set = set(empty_tiles)
    per_zone_time = max_time / max(1, len(worker_list))
    opening = [starting_money] * horizon
    if buy_morning and not ne_owned:
        opening[0] -= LAND2_BUY_COST
    elif buy_morning and ne_owned and not sw_owned:
        opening[0] -= LAND3_BUY_COST

    patterns = build_patterns(horizon, price_of)

    buy_land = False
    if not buy_morning:
        if not ne_owned:
            buy_land = _probe_buy_ne(
                patterns,
                horizon,
                opening,
                price_of,
                max_time=max(1.5, max_time * 0.15),
                charge_hire_daily=charge_hire_daily,
            )
        elif not sw_owned:
            buy_land = _probe_buy_sw(
                patterns,
                horizon,
                opening,
                price_of,
                max_time=max(1.5, max_time * 0.15),
                charge_hire_daily=charge_hire_daily,
            )

    print(
        f"[planner] threeland cascade workers={len(worker_list)} "
        f"ne_active={int(ne_active)} sw_active={int(sw_active)} open0={opening[0]}",
        flush=True,
    )
    if sw_active:
        # ops = daily_tile_ops only + hire animal preamble (+0/1); tape includes PICKUP
        print(
            "[planner] threeland ops-note land3 "
            "cap=NET_TILE_OPS animal_preamble=+0/1 tape_includes_PICKUP",
            flush=True,
        )

    assigned: dict[int, list] = {}
    solved_workers: list[str] = []
    locked_harvest: dict[str, int] = {}

    for worker in worker_list:
        n_empty = empty_counts.get(worker, 0)
        locked = locked_by_worker.get(worker) or _empty_locked_dict(horizon)
        if n_empty == 0:
            opening = _locked_conservative_handoff(
                opening,
                locked,
                horizon,
                worker,
                charge_hire_daily=charge_hire_daily,
            )
            solved_workers.append(worker)
            continue

        zone_empty = [idx for idx in WORKER_TILES[worker] if idx in empty_set]
        if worker == WORKERS[0] and track_shed:
            w_open = w_open0
            f_open = f_open0
        else:
            w_open = 0
            f_open = 0

        res = _solve_zone(
            worker,
            patterns,
            horizon=horizon,
            empty_tiles=zone_empty,
            locked=locked,
            locked_counts=locked_harvest,
            opening_balances=opening,
            w_open=w_open,
            f_open=f_open,
            max_time=per_zone_time,
            charge_hire_daily=charge_hire_daily,
            track_shed=track_shed,
            min_balance=min_balance,
            price_of=price_of,
        )
        if res is None:
            # TODO(two_land_fails §8): cascade break starves later zones (LAND3 behind LAND2).
            # Do not soft-continue — holes vs positional hands. Need skip/soft-cap design later.
            remaining = [w for w in worker_list if w not in solved_workers and w != worker]
            print(
                f"[planner] threeland cascade stop={worker} "
                f"solved={len(solved_workers)} starved={remaining} "
                f"sw_active={int(sw_active)}",
                flush=True,
            )
            # TODO(two_land_fails §10): no ratchet to drop permanently dead zones from hire count.
            if sw_active or worker in LAND2_WORKERS or worker in LAND3_WORKERS:
                print(
                    f"[planner] threeland dead-zone risk stop={worker} "
                    f"worker_list={len(worker_list)} solved={solved_workers}",
                    flush=True,
                )
            break

        assigned.update(_decode_wsp_assignment(worker, empty_set, res["picked"]))
        for pick in res["picked"]:
            for prod, units in pick["pattern"]["harvest_units"].items():
                locked_harvest[prod] = locked_harvest.get(prod, 0) + units
        opening = res["conservative"]
        solved_workers.append(worker)

    return SolveResult(
        assigned,
        len(solved_workers) == len(worker_list),
        tuple(solved_workers),
        buy_land=buy_land,
    )


def apply_replan(
    result: SolveResult,
    replan_tiles: list[int],
    tile_queues: dict,
    tile_state: dict | None,
    horizon: int,
    chain_to_queue_items,
) -> int:
    if not result.solved_workers or result.solved_workers[0] != WORKERS[0]:
        return 0

    written = 0
    replan_set = set(replan_tiles)
    for worker in result.solved_workers:
        for idx in WORKER_TILES[worker]:
            if idx not in replan_set:
                continue
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
