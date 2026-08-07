"""Weighted set-packing planner for forward season assignments."""

from __future__ import annotations

from ortools.sat.python import cp_model

from agent import rollouts

NUM_TILES = 9
PLAN_HORIZON = rollouts.PLAN_HORIZON
OPS_HORIZON = rollouts.SEASON_DAYS
SOLVER_TIME_LIMIT_S = 8.0

TileState = tuple[int, str, int, str]  # tile, crop, planted_day, profile


def _build_elements(current_day: int, horizon: int) -> list[tuple[int, int]]:
    return [
        (tile, day)
        for tile in range(NUM_TILES)
        for day in range(current_day, horizon)
    ]


def _ops_for_lifecycle(
    crop: str,
    profile: str,
    plant_day: int,
    ops_horizon: int,
) -> tuple[dict[int, int], bool]:
    """Tile ops by calendar day; False if any action falls past ops_horizon."""
    ops_by_day: dict[int, int] = {}
    for age_day in rollouts.profile_days(crop, profile):
        cal = plant_day + age_day["age"]
        if cal >= ops_horizon:
            return {}, False
        ops_by_day[cal] = len(age_day["actions"])
    for age in rollouts.fertilize_ages(crop, profile):
        cal = plant_day + age
        if cal >= ops_horizon:
            return {}, False
        ops_by_day[cal] = ops_by_day.get(cal, 0) + 1
    return ops_by_day, True


def _earliest_plant_by_tile(
    plannable_tiles: set[int],
    tile_states: list[TileState | None],
    current_day: int,
) -> dict[int, int]:
    """First calendar day a new lifecycle may start on each tile."""
    earliest = {tile: current_day for tile in plannable_tiles}
    for state in tile_states:
        if state is None:
            continue
        tile, _crop, planted_day, profile = state
        earliest[tile] = planted_day + rollouts.tile_free_age(_crop, profile)
    return earliest


def _build_candidates(
    plannable_tiles: set[int],
    earliest_plant: dict[int, int],
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
    fert_price = int(prices.get("FERTILIZER", 0) or 0)

    for crop, profile in rollouts.plant_options():
        seed = rollouts.seed_cost(crop)
        crop_price = int(prices.get(crop, 0) or 0)
        d = demand.get(crop, 0)
        yield_units = rollouts.expected_yield(crop, profile)
        fert_cost = rollouts.fert_count(crop, profile) * fert_price
        weight = yield_units * crop_price * (1 + d) - seed - fert_cost

        for tile in plannable_tiles:
            start = max(earliest_plant.get(tile, current_day), current_day)
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

                ops_by_day, ops_ok = _ops_for_lifecycle(
                    crop, profile, plant_day, ops_horizon
                )
                if not ops_ok:
                    continue

                subsets.append(
                    {
                        "id": f"S{len(subsets)}",
                        "crop": crop,
                        "profile": profile,
                        "tile": tile,
                        "plant_day": plant_day,
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
    """Ops from in-progress plants plus same-day weed DIG."""
    load: dict[int, int] = {}
    for state in tile_states:
        if state is None:
            continue
        _tile, crop, planted_day, profile = state
        for age_day in rollouts.profile_days(crop, profile):
            cal = planted_day + age_day["age"]
            if current_day <= cal < horizon:
                load[cal] = load.get(cal, 0) + len(age_day["actions"])
        for age in rollouts.fertilize_ages(crop, profile):
            cal = planted_day + age
            if current_day <= cal < horizon:
                load[cal] = load.get(cal, 0) + 1
    if weed_tiles:
        load[current_day] = load.get(current_day, 0) + len(weed_tiles)
    return load


def _as_placements(selected: list[dict]) -> list[dict]:
    return [
        {
            "tile": s["tile"],
            "crop": s["crop"],
            "profile": s["profile"],
            "plant_day": s["plant_day"],
        }
        for s in selected
    ]


def _greedy_pack(
    subsets: list[dict],
    existing_load: dict[int, int],
    current_day: int,
    ops_horizon: int,
) -> list[dict]:
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

    return _as_placements(chosen)


def _solver_has_solution(solver: cp_model.CpSolver) -> bool:
    return bool(solver.ResponseProto().solution)


def _extract_solution(solver: cp_model.CpSolver, y: dict, subsets: list[dict]) -> list[dict]:
    selected = [s for s in subsets if solver.Value(y[s["id"]]) == 1]
    return _as_placements(selected)


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
    """Return selected placements: [{tile, crop, profile, plant_day}, ...]."""
    if not plannable_tiles:
        return []

    earliest_plant = _earliest_plant_by_tile(
        plannable_tiles, tile_states, current_day
    )
    elements = _build_elements(current_day, plan_horizon)
    subsets = _build_candidates(
        plannable_tiles,
        earliest_plant,
        current_day,
        plan_horizon,
        ops_horizon,
        prices,
        shop_demand,
    )
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
    if _solver_has_solution(solver):
        placements = _extract_solution(solver, y, subsets)

    source = "cpsat"
    if not placements:
        placements = _greedy_pack(subsets, existing_load, current_day, ops_horizon)
        source = "greedy"

    obj = (
        solver.ObjectiveValue()
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        else None
    )

    print(
        f"[planner] day={current_day} status={status_name} "
        f"candidates={len(subsets)} selected={len(placements)} "
        f"source={source} obj={obj}"
    )
    return placements
