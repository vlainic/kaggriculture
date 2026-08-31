"""Reproduce day-0 hire1 INFEASIBLE: all-IDLE fixed assignment test."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import animal_rollouts, dp_catalog, pricing, rollouts
from agent.planner import (
    NUM_DAYS,
    STARTING_MONEY,
    _build_chains,
    _empty_locked,
    _load_json,
)
from agent.solvers import zonewise
from agent.zoning import WORKERS, WORKER_TILES, bind

bind()


def _i0_prices(crops_data: dict, animals_data: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for crop in rollouts.CROP_NAMES:
        out[crop] = rollouts.base_price(crop)
    for animal in animal_rollouts.animal_names():
        out[animal] = animal_rollouts.animal_cost(animal)
    for product in animal_rollouts.ANIMAL_PRODUCTS:
        out[product] = animals_data["products"][product]["base_price"]
    out["FERTILIZER"] = 100
    out["WHEAT"] = 25
    return out


def main() -> None:
    crops_data = _load_json("crop_rollouts.json")
    animals_data = animal_rollouts.data()
    i0 = _i0_prices(crops_data, animals_data)
    price_of = pricing.make_price_of({}, [], i0)
    handmade = dp_catalog.build_catalog(NUM_DAYS, price_of)
    chains = _build_chains(crops_data, animals_data, handmade, NUM_DAYS, price_of)
    idle_ci = next(
        i for i, c in enumerate(chains) if c.get("id") == "IDLE" or not c["raw_chain"]
    )
    print(f"catalog chains={len(chains)} idle_ci={idle_ci} id={chains[idle_ci]['id']}")

    empty_counts = {w: len(WORKER_TILES[w]) for w in WORKERS}
    locked_by_worker = {w: _empty_locked(NUM_DAYS) for w in WORKERS}
    result = zonewise.solve(
        chains,
        horizon=NUM_DAYS,
        empty_tiles=list(range(sum(empty_counts.values()))),
        empty_counts=empty_counts,
        locked_by_worker=locked_by_worker,
        starting_money=STARTING_MONEY,
        max_time=20.0,
    )
    print(f"day-0 cascade: complete={result.complete} workers={result.solved_workers}")

    # Smoke-captured farmer -> hire1 handoff (open0=2820, empty shed W/F on day 0)
    opening = [2820] * NUM_DAYS
    locked = _empty_locked(NUM_DAYS)

    free = zonewise._solve_zone(  # noqa: SLF001
        "hire1",
        chains,
        horizon=NUM_DAYS,
        n_empty=5,
        locked=locked,
        opening_balances=opening,
        w_open=0,
        f_open=0,
        max_time=30.0,
        charge_hire_daily=True,
        track_shed=True,
    )
    print(f"hire1 free solve: {'INFEASIBLE' if free is None else 'FEASIBLE'}")

    fixed = zonewise._solve_zone(  # noqa: SLF001
        "hire1",
        chains,
        horizon=NUM_DAYS,
        n_empty=5,
        locked=locked,
        opening_balances=opening,
        w_open=0,
        f_open=0,
        max_time=30.0,
        charge_hire_daily=True,
        track_shed=True,
        force_all_idle=True,
    )
    if fixed is None:
        print("hire1 all-IDLE fixed: INFEASIBLE -> exogenous constraint (not catalog)")
    else:
        print(f"hire1 all-IDLE fixed: FEASIBLE close0={fixed['balance'][0]} -> catalog bug")


if __name__ == "__main__":
    main()
