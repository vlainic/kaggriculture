"""Handmade-chain assignment planner: CP-SAT once at import -> TILE_QUEUES."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from agent import animal_rollouts, rollouts
from ortools.sat.python import cp_model

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

NUM_DAYS = 30
NUM_TILES = 25
WHEAT_PRICE = 25
FERT_PRICE = 100
MAX_BUY = NUM_TILES * NUM_DAYS
STARTING_MONEY = 3000
HIRE_DAILY_COST = 1 + 1 + 2

WORKERS = ("farmer", "hire1", "hire2", "hire3")
HAND_WORKERS = ("hire1", "hire2", "hire3")
WORKER_TILES = {
    "farmer": list(range(0, 9)),
    "hire1": list(range(9, 15)),
    "hire2": list(range(15, 21)),
    "hire3": list(range(21, 25)),
}
NET_TILE_OPS = {"farmer": 15, "hire1": 13, "hire2": 13, "hire3": 11}
PROFILE_SUFFIXES = ("no_fert", "with_fert", "no_care", "with_care")
ANIMAL_NAMES = frozenset(animal_rollouts.animal_names())

ZERO_DAILY = {
    "daily_tile_ops": [0] * NUM_DAYS,
    "daily_wheat_pickup": [0] * NUM_DAYS,
    "daily_animal_place": [0] * NUM_DAYS,
    "daily_animal_active": [0] * NUM_DAYS,
    "daily_fert_pickup": [0] * NUM_DAYS,
    "daily_feed": [0] * NUM_DAYS,
    "daily_fert": [0] * NUM_DAYS,
    "daily_collect": [0] * NUM_DAYS,
    "daily_wheat": [0] * NUM_DAYS,
}

_cached_queues: dict | None = None


def _load_json(name: str) -> dict | list:
    with (_DATA_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


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


def _build_cash_by_day(start_day, setup_cost, base_price, profile):
    cash = [0] * NUM_DAYS
    cash[start_day] -= setup_cost
    for age, yld in zip(profile["harvest_ages"], profile["yield_per_harvest"]):
        hday = start_day + age
        if hday < NUM_DAYS:
            cash[hday] += yld * base_price
    return cash


def _stamp_placement(profile_key: str, start_day: int, crops_data: dict, animals_data: dict):
    build_day_offset = animals_data["meta"].get("build_day_offset", -1)
    label, profile_name = _parse_profile_key(profile_key)
    kind, spec, profile = _rollout_spec(label, profile_name, crops_data, animals_data)
    setup_cost = spec["seed_cost"] if kind == "crop" else spec["animal_cost"]
    base_price = spec["base_price"]
    feed_by_age, fert_use_by_age, collect_by_age, wheat_gain_by_age = _parse_age_maps(
        profile, label, kind
    )

    daily_tile_ops = [0] * NUM_DAYS
    daily_wheat_pickup = [0] * NUM_DAYS
    daily_animal_place = [0] * NUM_DAYS
    daily_animal_active = [0] * NUM_DAYS
    daily_fert_pickup = [0] * NUM_DAYS
    daily_feed = [0] * NUM_DAYS
    daily_fert = [0] * NUM_DAYS
    daily_collect = [0] * NUM_DAYS
    daily_wheat = [0] * NUM_DAYS
    occupied = []

    if kind == "crop":
        for day in profile["days"]:
            cal = start_day + day["age"]
            if cal >= NUM_DAYS:
                return None
            occupied.append(cal)
            acts = day["actions"]
            daily_tile_ops[cal] += len(acts)
            if "FERTILIZE" in acts:
                daily_fert_pickup[cal] += 1
            age = day["age"]
            daily_feed[cal] += feed_by_age.get(age, 0)
            daily_fert[cal] += fert_use_by_age.get(age, 0)
            daily_collect[cal] += collect_by_age.get(age, 0)
            daily_wheat[cal] += wheat_gain_by_age.get(age, 0)
    else:
        for day in profile["days"]:
            cal = start_day + day["age"]
            if cal >= NUM_DAYS:
                break
            occupied.append(cal)
            acts = day["actions"]
            age = day["age"]
            daily_tile_ops[cal] += len(acts)
            if "FEED" in acts:
                daily_wheat_pickup[cal] += 1
            if age == 0:
                daily_animal_place[cal] = 1
            daily_animal_active[cal] = 1
            daily_feed[cal] += feed_by_age.get(age, 0)
            daily_fert[cal] += fert_use_by_age.get(age, 0)
            daily_collect[cal] += collect_by_age.get(age, 0)
            daily_wheat[cal] += wheat_gain_by_age.get(age, 0)
        if not occupied:
            return None
        build_day = start_day + build_day_offset
        if build_day < 0:
            build_day = start_day
        if build_day < NUM_DAYS:
            daily_tile_ops[build_day] += 1

    rev = sum(
        yld * base_price
        for age, yld in zip(profile["harvest_ages"], profile["yield_per_harvest"])
        if start_day + age < NUM_DAYS
    )
    cash = _build_cash_by_day(start_day, setup_cost, base_price, profile)
    return {
        "weight": rev - setup_cost,
        "cash_by_day": cash,
        "daily_tile_ops": daily_tile_ops,
        "daily_wheat_pickup": daily_wheat_pickup,
        "daily_animal_place": daily_animal_place,
        "daily_animal_active": daily_animal_active,
        "daily_fert_pickup": daily_fert_pickup,
        "daily_feed": daily_feed,
        "daily_fert": daily_fert,
        "daily_collect": daily_collect,
        "daily_wheat": daily_wheat,
    }


def _add_daily(dst, src):
    for i in range(NUM_DAYS):
        dst[i] += src[i]


def _stamp_chain(chain, chain_idx, crops_data, animals_data):
    out = {k: v[:] for k, v in ZERO_DAILY.items()}
    cash_by_day = [0] * NUM_DAYS
    skipped = []
    for profile_key, start_day in chain:
        seg = _stamp_placement(profile_key, start_day, crops_data, animals_data)
        if seg is None:
            skipped.append((profile_key, start_day))
            continue
        for key in ZERO_DAILY:
            _add_daily(out[key], seg[key])
        _add_daily(cash_by_day, seg["cash_by_day"])
    return {
        "id": f"C{chain_idx}" if chain_idx >= 0 else "IDLE",
        "chain_idx": chain_idx,
        "raw_chain": chain,
        "weight": sum(cash_by_day),
        "cash_by_day": cash_by_day,
        **out,
        "skipped": skipped,
    }


def _build_chains(crops_data, animals_data, handmade_chains):
    chains = [_stamp_chain(chain, i, crops_data, animals_data) for i, chain in enumerate(handmade_chains)]
    chains.append(_stamp_chain([], -1, crops_data, animals_data) | {"id": "IDLE"})
    return chains


OBJECTIVE_GOOD_ENOUGH = 80_000


class _GoodEnoughCallback(cp_model.CpSolverSolutionCallback):
    def __init__(self, threshold: int):
        super().__init__()
        self.threshold = threshold
        self.hit = False

    def on_solution_callback(self):
        if self.ObjectiveValue() >= self.threshold:
            self.hit = True
            self.StopSearch()


def _solve_assignment(chains):
    model = cp_model.CpModel()
    count = {}
    for worker in WORKERS:
        zsize = len(WORKER_TILES[worker])
        count[worker] = [
            model.NewIntVar(0, zsize, f"n_{worker}_{c['id']}") for c in chains
        ]
        model.Add(sum(count[worker]) == zsize)

    for worker in WORKERS:
        cap = NET_TILE_OPS[worker]
        zsize = len(WORKER_TILES[worker])
        for day in range(NUM_DAYS):
            terms = []
            for ci, chain in enumerate(chains):
                var = count[worker][ci]
                for key in (
                    "daily_tile_ops",
                    "daily_wheat_pickup",
                    "daily_animal_place",
                    "daily_fert_pickup",
                ):
                    n = chain[key][day]
                    if n:
                        terms.append(var * n)

            if worker in HAND_WORKERS:
                animal_terms = [
                    count[worker][ci]
                    for ci, chain in enumerate(chains)
                    if chain["daily_animal_active"][day]
                ]
                preamble = model.NewBoolVar(f"preamble_{worker}_{day}")
                if animal_terms:
                    animal_count = sum(animal_terms)
                    model.Add(preamble <= animal_count)
                    model.Add(animal_count <= preamble * zsize)
                else:
                    model.Add(preamble == 0)
                terms.append(preamble)

            if terms:
                model.Add(sum(terms) <= cap)

    buy_w = []
    buy_f = []
    buy_w_cost = []
    buy_f_cost = []
    W = [model.NewIntVar(0, MAX_BUY, f"W_{d}") for d in range(NUM_DAYS + 1)]
    F = [model.NewIntVar(0, MAX_BUY, f"F_{d}") for d in range(NUM_DAYS + 1)]
    model.Add(W[0] == 0)
    model.Add(F[0] == 0)

    for d in range(NUM_DAYS):
        feed_d = sum(
            count[w][ci] * chains[ci]["daily_feed"][d]
            for w in WORKERS
            for ci in range(len(chains))
        )
        fert_d = sum(
            count[w][ci] * chains[ci]["daily_fert"][d]
            for w in WORKERS
            for ci in range(len(chains))
        )
        collect_d = sum(
            count[w][ci] * chains[ci]["daily_collect"][d]
            for w in WORKERS
            for ci in range(len(chains))
        )
        wheat_d = sum(
            count[w][ci] * chains[ci]["daily_wheat"][d]
            for w in WORKERS
            for ci in range(len(chains))
        )
        bw = model.NewIntVar(0, MAX_BUY, f"buy_w_{d}")
        bf = model.NewIntVar(0, MAX_BUY, f"buy_f_{d}")
        buy_w.append(bw)
        buy_f.append(bf)
        buy_w_cost.append(WHEAT_PRICE * bw)
        buy_f_cost.append(FERT_PRICE * bf)
        model.Add(W[d] >= feed_d)
        model.Add(F[d] >= fert_d)
        model.Add(W[d + 1] == W[d] - feed_d + wheat_d + bw)
        model.Add(F[d + 1] == F[d] - fert_d + collect_d + bf)

    balance_vars = []
    for d in range(NUM_DAYS):
        day_terms = []
        for w in WORKERS:
            for ci, chain in enumerate(chains):
                cash = chain["cash_by_day"][d]
                if cash:
                    day_terms.append(count[w][ci] * cash)
        day_terms.append(-WHEAT_PRICE * buy_w[d])
        day_terms.append(-FERT_PRICE * buy_f[d])
        day_terms.append(-HIRE_DAILY_COST)
        bal = model.NewIntVar(0, 200_000, f"balance_{d}")
        prev = STARTING_MONEY if d == 0 else balance_vars[-1]
        model.Add(bal == prev + (sum(day_terms) if day_terms else 0))
        balance_vars.append(bal)

    model.Maximize(
        sum(
            chains[ci]["weight"] * count[w][ci]
            for w in WORKERS
            for ci in range(len(chains))
        )
        - sum(buy_w_cost)
        - sum(buy_f_cost)
    )

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    callback = _GoodEnoughCallback(OBJECTIVE_GOOD_ENOUGH)
    t0 = time.perf_counter()
    status = solver.Solve(model, callback)
    elapsed = time.perf_counter() - t0

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"planner infeasible: {solver.StatusName(status)}")

    assigned = {tile: [] for tile in range(NUM_TILES)}
    for worker in WORKERS:
        remaining = list(WORKER_TILES[worker])
        for ci, chain in enumerate(chains):
            n = int(solver.Value(count[worker][ci]))
            for _ in range(n):
                assigned[remaining.pop(0)] = chain["raw_chain"]

    obj = solver.ObjectiveValue()
    print(
        f"[planner] status={solver.StatusName(status)} good_enough={callback.hit} "
        f"obj={obj:.0f} time={elapsed:.3f}s "
        f"tiles={sum(1 for c in assigned.values() if c)}",
        flush=True,
    )
    return assigned


def _occupancy_end(profile_key: str, start_day: int) -> int:
    label, profile_name = _parse_profile_key(profile_key)
    if label in ANIMAL_NAMES:
        return NUM_DAYS
    return start_day + rollouts.tile_free_age(label, profile_name)


def chain_to_queue_items(chain: list) -> list:
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
            prev_label, prev_profile = _parse_profile_key(prev_key)
            prev_end = _occupancy_end(prev_key, prev_start)
            items[i - 1] = QueueItem(
                kind=items[i - 1].kind,
                label=items[i - 1].label,
                profile=items[i - 1].profile,
                start_lag=items[i - 1].start_lag,
                replant_gap=max(0, start_day - prev_end),
                dig_before=items[i - 1].dig_before,
            )
    return items


def _build_from_solver() -> dict[int, list]:
    crops_data = _load_json("crop_rollouts.json")
    animals_data = _load_json("animal_rollouts.json")
    handmade_chains = _load_json("handmade_dp_candidates.json")
    chains = _build_chains(crops_data, animals_data, handmade_chains)
    assigned = _solve_assignment(chains)
    return {tile: chain_to_queue_items(assigned.get(tile, [])) for tile in range(NUM_TILES)}


def get_tile_queues(fallback: Callable[[], dict]) -> dict:
    global _cached_queues
    if _cached_queues is None:
        try:
            _cached_queues = _build_from_solver()
        except Exception as exc:
            print(f"[planner] fallback to script queues: {exc}", flush=True)
            _cached_queues = fallback()
    return _cached_queues
