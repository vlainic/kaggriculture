"""Weighted set-packing planner for forward season assignments (crops + animals)."""

from __future__ import annotations

import time

from ortools.sat.python import cp_model

from agent import animal_rollouts, ops_budget, rollouts, workers

NUM_TILES = workers.NUM_TILES
PLAN_HORIZON = rollouts.PLAN_HORIZON
OPS_HORIZON = rollouts.SEASON_DAYS
SOLVER_TIME_LIMIT_S = 25.0
SOLVER_OVERAGE_SAFETY_S = 20.0

# tile, label (crop or animal name), start_day, profile, kind
TileState = tuple[int, str, int, str, str]


def _build_elements(current_day: int, horizon: int) -> list[tuple[int, int]]:
    return [
        (tile, day)
        for tile in range(NUM_TILES)
        for day in range(current_day, horizon)
    ]


def _ops_for_crop_lifecycle(
    crop: str,
    profile: str,
    plant_day: int,
    ops_horizon: int,
) -> tuple[dict[int, int], bool]:
    """Executor ops by calendar day; False if any action falls past ops_horizon."""
    ops_by_day: dict[int, int] = {}
    for age_day in rollouts.profile_days(crop, profile):
        cal = plant_day + age_day["age"]
        if cal >= ops_horizon:
            return {}, False
    ops_by_day = rollouts.executor_ops_by_day(crop, plant_day, ops_horizon, profile)
    if any(cal >= ops_horizon for cal in ops_by_day):
        return {}, False
    return ops_by_day, True


def _cash_by_day(s: dict, prices: dict[str, int], current_day: int) -> dict[int, int]:
    """Signed coin flow per calendar day for one candidate lifecycle."""
    out: dict[int, int] = {}
    start = s["start_day"]
    purchase_day = max(current_day, start - 1)

    if s["kind"] == "crop":
        crop = s["crop"]
        profile = s["profile"]
        seed = rollouts.seed_cost(crop)
        fert = rollouts.fert_count(crop, profile) * int(
            prices.get("FERTILIZER", 0) or 0
        )
        out[purchase_day] = out.get(purchase_day, 0) - seed - fert
        crop_price = int(prices.get(crop, 0) or 0)
        for age, units in zip(
            rollouts.harvest_ages(crop, profile),
            rollouts.yield_per_harvest(crop, profile),
        ):
            sale_day = start + age + 1
            out[sale_day] = out.get(sale_day, 0) + units * crop_price
    else:
        animal = s["animal"]
        profile = s["profile"]
        cost = animal_rollouts.animal_cost(animal)
        out[purchase_day] = out.get(purchase_day, 0) - cost
        wheat_price = int(prices.get("WHEAT", 0) or 0) or animal_rollouts.WHEAT_PRICE
        for _tile, cal in s["subset"]:
            out[cal] = out.get(cal, 0) - wheat_price
        product = animal_rollouts.product_for(animal)
        product_price = (
            int(prices.get(product, 0) or 0) or animal_rollouts.base_price(animal)
        )
        for age, units in zip(
            animal_rollouts.harvest_ages(animal, profile),
            animal_rollouts.yield_per_harvest(animal, profile),
        ):
            sale_day = start + age + 1
            out[sale_day] = out.get(sale_day, 0) + units * product_price
    return out


def _attach_cash_schedules(
    subsets: list[dict], prices: dict[str, int], current_day: int
) -> None:
    for s in subsets:
        s["cash_by_day"] = _cash_by_day(s, prices, current_day)


def _cash_subset_from_entry(
    entry: dict, plan_horizon: int, current_day: int
) -> dict:
    """Minimal subset dict for cash scheduling from a committed plan entry."""
    kind = entry.get("kind", "crop")
    start = entry["start_day"]
    tile = entry["tile"]
    profile = entry["profile"]
    if kind == "crop":
        crop = entry["crop"]
        covered = {
            (tile, cal)
            for cal in rollouts.covered_days(crop, start, plan_horizon, profile)
        }
        return {
            "kind": "crop",
            "crop": crop,
            "profile": profile,
            "start_day": start,
            "subset": covered,
        }
    animal = entry["animal"]
    covered = {
        (tile, cal)
        for cal in animal_rollouts.covered_days(animal, start, plan_horizon, profile)
    }
    return {
        "kind": "animal",
        "animal": animal,
        "profile": profile,
        "start_day": start,
        "subset": covered,
    }


def _cash_metrics(
    subsets: list[dict],
    money: int,
    current_day: int,
    ops_horizon: int,
) -> tuple[int, int]:
    """Return (peak cumulative spend, minimum balance) over the horizon."""
    balance = money
    min_bal = money
    cum_spend = 0
    peak_spend = 0
    for day in range(current_day, ops_horizon):
        flow = sum(s.get("cash_by_day", {}).get(day, 0) for s in subsets)
        if flow < 0:
            cum_spend -= flow
            peak_spend = max(peak_spend, cum_spend)
        balance += flow
        min_bal = min(min_bal, balance)
    return peak_spend, min_bal


def _min_balance(
    subsets: list[dict],
    money: int,
    current_day: int,
    ops_horizon: int,
) -> int:
    balance = money
    min_bal = money
    for day in range(current_day, ops_horizon):
        balance += sum(s.get("cash_by_day", {}).get(day, 0) for s in subsets)
        min_bal = min(min_bal, balance)
    return min_bal


def _earliest_start_by_tile(
    plannable_tiles: set[int],
    tile_states: list[TileState | None],
    current_day: int,
) -> dict[int, int]:
    """First calendar day a new lifecycle may start on each tile."""
    earliest = {tile: current_day for tile in plannable_tiles}
    for state in tile_states:
        if state is None:
            continue
        tile, label, start_day, profile, kind = state
        if kind == "crop":
            earliest[tile] = start_day + rollouts.tile_free_age(label, profile)
        else:
            # Animal tile stays occupied until horizon end (truncated in planner).
            earliest[tile] = OPS_HORIZON
    return earliest


def _build_crop_candidates(
    plannable_tiles: set[int],
    earliest_start: dict[int, int],
    current_day: int,
    plan_horizon: int,
    ops_horizon: int,
    prices: dict[str, int],
    shop_demand: dict[str, int] | None = None,
) -> list[dict]:
    elements = _build_elements(current_day, plan_horizon)
    element_set = set(elements)
    subsets: list[dict] = []
    demand = shop_demand or {}

    for crop, profile in rollouts.plant_options():
        seed = rollouts.seed_cost(crop)
        crop_price = int(prices.get(crop, 0) or 0)
        d = demand.get(crop, 0)
        yield_units = rollouts.expected_yield(crop, profile)
        fert_price = int(prices.get("FERTILIZER", 0) or 0)
        fert_cost = rollouts.fert_count(crop, profile) * fert_price
        weight = yield_units * crop_price * (1 + d) - seed - fert_cost

        for tile in plannable_tiles:
            start = max(earliest_start.get(tile, current_day), current_day)
            for plant_day in range(start, plan_horizon):
                if not rollouts.lifecycle_fits(crop, plant_day, ops_horizon, profile):
                    continue

                covered: set[tuple[int, int]] = set()
                ok = True
                free_age = rollouts.tile_free_age(crop, profile)
                for age in range(free_age):
                    cal = plant_day + age
                    if cal >= plan_horizon:
                        ok = False
                        break
                    cell = (tile, cal)
                    if cell not in element_set:
                        ok = False
                        break
                    covered.add(cell)

                if not ok or not covered:
                    continue

                ops_by_day, ops_ok = _ops_for_crop_lifecycle(
                    crop, profile, plant_day, ops_horizon
                )
                if not ops_ok:
                    continue

                subsets.append(
                    {
                        "id": f"S{len(subsets)}",
                        "kind": "crop",
                        "crop": crop,
                        "profile": profile,
                        "tile": tile,
                        "worker": workers.worker_for_tile(tile),
                        "start_day": plant_day,
                        "subset": covered,
                        "ops_by_day": ops_by_day,
                        "weight": weight,
                    }
                )

    return subsets


def _build_animal_candidates(
    plannable_tiles: set[int],
    earliest_start: dict[int, int],
    current_day: int,
    plan_horizon: int,
    ops_horizon: int,
    prices: dict[str, int],
    shop_demand: dict[str, int] | None = None,
) -> list[dict]:
    elements = _build_elements(current_day, plan_horizon)
    element_set = set(elements)
    subsets: list[dict] = []
    demand = shop_demand or {}
    wheat_price = int(prices.get("WHEAT", 0) or 0) or animal_rollouts.WHEAT_PRICE

    for animal, profile in animal_rollouts.animal_options():
        product = animal_rollouts.product_for(animal)
        d = demand.get(product, 0)
        cost = animal_rollouts.animal_cost(animal)
        product_price = (
            int(prices.get(product, 0) or 0) or animal_rollouts.base_price(animal)
        )

        for tile in plannable_tiles:
            start = max(earliest_start.get(tile, current_day), current_day)
            for place_day in range(start, plan_horizon):
                day_set = animal_rollouts.covered_days(
                    animal, place_day, plan_horizon, profile
                )
                if not day_set:
                    continue
                covered = {(tile, cal) for cal in day_set}
                if not covered.issubset(element_set):
                    continue

                ops_by_day = animal_rollouts.executor_ops_by_day(
                    animal, place_day, ops_horizon, profile, min_day=current_day
                )
                feed_days = len(covered)
                rev = animal_rollouts.revenue_in_window(
                    animal,
                    place_day,
                    ops_horizon,
                    profile,
                    unit_price=product_price,
                )
                weight = rev * (1 + d) - cost - feed_days * wheat_price

                subsets.append(
                    {
                        "id": f"S{len(subsets)}",
                        "kind": "animal",
                        "animal": animal,
                        "profile": profile,
                        "tile": tile,
                        "worker": workers.worker_for_tile(tile),
                        "start_day": place_day,
                        "subset": covered,
                        "ops_by_day": ops_by_day,
                        "weight": weight,
                    }
                )

    return subsets


def existing_ops_by_day(
    tile_states: list[TileState | None],
    current_day: int,
    horizon: int,
    weed_tiles: set[int] | None = None,
) -> dict[str, dict[int, int]]:
    """Per-worker ops from in-progress lifecycles and same-day weed DIG."""
    load: dict[str, dict[int, int]] = {w: {} for w in workers.WORKERS}
    for state in tile_states:
        if state is None:
            continue
        tile, label, start_day, profile, kind = state
        w = workers.worker_for_tile(tile)
        ops = ops_budget.executor_ops_by_day(
            kind, label, profile, start_day, horizon, min_day=current_day
        )
        for cal, n_ops in ops.items():
            if current_day <= cal < horizon:
                load[w][cal] = load[w].get(cal, 0) + n_ops
    if weed_tiles:
        for tile in weed_tiles:
            w = workers.worker_for_tile(tile)
            load[w][current_day] = load[w].get(current_day, 0) + 1
    return load


def plan_ops_by_day(
    plan_entries: list[dict],
    current_day: int,
    horizon: int,
) -> dict[str, dict[int, int]]:
    """Per-worker ops from committed plan entries (future commitments)."""
    load: dict[str, dict[int, int]] = {w: {} for w in workers.WORKERS}
    for entry in plan_entries:
        start_day = entry["start_day"]
        if start_day >= horizon:
            continue
        kind = entry.get("kind", "crop")
        profile = entry.get(
            "profile", "no_fert" if kind == "crop" else "no_care"
        )
        label = entry.get("crop") if kind == "crop" else entry.get("animal")
        if not label:
            continue
        w = workers.worker_for_tile(entry["tile"])
        ops = ops_budget.executor_ops_by_day(
            kind, label, profile, start_day, horizon, min_day=current_day
        )
        for cal, n_ops in ops.items():
            if current_day <= cal < horizon:
                load[w][cal] = load[w].get(cal, 0) + n_ops
    return load


def patch_plan(
    free_tiles: set[int],
    current_day: int,
    prices: dict[str, int],
    plan_entries: list[dict],
    money: int,
    shop_demand: dict[str, int] | None = None,
    plan_horizon: int = PLAN_HORIZON,
    ops_horizon: int = OPS_HORIZON,
) -> list[dict]:
    """Greedy-only fill for newly freed tiles; no CP-SAT."""
    if not free_tiles:
        return []

    earliest_start = {tile: current_day for tile in free_tiles}
    crop_subsets = _build_crop_candidates(
        free_tiles,
        earliest_start,
        current_day,
        plan_horizon,
        ops_horizon,
        prices,
        shop_demand,
    )
    animal_subsets = _build_animal_candidates(
        free_tiles,
        earliest_start,
        current_day,
        plan_horizon,
        ops_horizon,
        prices,
        shop_demand,
    )
    for i, s in enumerate(animal_subsets):
        s["id"] = f"S{len(crop_subsets) + i}"
    subsets = crop_subsets + animal_subsets
    if not subsets:
        print(
            f"[planner] patch day={current_day} no candidates "
            f"free_tiles={sorted(free_tiles)}"
        )
        return []

    existing_load = plan_ops_by_day(plan_entries, current_day, ops_horizon)
    committed_cash = [
        _cash_subset_from_entry(entry, plan_horizon, current_day)
        for entry in plan_entries
    ]
    _attach_cash_schedules(committed_cash, prices, current_day)
    _attach_cash_schedules(subsets, prices, current_day)
    placements, selected_subsets = _greedy_pack_with_subsets(
        subsets,
        existing_load,
        current_day,
        ops_horizon,
        money=money,
        committed_cash=committed_cash,
    )

    peak_by_worker = ops_budget.peak_load_by_worker(
        selected_subsets, existing_load, current_day, ops_horizon
    )
    peak_parts = " ".join(
        f"{w}={load}/{workers.net_tile_ops(w)}"
        for w, (peak_day, load) in peak_by_worker.items()
        if load > 0 or w == "farmer"
    )

    print(
        f"[planner] patch day={current_day} free_tiles={sorted(free_tiles)} "
        f"candidates={len(subsets)} (crop={len(crop_subsets)} "
        f"animal={len(animal_subsets)}) added={len(placements)} source=greedy"
    )
    if peak_parts:
        print(f"[planner] patch peak_ops {peak_parts}")
    for entry in sorted(placements, key=lambda e: (e["start_day"], e["tile"])):
        print(_format_placement(entry))
    return placements


def _format_placement(entry: dict) -> str:
    if entry.get("kind") == "animal":
        return (
            f"  animal {entry['animal']} {entry['profile']} "
            f"tile={entry['tile']} start={entry['start_day']}"
        )
    return (
        f"  crop {entry['crop']} {entry['profile']} "
        f"tile={entry['tile']} start={entry['start_day']}"
    )


def _log_plan(current_day: int, placements: list[dict]) -> None:
    for entry in sorted(placements, key=lambda e: (e["start_day"], e["tile"])):
        print(_format_placement(entry))


def _as_placements(selected: list[dict]) -> list[dict]:
    out: list[dict] = []
    for s in selected:
        entry = {
            "kind": s["kind"],
            "tile": s["tile"],
            "profile": s["profile"],
            "start_day": s["start_day"],
        }
        if s["kind"] == "crop":
            entry["crop"] = s["crop"]
        else:
            entry["animal"] = s["animal"]
        out.append(entry)
    return out


def _greedy_pack_with_subsets(
    subsets: list[dict],
    existing_load: dict[str, dict[int, int]],
    current_day: int,
    ops_horizon: int,
    money: int = 0,
    committed_cash: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Weight-descending greedy packing when CP-SAT yields nothing."""
    occupied: set[tuple[int, int]] = set()
    day_ops: dict[str, dict[int, int]] = {
        w: dict(existing_load.get(w, {})) for w in workers.WORKERS
    }
    chosen: list[dict] = []
    cash_base = list(committed_cash or [])

    for s in sorted(subsets, key=lambda x: x["weight"], reverse=True):
        if s["weight"] <= 0:
            continue
        if s["subset"] & occupied:
            continue
        w = s["worker"]
        cap = workers.net_tile_ops(w)
        fits = True
        for d, ops in s["ops_by_day"].items():
            if day_ops[w].get(d, 0) + ops > cap:
                fits = False
                break
        if not fits:
            continue
        if _min_balance(cash_base + chosen + [s], money, current_day, ops_horizon) < 0:
            continue
        occupied |= s["subset"]
        for d, ops in s["ops_by_day"].items():
            day_ops[w][d] = day_ops[w].get(d, 0) + ops
        chosen.append(s)

    return _as_placements(chosen), chosen


def _greedy_pack(
    subsets: list[dict],
    existing_load: dict[str, dict[int, int]],
    current_day: int,
    ops_horizon: int,
    money: int = 0,
    committed_cash: list[dict] | None = None,
) -> list[dict]:
    placements, _ = _greedy_pack_with_subsets(
        subsets,
        existing_load,
        current_day,
        ops_horizon,
        money=money,
        committed_cash=committed_cash,
    )
    return placements


def _solver_has_solution(solver: cp_model.CpSolver) -> bool:
    return bool(solver.ResponseProto().solution)


def _extract_solution(solver: cp_model.CpSolver, y: dict, subsets: list[dict]) -> list[dict]:
    selected = [s for s in subsets if solver.Value(y[s["id"]]) == 1]
    return _as_placements(selected)


def _selected_subsets(solver: cp_model.CpSolver, y: dict, subsets: list[dict]) -> list[dict]:
    return [s for s in subsets if solver.Value(y[s["id"]]) == 1]


def solve_plan(
    plannable_tiles: set[int],
    tile_states: list[TileState | None],
    current_day: int,
    prices: dict[str, int],
    money: int,
    plan_horizon: int = PLAN_HORIZON,
    ops_horizon: int = OPS_HORIZON,
    weed_tiles: set[int] | None = None,
    shop_demand: dict[str, int] | None = None,
    time_limit_s: float | None = None,
) -> list[dict]:
    """Return selected placements: [{kind, tile, crop|animal, profile, start_day}, ...]."""
    if not plannable_tiles:
        return []

    earliest_start = _earliest_start_by_tile(
        plannable_tiles, tile_states, current_day
    )
    elements = _build_elements(current_day, plan_horizon)
    crop_subsets = _build_crop_candidates(
        plannable_tiles,
        earliest_start,
        current_day,
        plan_horizon,
        ops_horizon,
        prices,
        shop_demand,
    )
    animal_subsets = _build_animal_candidates(
        plannable_tiles,
        earliest_start,
        current_day,
        plan_horizon,
        ops_horizon,
        prices,
        shop_demand,
    )
    for i, s in enumerate(animal_subsets):
        s["id"] = f"S{len(crop_subsets) + i}"
    subsets = crop_subsets + animal_subsets
    if not subsets:
        print(
            f"[planner] day={current_day} no candidates "
            f"tiles={sorted(plannable_tiles)}"
        )
        return []

    existing_load = existing_ops_by_day(
        tile_states, current_day, ops_horizon, weed_tiles
    )
    _attach_cash_schedules(subsets, prices, current_day)

    model = cp_model.CpModel()
    y = {s["id"]: model.NewBoolVar(s["id"]) for s in subsets}

    # Precompute (tile, day) -> covering vars and (worker, day) -> ops terms
    # once, instead of rescanning all subsets per element/worker/day (which
    # was O(elements*subsets) and O(workers*days*subsets) respectively).
    element_to_vars: dict[tuple[int, int], list] = {}
    worker_day_terms: dict[tuple[str, int], list] = {}
    for s in subsets:
        var = y[s["id"]]
        for e in s["subset"]:
            element_to_vars.setdefault(e, []).append(var)
        w = s["worker"]
        for day, ops in s["ops_by_day"].items():
            worker_day_terms.setdefault((w, day), []).append(var * ops)

    for e in elements:
        covering = element_to_vars.get(e)
        if covering:
            model.Add(sum(covering) <= 1)

    for worker in workers.WORKERS:
        for day in range(current_day, ops_horizon):
            operations = worker_day_terms.get((worker, day))
            cap = workers.net_tile_ops(worker) - existing_load.get(worker, {}).get(
                day, 0
            )
            if operations and cap >= 0:
                model.Add(sum(operations) <= cap)

    cum_terms: list = []
    for day in range(current_day, ops_horizon):
        for s in subsets:
            cash = s["cash_by_day"].get(day, 0)
            if cash:
                cum_terms.append(y[s["id"]] * cash)
        if cum_terms:
            model.Add(money + sum(cum_terms) >= 0)

    model.Maximize(sum(int(s["weight"]) * y[s["id"]] for s in subsets))

    limit = SOLVER_TIME_LIMIT_S
    if time_limit_s is not None:
        limit = min(SOLVER_TIME_LIMIT_S, max(2.0, time_limit_s))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = limit
    solver.parameters.num_workers = 8
    t0 = time.perf_counter()
    status = solver.Solve(model)
    solve_s = time.perf_counter() - t0
    status_name = solver.StatusName(status)

    placements: list[dict] = []
    selected_subsets: list[dict] = []
    if _solver_has_solution(solver):
        selected_subsets = _selected_subsets(solver, y, subsets)
        placements = _as_placements(selected_subsets)

    source = "cpsat"
    if not placements:
        placements, selected_subsets = _greedy_pack_with_subsets(
            subsets, existing_load, current_day, ops_horizon, money=money
        )
        source = "greedy"

    obj = (
        solver.ObjectiveValue()
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        else None
    )

    peak_spend, cash_floor = _cash_metrics(
        selected_subsets, money, current_day, ops_horizon
    )

    peak_by_worker = ops_budget.peak_load_by_worker(
        selected_subsets, existing_load, current_day, ops_horizon
    )
    peak_parts = " ".join(
        f"{w}={load}/{workers.net_tile_ops(w)}"
        for w, (peak_day, load) in peak_by_worker.items()
        if load > 0 or w == "farmer"
    )

    print(
        f"[planner] day={current_day} status={status_name} "
        f"candidates={len(subsets)} (crop={len(crop_subsets)} "
        f"animal={len(animal_subsets)}) selected={len(placements)} "
        f"source={source} obj={obj} capital={peak_spend} "
        f"cash_floor={cash_floor} limit={limit:.1f} solve={solve_s:.1f}"
    )
    print(f"[planner] peak_ops {peak_parts}")
    _log_plan(current_day, placements)
    return placements
