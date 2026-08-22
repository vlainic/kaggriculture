"""DP catalog + zone-count CP-SAT planner with dawn replan."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from agent import animal_rollouts, dp_catalog, rollouts, script
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
NET_TILE_OPS = {"farmer": 14, "hire1": 12, "hire2": 12, "hire3": 10}
PROFILE_SUFFIXES = ("no_fert", "with_fert", "no_care", "with_care")
ANIMAL_NAMES = frozenset(animal_rollouts.animal_names())
CROP_PROFILE = "no_fert"
ANIMAL_PROFILE = "with_care"

ZERO_DAILY_KEYS = (
    "daily_tile_ops",
    "daily_wheat_pickup",
    "daily_animal_place",
    "daily_animal_active",
    "daily_fert_pickup",
    "daily_feed",
    "daily_fert",
    "daily_collect",
    "daily_wheat",
)

_cached_queues: dict | None = None


def _load_json(name: str) -> dict | list:
    with (_DATA_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


def _i0_prices(crops_data: dict, animals_data: dict) -> dict[str, int]:
    prices = {crop: spec["base_price"] for crop, spec in crops_data["crops"].items()}
    for animal, spec in animals_data["animals"].items():
        prices[spec["product"]] = spec["base_price"]
    return prices


def _opponent_product_tile_counts(opp_farm: dict) -> dict[str, int]:
    """Count opponent tiles producing each market product (visible farm only)."""
    counts: dict[str, int] = {}
    for row in opp_farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            kind = tile.get("kind")
            if kind == "PLANT":
                crop = tile.get("crop")
                if crop:
                    counts[crop] = counts.get(crop, 0) + 1
            elif kind in ("COOP", "PASTURE"):
                animal = tile.get("animal")
                if animal:
                    product = animal_rollouts.product_for(animal)
                    counts[product] = counts.get(product, 0) + 1
    return counts


def effective_price(
    product: str,
    market_prices: dict,
    shops: list[str],
    i0_prices: dict[str, int],
    opp_tile_counts: dict[str, int] | None = None,
) -> int:
    demand = rollouts.shop_demand_by_product(shops)
    quoted = int(market_prices.get(product, i0_prices.get(product, 0)) or 0)
    opp = (opp_tile_counts or {}).get(product, 0)
    opp_bonus = max(0.1, 1.0 - opp / 10.0)
    return int(quoted * (1 + demand.get(product, 0) + opp_bonus))


def make_price_of(
    market_prices: dict,
    shops: list[str],
    i0_prices: dict[str, int],
    opp_tile_counts: dict[str, int] | None = None,
) -> Callable[[str], int]:
    def price_of(product: str) -> int:
        return effective_price(
            product, market_prices, shops, i0_prices, opp_tile_counts
        )

    return price_of


def _zero_daily(horizon: int) -> dict[str, list[int]]:
    return {key: [0] * horizon for key in ZERO_DAILY_KEYS}


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


def _product_for_label(label: str, kind: str) -> str:
    if kind == "animal":
        return animal_rollouts.product_for(label)
    return label


def _build_cash_by_day(
    start_day: int,
    setup_cost: int,
    unit_price: int,
    profile,
    horizon: int,
    *,
    min_age: int = 0,
    charge_setup: bool = True,
) -> list[int]:
    cash = [0] * horizon
    if charge_setup and start_day < horizon:
        cash[start_day] -= setup_cost
    for age, yld in zip(profile["harvest_ages"], profile["yield_per_harvest"]):
        if age < min_age:
            continue
        hday = start_day + (age - min_age)
        if hday < horizon:
            cash[hday] += yld * unit_price
    return cash


def _stamp_profile_segment(
    label: str,
    profile_name: str,
    rel_start: int,
    min_age: int,
    horizon: int,
    price_of: Callable[[str], int],
    crops_data: dict,
    animals_data: dict,
    *,
    charge_setup: bool,
):
    kind, spec, profile = _rollout_spec(label, profile_name, crops_data, animals_data)
    setup_cost = spec["seed_cost"] if kind == "crop" else spec["animal_cost"]
    unit_price = price_of(_product_for_label(label, kind))
    feed_by_age, fert_use_by_age, collect_by_age, wheat_gain_by_age = _parse_age_maps(
        profile, label, kind
    )
    build_day_offset = animals_data["meta"].get("build_day_offset", -1)

    out = _zero_daily(horizon)
    cash_by_day = [0] * horizon

    if kind == "crop":
        for day in profile["days"]:
            age = day["age"]
            if age < min_age:
                continue
            rel = rel_start + (age - min_age)
            if rel >= horizon:
                continue
            acts = day["actions"]
            out["daily_tile_ops"][rel] += len(acts)
            if "FERTILIZE" in acts:
                out["daily_fert_pickup"][rel] += 1
            out["daily_feed"][rel] += feed_by_age.get(age, 0)
            out["daily_fert"][rel] += fert_use_by_age.get(age, 0)
            out["daily_collect"][rel] += collect_by_age.get(age, 0)
            out["daily_wheat"][rel] += wheat_gain_by_age.get(age, 0)
    else:
        occupied = False
        for day in profile["days"]:
            age = day["age"]
            if age < min_age:
                continue
            rel = rel_start + (age - min_age)
            if rel >= horizon:
                break
            occupied = True
            acts = day["actions"]
            out["daily_tile_ops"][rel] += len(acts)
            if "FEED" in acts:
                out["daily_wheat_pickup"][rel] += 1
            if age == 0 and min_age == 0:
                out["daily_animal_place"][rel] = 1
            out["daily_animal_active"][rel] = 1
            out["daily_feed"][rel] += feed_by_age.get(age, 0)
            out["daily_fert"][rel] += fert_use_by_age.get(age, 0)
            out["daily_collect"][rel] += collect_by_age.get(age, 0)
            out["daily_wheat"][rel] += wheat_gain_by_age.get(age, 0)
        if not occupied:
            return None
        if min_age == 0:
            build_day = rel_start + build_day_offset
            if build_day < 0:
                build_day = rel_start
            if build_day < horizon:
                out["daily_tile_ops"][build_day] += 1

    cash_by_day = _build_cash_by_day(
        rel_start,
        setup_cost,
        unit_price,
        profile,
        horizon,
        min_age=min_age,
        charge_setup=charge_setup,
    )
    return {
        "weight": sum(cash_by_day),
        "cash_by_day": cash_by_day,
        **out,
    }


def _stamp_placement(
    profile_key: str,
    start_day: int,
    horizon: int,
    price_of: Callable[[str], int],
    crops_data: dict,
    animals_data: dict,
):
    label, profile_name = _parse_profile_key(profile_key)
    return _stamp_profile_segment(
        label,
        profile_name,
        start_day,
        0,
        horizon,
        price_of,
        crops_data,
        animals_data,
        charge_setup=True,
    )


def _add_daily(dst: list[int], src: list[int], horizon: int) -> None:
    for i in range(horizon):
        dst[i] += src[i]


def _stamp_chain(
    chain,
    chain_idx,
    horizon: int,
    price_of: Callable[[str], int],
    crops_data: dict,
    animals_data: dict,
):
    out = _zero_daily(horizon)
    cash_by_day = [0] * horizon
    skipped = []
    for profile_key, start_day in chain:
        seg = _stamp_placement(
            profile_key, start_day, horizon, price_of, crops_data, animals_data
        )
        if seg is None:
            skipped.append((profile_key, start_day))
            continue
        for key in ZERO_DAILY_KEYS:
            _add_daily(out[key], seg[key], horizon)
        _add_daily(cash_by_day, seg["cash_by_day"], horizon)
    return {
        "id": f"C{chain_idx}" if chain_idx >= 0 else "IDLE",
        "chain_idx": chain_idx,
        "raw_chain": chain,
        "weight": sum(cash_by_day),
        "cash_by_day": cash_by_day,
        **out,
        "skipped": skipped,
    }


def _build_chains(
    crops_data: dict,
    animals_data: dict,
    handmade_chains: list,
    horizon: int,
    price_of: Callable[[str], int],
):
    chains = [
        _stamp_chain(chain, i, horizon, price_of, crops_data, animals_data)
        for i, chain in enumerate(handmade_chains)
    ]
    chains.append(_stamp_chain([], -1, horizon, price_of, crops_data, animals_data) | {"id": "IDLE"})
    return chains


def _worker_for_tile(idx: int) -> str:
    for worker, indices in WORKER_TILES.items():
        if idx in indices:
            return worker
    return "farmer"


def _tile_at(me: dict, idx: int):
    from agent.script import TILE_COORDS

    x, y = TILE_COORDS[idx]
    return me["tiles"][y][x]


def _stamp_locked_tile(
    tile: dict,
    day: int,
    horizon: int,
    price_of: Callable[[str], int],
    crops_data: dict,
    animals_data: dict,
):
    if tile.get("kind") == "PLANT":
        crop = tile["crop"]
        current_age = day - tile["planted_day"]
        return _stamp_profile_segment(
            crop,
            CROP_PROFILE,
            0,
            current_age,
            horizon,
            price_of,
            crops_data,
            animals_data,
            charge_setup=False,
        )
    if tile.get("kind") in ("COOP", "PASTURE"):
        animal = tile.get("animal")
        if not animal:
            empty = _zero_daily(horizon)
            return {"weight": 0, "cash_by_day": [0] * horizon, **empty}
        current_age = day - tile["placed_day"]
        return _stamp_profile_segment(
            animal,
            ANIMAL_PROFILE,
            0,
            current_age,
            horizon,
            price_of,
            crops_data,
            animals_data,
            charge_setup=False,
        )
    empty = _zero_daily(horizon)
    return {"weight": 0, "cash_by_day": [0] * horizon, **empty}


def _aggregate_locked(
    locked_by_worker: dict[str, dict],
    worker: str,
    seg: dict,
    horizon: int,
) -> None:
    for key in ZERO_DAILY_KEYS:
        _add_daily(locked_by_worker[worker][key], seg[key], horizon)
    _add_daily(locked_by_worker[worker]["cash_by_day"], seg["cash_by_day"], horizon)


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


def _earliest_animal_day(raw_chain: list) -> int:
    best = 10**9
    for profile_key, start_day in raw_chain:
        label, _ = _parse_profile_key(profile_key)
        if label in ANIMAL_NAMES:
            best = min(best, int(start_day))
    return best


def _decode_sort_key(raw_chain: list) -> tuple:
    animal_day = _earliest_animal_day(raw_chain)
    if animal_day < 10**9:
        return (0, animal_day)
    if not raw_chain:
        return (1, 0)
    return (2, 0)


def _solve_assignment(
    chains,
    *,
    horizon: int,
    empty_tiles: list[int],
    empty_counts: dict[str, int],
    locked_by_worker: dict[str, dict],
    starting_money: int,
    max_time: float = 20.0,
):
    model = cp_model.CpModel()
    count = {}
    for worker in WORKERS:
        zempty = empty_counts[worker]
        count[worker] = [
            model.NewIntVar(0, zempty, f"n_{worker}_{c['id']}") for c in chains
        ]
        model.Add(sum(count[worker]) == zempty)

    for worker in WORKERS:
        cap = NET_TILE_OPS[worker]
        locked = locked_by_worker[worker]
        for day in range(horizon):
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
            locked_ops = (
                locked["daily_tile_ops"][day]
                + locked["daily_wheat_pickup"][day]
                + locked["daily_animal_place"][day]
                + locked["daily_fert_pickup"][day]
            )
            if worker in HAND_WORKERS:
                animal_terms = [
                    count[worker][ci]
                    for ci, chain in enumerate(chains)
                    if chain["daily_animal_active"][day]
                ]
                if animal_terms:
                    preamble = model.NewBoolVar(f"preamble_{worker}_{day}")
                    animal_count = sum(animal_terms)
                    model.Add(preamble <= animal_count)
                    model.Add(animal_count <= preamble * max(1, empty_counts[worker]))
                    terms.append(preamble)
                elif locked["daily_animal_active"][day] > 0:
                    locked_ops += 1

            if terms or locked_ops:
                model.Add(sum(terms) + locked_ops <= cap)

    buy_w = []
    buy_f = []
    buy_w_cost = []
    buy_f_cost = []
    W = [model.NewIntVar(0, MAX_BUY, f"W_{d}") for d in range(horizon + 1)]
    F = [model.NewIntVar(0, MAX_BUY, f"F_{d}") for d in range(horizon + 1)]
    model.Add(W[0] == 0)
    model.Add(F[0] == 0)

    for d in range(horizon):
        feed_d = sum(
            locked_by_worker[w]["daily_feed"][d]
            + sum(count[w][ci] * chains[ci]["daily_feed"][d] for ci in range(len(chains)))
            for w in WORKERS
        )
        fert_d = sum(
            locked_by_worker[w]["daily_fert"][d]
            + sum(count[w][ci] * chains[ci]["daily_fert"][d] for ci in range(len(chains)))
            for w in WORKERS
        )
        collect_d = sum(
            locked_by_worker[w]["daily_collect"][d]
            + sum(count[w][ci] * chains[ci]["daily_collect"][d] for ci in range(len(chains)))
            for w in WORKERS
        )
        wheat_d = sum(
            locked_by_worker[w]["daily_wheat"][d]
            + sum(count[w][ci] * chains[ci]["daily_wheat"][d] for ci in range(len(chains)))
            for w in WORKERS
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
    for d in range(horizon):
        day_terms = []
        for w in WORKERS:
            day_terms.append(locked_by_worker[w]["cash_by_day"][d])
            for ci, chain in enumerate(chains):
                cash = chain["cash_by_day"][d]
                if cash:
                    day_terms.append(count[w][ci] * cash)
        day_terms.append(-WHEAT_PRICE * buy_w[d])
        day_terms.append(-FERT_PRICE * buy_f[d])
        day_terms.append(-HIRE_DAILY_COST)
        bal = model.NewIntVar(0, 200_000, f"balance_{d}")
        prev = starting_money if d == 0 else balance_vars[-1]
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
    solver.parameters.num_workers = 8
    solver.parameters.max_time_in_seconds = max_time
    threshold = max(1000, int(OBJECTIVE_GOOD_ENOUGH * horizon / NUM_DAYS))
    callback = _GoodEnoughCallback(threshold)
    t0 = time.perf_counter()
    status = solver.Solve(model, callback)
    elapsed = time.perf_counter() - t0

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"planner infeasible: {solver.StatusName(status)}")

    empty_set = set(empty_tiles)
    assigned = {tile: [] for tile in range(NUM_TILES)}
    for worker in WORKERS:
        remaining = [idx for idx in WORKER_TILES[worker] if idx in empty_set]
        if not remaining:
            continue
        slots = []
        for ci, chain in enumerate(chains):
            n = int(solver.Value(count[worker][ci]))
            for _ in range(n):
                slots.append(chain["raw_chain"])
        slots.sort(key=_decode_sort_key)
        for i, idx in enumerate(remaining):
            assigned[idx] = slots[i]

    obj = solver.ObjectiveValue()
    print(
        f"[planner] status={solver.StatusName(status)} good_enough={callback.hit} "
        f"obj={obj:.0f} time={elapsed:.3f}s horizon={horizon} "
        f"empty={sum(empty_counts.values())}",
        flush=True,
    )
    return assigned


def _occupancy_end(profile_key: str, start_day: int, horizon: int) -> int:
    label, profile_name = _parse_profile_key(profile_key)
    if label in ANIMAL_NAMES:
        return horizon
    return start_day + rollouts.tile_free_age(label, profile_name)


def _replan_eligible(idx: int, tile, st: dict, queues: dict) -> bool:
    if tile is not None:
        return False
    queue = queues.get(idx, [])
    qi = st.get("queue_idx", 0)
    return qi >= len(queue)


def chain_to_queue_items(chain: list, horizon: int = NUM_DAYS) -> list:
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
            prev_end = _occupancy_end(prev_key, prev_start, horizon)
            items[i - 1] = QueueItem(
                kind=items[i - 1].kind,
                label=items[i - 1].label,
                profile=items[i - 1].profile,
                start_lag=items[i - 1].start_lag,
                replant_gap=max(0, start_day - prev_end),
                dig_before=items[i - 1].dig_before,
            )
    return items


def replan(obs: dict, tile_queues: dict, tile_state: dict | None = None) -> None:
    day = obs["day"]
    if day == 0 or day >= script.SEASON_LAST_DAY:
        return
    horizon = NUM_DAYS - day
    if horizon <= 0:
        return

    player = obs["player"]
    me = obs["farms"][player]
    shops = obs.get("town", {}).get("unlocked_shops", [])
    market_prices = obs.get("market", {}).get("prices", {})

    crops_data = _load_json("crop_rollouts.json")
    animals_data = _load_json("animal_rollouts.json")
    i0 = _i0_prices(crops_data, animals_data)
    opp_farm = obs["farms"][1 - player]
    opp_counts = _opponent_product_tile_counts(opp_farm)
    price_of = make_price_of(market_prices, shops, i0, opp_counts)

    handmade_chains = dp_catalog.build_catalog(horizon, price_of)
    chains = _build_chains(crops_data, animals_data, handmade_chains, horizon, price_of)

    replan_tiles = []
    preserved = 0
    empty_counts = {w: 0 for w in WORKERS}
    locked_by_worker = {w: _zero_daily(horizon) | {"cash_by_day": [0] * horizon} for w in WORKERS}

    for idx in range(NUM_TILES):
        tile = _tile_at(me, idx)
        worker = _worker_for_tile(idx)
        st = (tile_state or {}).get(idx, {})
        if tile is not None:
            seg = _stamp_locked_tile(tile, day, horizon, price_of, crops_data, animals_data)
            if seg:
                _aggregate_locked(locked_by_worker, worker, seg, horizon)
        elif _replan_eligible(idx, tile, st, tile_queues):
            replan_tiles.append(idx)
            empty_counts[worker] += 1
        else:
            preserved += 1

    if not replan_tiles:
        print(
            f"[planner] replan d={day} skip assign preserved={preserved}",
            flush=True,
        )
        return

    assigned = _solve_assignment(
        chains,
        horizon=horizon,
        empty_tiles=replan_tiles,
        empty_counts=empty_counts,
        locked_by_worker=locked_by_worker,
        starting_money=int(me["money"]),
        max_time=5.0,
    )

    for idx in replan_tiles:
        tile_queues[idx] = chain_to_queue_items(assigned.get(idx, []), horizon)
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
            }

    opp_log = " ".join(
        f"opp_{p}={n}" for p, n in sorted(opp_counts.items()) if n > 0
    )
    print(
        f"[planner] replan d={day} shops={len(shops)} "
        f"catalog={len(handmade_chains)} assign={len(replan_tiles)} preserved={preserved}"
        + (f" {opp_log}" if opp_log else ""),
        flush=True,
    )


def _build_from_solver() -> dict[int, list]:
    crops_data = _load_json("crop_rollouts.json")
    animals_data = _load_json("animal_rollouts.json")
    i0 = _i0_prices(crops_data, animals_data)
    price_of = make_price_of({}, [], i0)
    handmade_chains = dp_catalog.build_catalog(NUM_DAYS, price_of)
    chains = _build_chains(crops_data, animals_data, handmade_chains, NUM_DAYS, price_of)
    empty_counts = {w: len(WORKER_TILES[w]) for w in WORKERS}
    locked_by_worker = {w: _zero_daily(NUM_DAYS) | {"cash_by_day": [0] * NUM_DAYS} for w in WORKERS}
    assigned = _solve_assignment(
        chains,
        horizon=NUM_DAYS,
        empty_tiles=list(range(NUM_TILES)),
        empty_counts=empty_counts,
        locked_by_worker=locked_by_worker,
        starting_money=STARTING_MONEY,
        max_time=20.0,
    )
    return {
        tile: chain_to_queue_items(assigned.get(tile, []), NUM_DAYS)
        for tile in range(NUM_TILES)
    }


def get_tile_queues(fallback: Callable[[], dict]) -> dict:
    global _cached_queues
    if _cached_queues is None:
        try:
            _cached_queues = _build_from_solver()
        except Exception as exc:
            print(f"[planner] fallback to script queues: {exc}", flush=True)
            _cached_queues = fallback()
    return _cached_queues
