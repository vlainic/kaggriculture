"""Weighted set-packing planner for empty-tile plant assignments."""

from __future__ import annotations

from ortools.sat.python import cp_model

from agent import rollouts

NUM_TILES = 9
HORIZON = rollouts.SEASON_DAYS
SOLVER_TIME_LIMIT_S = 8.0


def _build_elements(current_day: int, horizon: int) -> list[tuple[int, int]]:
    return [
        (tile, day)
        for tile in range(NUM_TILES)
        for day in range(current_day, horizon)
    ]


def _build_candidates(
    empty_tiles: set[int],
    current_day: int,
    horizon: int,
    prices: dict[str, int],
) -> list[dict]:
    elements = _build_elements(current_day, horizon)
    element_set = set(elements)
    subsets: list[dict] = []

    for crop in rollouts.crop_names():
        cost = rollouts.seed_cost(crop)
        price = int(prices.get(crop, 0) or 0)
        weight = rollouts.expected_yield(crop) * price - cost

        for tile in empty_tiles:
            for plant_day in range(current_day, horizon):
                if not rollouts.lifecycle_fits(crop, plant_day, horizon):
                    continue

                covered: set[tuple[int, int]] = set()
                ops_by_day: dict[int, int] = {}
                ok = True
                for age_day in rollouts.profile_days(crop):
                    cal = plant_day + age_day["age"]
                    if cal >= horizon:
                        ok = False
                        break
                    cell = (tile, cal)
                    if cell not in element_set:
                        ok = False
                        break
                    covered.add(cell)
                    ops_by_day[cal] = len(age_day["actions"])

                if ok and covered:
                    subsets.append(
                        {
                            "id": f"S{len(subsets)}",
                            "crop": crop,
                            "tile": tile,
                            "plant_day": plant_day,
                            "subset": covered,
                            "ops_by_day": ops_by_day,
                            "weight": weight,
                        }
                    )

    return subsets


def existing_ops_by_day(
    tile_states: list[tuple[int, str, int] | None],
    current_day: int,
    horizon: int,
) -> dict[int, int]:
    """Ops contributed by plants already on tiles: (tile_idx, crop, planted_day)."""
    load: dict[int, int] = {}
    for state in tile_states:
        if state is None:
            continue
        _tile, crop, planted_day = state
        for age_day in rollouts.profile_days(crop):
            cal = planted_day + age_day["age"]
            if current_day <= cal < horizon:
                load[cal] = load.get(cal, 0) + len(age_day["actions"])
    return load


def _as_placements(selected: list[dict]) -> list[dict]:
    return [
        {"tile": s["tile"], "crop": s["crop"], "plant_day": s["plant_day"]}
        for s in selected
    ]


def _greedy_pack(
    subsets: list[dict],
    existing_load: dict[int, int],
    current_day: int,
    horizon: int,
) -> list[dict]:
    """Weight-descending greedy packing when CP-SAT yields nothing."""
    occupied: set[tuple[int, int]] = set()
    day_ops = {
        d: existing_load.get(d, 0) for d in range(current_day, horizon)
    }
    chosen: list[dict] = []

    for s in sorted(subsets, key=lambda x: x["weight"], reverse=True):
        if s["weight"] <= 0:
            continue
        if s["subset"] & occupied:
            continue
        fits = True
        for d, ops in s["ops_by_day"].items():
            if day_ops.get(d, 0) + ops > rollouts.DAILY_OP_BUDGET:
                fits = False
                break
        if not fits:
            continue
        occupied |= s["subset"]
        for d, ops in s["ops_by_day"].items():
            day_ops[d] = day_ops.get(d, 0) + ops
        chosen.append(s)

    return _as_placements(chosen)


def _extract_solution(solver: cp_model.CpSolver, y: dict, subsets: list[dict]) -> list[dict]:
    selected = []
    for s in subsets:
        try:
            if solver.Value(y[s["id"]]) == 1:
                selected.append(s)
        except Exception:
            return []
    return _as_placements(selected)


def solve_plan(
    empty_tiles: set[int],
    tile_states: list[tuple[int, str, int] | None],
    current_day: int,
    prices: dict[str, int],
    horizon: int = HORIZON,
) -> list[dict]:
    """Return selected placements: [{tile, crop, plant_day}, ...]."""
    if not empty_tiles:
        return []

    elements = _build_elements(current_day, horizon)
    subsets = _build_candidates(empty_tiles, current_day, horizon, prices)
    if not subsets:
        print(f"[planner] day={current_day} no candidates empty={sorted(empty_tiles)}")
        return []

    existing_load = existing_ops_by_day(tile_states, current_day, horizon)

    model = cp_model.CpModel()
    y = {s["id"]: model.NewBoolVar(s["id"]) for s in subsets}

    for e in elements:
        covering = [y[s["id"]] for s in subsets if e in s["subset"]]
        if covering:
            model.Add(sum(covering) <= 1)

    for day in range(current_day, horizon):
        operations = []
        for s in subsets:
            ops = s["ops_by_day"].get(day)
            if not ops:
                continue
            operations.append(y[s["id"]] * ops)

        cap = rollouts.DAILY_OP_BUDGET - existing_load.get(day, 0)
        if operations and cap >= 0:
            model.Add(sum(operations) <= cap)

    model.Maximize(sum(int(s["weight"]) * y[s["id"]] for s in subsets))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVER_TIME_LIMIT_S
    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    placements: list[dict] = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        placements = _extract_solution(solver, y, subsets)
    elif status == cp_model.UNKNOWN:
        # Timed out: try reading an incumbent if one exists.
        placements = _extract_solution(solver, y, subsets)

    source = "cpsat"
    if not placements:
        placements = _greedy_pack(subsets, existing_load, current_day, horizon)
        source = "greedy"

    obj = None
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        try:
            obj = solver.ObjectiveValue()
        except Exception:
            obj = None

    print(
        f"[planner] day={current_day} status={status_name} "
        f"candidates={len(subsets)} selected={len(placements)} "
        f"source={source} obj={obj}"
    )
    return placements
