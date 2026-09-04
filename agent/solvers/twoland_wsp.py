"""Sequential per-zone WSP with land-2 probe: day-0 from wsp_prestart.json (land 1 only)."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from ortools.sat.python import cp_model

from agent import animal_rollouts, pricing
from agent.solvers.common import decode_sort_key
from agent.solvers.types import SolveResult
from agent.zoning import (
    HAND_DAILY_COST,
    HAND_WORKERS,
    LAND1_TILE_COUNT,
    LAND1_WORKERS,
    LAND2_WORKERS,
    NET_TILE_OPS,
    NUM_TILES,
    WORKER_TILES,
    WORKERS,
)

NUM_DAYS = 30
LAND2_PROBE_WORKER = "hire5"
LAND2_BUY_COST = 1000
WHEAT_PRICE = 25
FERT_PRICE = 100
MAX_BUY = NUM_TILES * NUM_DAYS
OBJ_EARLY_STOP = 5_000
PER_TILE_FLOOR = 400
PROBE_ZONE_TIME = 0.3

_PROBE_CACHE: dict | None = None

CROP_PROFILES = ("no_fert", "with_fert")
ANIMAL_PROFILES = ("no_care", "with_care")
PROFILE_SUFFIXES = ("no_fert", "with_fert", "no_care", "with_care")
GLUT_PRODUCTS = ("MELON", "STRAWBERRY", "MILK", "WOOL")

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
        if worker in HAND_WORKERS:
            start_d = opening[d] if d < len(opening) else opening[-1]
        elif d == 0:
            start_d = opening[0]
        else:
            start_d = opening[d] + (conservative[d - 1] - opening[0])
        spend_d = locked_spend[d]
        if charge_hire_daily and worker in HAND_WORKERS:
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
    return all(
        empty_counts.get(worker, 0) == len(WORKER_TILES[worker])
        for worker in LAND1_WORKERS
    )


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


def _seed_locked_harvest(
    locked_by_worker: dict[str, dict],
    market_inv: dict[str, int] | None = None,
) -> dict[str, int]:
    """Seed booked volume from locked tile daily harvest vectors."""
    del market_inv
    counts: dict[str, int] = {}
    for locked in locked_by_worker.values():
        for product in GLUT_PRODUCTS:
            daily = locked.get("daily_harvest", {}).get(product)
            if daily:
                counts[product] = counts.get(product, 0) + sum(daily)
    return counts


def _marginal_glut_price(
    product: str,
    already_booked: int,
    market_inv: dict[str, int] | None,
) -> int:
    inv = int((market_inv or {}).get(product, pricing.MARKET_PARAMS[product].i0))
    return pricing.marginal_unit_price(product, inv, already_booked, 1)


def _pattern_weight(
    pat,
    locked_counts: dict[str, int],
    price_of: Callable[[str], int],
    market_inv: dict[str, int] | None = None,
) -> int:
    del price_of
    rev = 0
    booked = dict(locked_counts)
    for product, _hday, yld in pat["harvest_lines"]:
        unit = _marginal_glut_price(product, booked.get(product, 0), market_inv)
        rev += yld * unit
        booked[product] = booked.get(product, 0) + yld
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
    market_inv: dict[str, int] | None = None,
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
        if worker in HAND_WORKERS:
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

    zone_weights = [
        _pattern_weight(pat, locked_counts, price_of, market_inv) for pat in patterns
    ]
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
    early_target = PER_TILE_FLOOR * zsize * horizon / NUM_DAYS
    callback = _ObjEarlyStop(early_target)
    t0 = time.perf_counter()
    status = solver.Solve(model, callback)
    elapsed = time.perf_counter() - t0
    n_patterns = len(patterns)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(
            f"[planner] twoland_wsp zone={worker} status={solver.StatusName(status)} "
            f"time={elapsed:.3f}s empty={zsize} n_patterns={n_patterns} "
            f"early_stopped={callback.stopped_early} written=0 "
            f"open0={opening_balances[0] if opening_balances else 'N/A'}",
            flush=True,
        )
        return None

    picked = []
    for pi, pat in enumerate(patterns):
        for tile in zone_empty:
            if solver.Value(x[pi, tile]) == 1:
                picked.append({"tile": tile, "pattern": pat})

    w_levels = (
        [int(solver.Value(w_vars[d])) for d in range(horizon + 1)] if track_shed else []
    )
    f_levels = (
        [int(solver.Value(f_vars[d])) for d in range(horizon + 1)] if track_shed else []
    )

    print(
        f"[planner] twoland_wsp zone={worker} {solver.StatusName(status)} "
        f"obj={solver.ObjectiveValue():.0f} time={elapsed:.3f}s "
        f"close0={int(solver.Value(balance_vars[0]))} "
        f"cons0={int(solver.Value(conservative_vars[0]))} "
        f"open0={opening_balances[0] if opening_balances else 'N/A'} "
        f"empty={zsize} picks={len(picked)} n_patterns={n_patterns} "
        f"early_stopped={callback.stopped_early} written=1",
        flush=True,
    )

    return {
        "picked": picked,
        "balance": [int(solver.Value(b)) for b in balance_vars],
        "conservative": [int(solver.Value(c)) for c in conservative_vars],
        "w_levels": w_levels,
        "f_levels": f_levels,
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
    land_owned: bool = False,
    buy_morning: bool = False,
    market_inventory: dict[str, int] | None = None,
) -> SolveResult:
    global _PROBE_CACHE
    del chains, cascade_reserve
    if _is_prestart_solve(horizon, empty_tiles, empty_counts):
        assigned, complete, solved_workers = _load_prestart()
        print(
            f"[planner] twoland_wsp prestart loaded tiles={len(assigned)} complete={complete}",
            flush=True,
        )
        return SolveResult(assigned, complete, solved_workers)

    if price_of is None:
        base = _i0_base_prices()
        price_of = lambda product, _base=base: _base[product]

    probe_mode = not land_owned and not buy_morning
    if probe_mode:
        worker_list = list(LAND1_WORKERS) + [LAND2_PROBE_WORKER]
    else:
        worker_list = list(WORKERS)

    empty_set = set(empty_tiles)
    if probe_mode:
        empty_set.update(WORKER_TILES[LAND2_PROBE_WORKER])

    zone_weights_time = []
    for worker in worker_list:
        if probe_mode and worker == LAND2_PROBE_WORKER:
            n_empty = len(WORKER_TILES[worker])
        else:
            n_empty = empty_counts.get(worker, 0)
        zone_weights_time.append(max(1, n_empty * horizon))
    weight_sum = sum(zone_weights_time) or 1

    opening = [starting_money] * horizon
    if buy_morning and not land_owned:
        opening[0] -= LAND2_BUY_COST

    assigned: dict[int, list] = {}
    solved_workers: list[str] = []
    locked_harvest = _seed_locked_harvest(locked_by_worker, market_inventory)
    patterns = build_patterns(horizon, price_of)
    buy_land = False
    w_levels = [0] * (horizon + 1)
    f_levels = [0] * (horizon + 1)
    probe_affordable = starting_money >= LAND2_BUY_COST

    for wi, worker in enumerate(worker_list):
        per_zone_time = max_time * zone_weights_time[wi] / weight_sum
        if probe_mode and worker == LAND2_PROBE_WORKER:
            if not probe_affordable:
                break
            per_zone_time = min(PROBE_ZONE_TIME, per_zone_time)
            n_empty = len(WORKER_TILES[worker])
        else:
            n_empty = empty_counts.get(worker, 0)
        locked = locked_by_worker[worker]
        if n_empty == 0:
            if not land_owned and worker not in LAND1_WORKERS:
                break
            opening = _locked_conservative_handoff(
                opening,
                locked,
                horizon,
                worker,
                charge_hire_daily=charge_hire_daily,
            )
            solved_workers.append(worker)
            continue

        if buy_morning and not land_owned and worker in LAND2_WORKERS and _PROBE_CACHE:
            cached = _PROBE_CACHE.get("assigned", {})
            zone_tiles = set(WORKER_TILES[worker])
            for idx, chain in cached.items():
                if idx in zone_tiles:
                    assigned[idx] = chain
            solved_workers.append(worker)
            continue

        if probe_mode and worker == LAND2_PROBE_WORKER:
            zone_empty = list(WORKER_TILES[worker])
        else:
            zone_empty = [idx for idx in WORKER_TILES[worker] if idx in empty_set]
        if worker == WORKERS[0] and track_shed:
            w_open = w_open0
            f_open = f_open0
        elif worker != WORKERS[0] and track_shed:
            w_open = w_levels[1]
            f_open = f_levels[1]
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
            market_inv=market_inventory,
        )
        if res is None:
            if probe_mode and worker == LAND2_PROBE_WORKER:
                break
            break

        if probe_mode and worker == LAND2_PROBE_WORKER:
            cons = res["conservative"]
            leftover = cons[1] if len(cons) > 1 else cons[0]
            if leftover >= LAND2_BUY_COST:
                buy_land = True
                probe_assigned = _decode_wsp_assignment(
                    worker, empty_set, res["picked"]
                )
                _PROBE_CACHE = {"assigned": probe_assigned}
                print(
                    f"[planner] twoland_wsp probe hire5 ok cons_left={leftover} "
                    f"buy_land tomorrow",
                    flush=True,
                )
            break

        if buy_morning and worker in LAND2_WORKERS:
            _PROBE_CACHE = None

        assigned.update(_decode_wsp_assignment(worker, empty_set, res["picked"]))
        for pick in res["picked"]:
            for prod, units in pick["pattern"]["harvest_units"].items():
                locked_harvest[prod] = locked_harvest.get(prod, 0) + units
        opening = res["conservative"]
        if opening[0] < 0:
            print(
                f"[planner] twoland_wsp zone={worker} handoff open0={opening[0]} < 0, "
                f"stop cascade",
                flush=True,
            )
            solved_workers.append(worker)
            break
        if track_shed:
            w_levels = res["w_levels"]
            f_levels = res["f_levels"]
        solved_workers.append(worker)

    complete = len(solved_workers) == len(WORKERS) and not probe_mode
    return SolveResult(
        assigned,
        complete,
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
    *,
    write_all_solved: bool = False,
) -> int:
    if not result.solved_workers or result.solved_workers[0] != WORKERS[0]:
        return 0

    written = 0
    replan_set = set(replan_tiles)
    for worker in result.solved_workers:
        for idx in WORKER_TILES[worker]:
            if not write_all_solved and idx not in replan_set:
                continue
            chain = result.assigned.get(idx, [])
            if not chain and tile_queues.get(idx):
                print(
                    f"[planner] twoland_wsp apply_replan t{idx + 1}: "
                    f"preserve stale queue (empty chain)",
                    flush=True,
                )
                continue
            tile_queues[idx] = chain_to_queue_items(chain, horizon)
            written += 1
            if tile_state is not None:
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
