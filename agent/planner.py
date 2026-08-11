"""Weighted set-packing planner for forward season assignments (crops + animals)."""

from __future__ import annotations

from ortools.sat.python import cp_model

from agent import animal_rollouts, ops_budget, rollouts

NUM_TILES = 9
PLAN_HORIZON = rollouts.PLAN_HORIZON
OPS_HORIZON = rollouts.SEASON_DAYS
SOLVER_TIME_LIMIT_S = 8.0

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
    shop_demand: dict[str, int] | None = None,
) -> list[dict]:
    elements = _build_elements(current_day, plan_horizon)
    element_set = set(elements)
    subsets: list[dict] = []
    demand = shop_demand or {}

    for animal, profile in animal_rollouts.animal_options():
        product = animal_rollouts.product_for(animal)
        d = demand.get(product, 0)
        cost = animal_rollouts.animal_cost(animal)

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
                    animal, place_day, ops_horizon, profile
                )
                weight = rev * (1 + d) - cost - feed_days * animal_rollouts.WHEAT_PRICE

                subsets.append(
                    {
                        "id": f"S{len(subsets)}",
                        "kind": "animal",
                        "animal": animal,
                        "profile": profile,
                        "tile": tile,
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
) -> dict[int, int]:
    """Ops from in-progress plants/animals and same-day weed DIG."""
    load: dict[int, int] = {}
    for state in tile_states:
        if state is None:
            continue
        _tile, label, start_day, profile, kind = state
        ops = ops_budget.executor_ops_by_day(
            kind, label, profile, start_day, horizon, min_day=current_day
        )
        for cal, n_ops in ops.items():
            if current_day <= cal < horizon:
                load[cal] = load.get(cal, 0) + n_ops
    if weed_tiles:
        load[current_day] = load.get(current_day, 0) + len(weed_tiles)
    return load


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
    existing_load: dict[int, int],
    current_day: int,
    ops_horizon: int,
) -> tuple[list[dict], list[dict]]:
    """Weight-descending greedy packing when CP-SAT yields nothing."""
    occupied: set[tuple[int, int]] = set()
    day_ops = {
        d: existing_load.get(d, 0) for d in range(current_day, ops_horizon)
    }
    chosen: list[dict] = []

    for s in sorted(subsets, key=lambda x: x["weight"], reverse=True):
        if s["weight"] <= 0:
            continue
        if s["subset"] & occupied:
            continue
        fits = True
        for d, ops in s["ops_by_day"].items():
            if day_ops.get(d, 0) + ops > rollouts.daily_op_budget(d):
                fits = False
                break
        if not fits:
            continue
        occupied |= s["subset"]
        for d, ops in s["ops_by_day"].items():
            day_ops[d] = day_ops.get(d, 0) + ops
        chosen.append(s)

    return _as_placements(chosen), chosen


def _greedy_pack(
    subsets: list[dict],
    existing_load: dict[int, int],
    current_day: int,
    ops_horizon: int,
) -> list[dict]:
    placements, _ = _greedy_pack_with_subsets(
        subsets, existing_load, current_day, ops_horizon
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
    plan_horizon: int = PLAN_HORIZON,
    ops_horizon: int = OPS_HORIZON,
    weed_tiles: set[int] | None = None,
    shop_demand: dict[str, int] | None = None,
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

    model = cp_model.CpModel()
    y = {s["id"]: model.NewBoolVar(s["id"]) for s in subsets}

    for e in elements:
        covering = [y[s["id"]] for s in subsets if e in s["subset"]]
        if covering:
            model.Add(sum(covering) <= 1)

    for day in range(current_day, ops_horizon):
        operations = []
        for s in subsets:
            ops = s["ops_by_day"].get(day)
            if not ops:
                continue
            operations.append(y[s["id"]] * ops)

        cap = rollouts.daily_op_budget(day) - existing_load.get(day, 0)
        if operations and cap >= 0:
            model.Add(sum(operations) <= cap)

    model.Maximize(sum(int(s["weight"]) * y[s["id"]] for s in subsets))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVER_TIME_LIMIT_S
    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    placements: list[dict] = []
    selected_subsets: list[dict] = []
    if _solver_has_solution(solver):
        selected_subsets = _selected_subsets(solver, y, subsets)
        placements = _as_placements(selected_subsets)

    source = "cpsat"
    if not placements:
        placements, selected_subsets = _greedy_pack_with_subsets(
            subsets, existing_load, current_day, ops_horizon
        )
        source = "greedy"

    obj = (
        solver.ObjectiveValue()
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        else None
    )

    peak_day, peak_ops = ops_budget.peak_load(
        selected_subsets, existing_load, current_day, ops_horizon
    )
    cap = rollouts.daily_op_budget(peak_day)

    print(
        f"[planner] day={current_day} status={status_name} "
        f"candidates={len(subsets)} (crop={len(crop_subsets)} "
        f"animal={len(animal_subsets)}) selected={len(placements)} "
        f"source={source} obj={obj}"
    )
    print(f"[planner] peak_ops day={peak_day} load={peak_ops}/{cap}")
    _log_plan(current_day, placements)
    return placements
