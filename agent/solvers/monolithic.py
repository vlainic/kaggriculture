"""Monolithic all-zone CP-SAT solver."""

from __future__ import annotations

import time

from ortools.sat.python import cp_model

from agent.solvers.common import decode_monolithic_assignment
from agent.solvers.types import SolveResult
from agent.zoning import (
    HAND_WORKERS,
    HIRE_DAILY_COST,
    NET_TILE_OPS,
    NUM_TILES,
    WORKERS,
    WORKER_TILES,
)

NUM_DAYS = 30
WHEAT_PRICE = 25
FERT_PRICE = 100
MAX_BUY = NUM_TILES * NUM_DAYS
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
) -> SolveResult:
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
                n = chain["daily_tile_ops"][day]
                if n:
                    terms.append(var * n)
            locked_ops = locked["daily_tile_ops"][day]
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

    buy_w: list = []
    buy_f: list = []
    buy_w_cost: list = []
    buy_f_cost: list = []

    if track_shed:
        W = [model.NewIntVar(0, MAX_BUY, f"W_{d}") for d in range(horizon + 1)]
        F = [model.NewIntVar(0, MAX_BUY, f"F_{d}") for d in range(horizon + 1)]
        model.Add(W[0] == w_open0)
        model.Add(F[0] == f_open0)

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
        if track_shed:
            day_terms.append(-WHEAT_PRICE * buy_w[d])
            day_terms.append(-FERT_PRICE * buy_f[d])
        if charge_hire_daily and track_shed:
            day_terms.append(-HIRE_DAILY_COST)
        bal = model.NewIntVar(0, 200_000, f"balance_{d}")
        prev = starting_money if d == 0 else balance_vars[-1]
        model.Add(bal == prev + (sum(day_terms) if day_terms else 0))
        balance_vars.append(bal)

    obj_terms = [
        chains[ci]["weight"] * count[w][ci]
        for w in WORKERS
        for ci in range(len(chains))
    ]
    if track_shed:
        obj_terms.extend([-c for c in buy_w_cost])
        obj_terms.extend([-c for c in buy_f_cost])
    model.Maximize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 8
    solver.parameters.max_time_in_seconds = max_time
    threshold = max(1000, int(OBJECTIVE_GOOD_ENOUGH * horizon / NUM_DAYS))
    callback = _GoodEnoughCallback(threshold)
    t0 = time.perf_counter()
    status = solver.Solve(model, callback)
    elapsed = time.perf_counter() - t0
    status_name = solver.StatusName(status)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(
            f"[planner] monolithic status={status_name} good_enough={callback.hit} "
            f"time={elapsed:.3f}s horizon={horizon} "
            f"empty={sum(empty_counts.values())}",
            flush=True,
        )
        return SolveResult({}, False, ())

    empty_set = set(empty_tiles)
    assigned = decode_monolithic_assignment(chains, solver, count, WORKERS, empty_set)
    obj = solver.ObjectiveValue()
    print(
        f"[planner] monolithic {solver.StatusName(status)} good_enough={callback.hit} "
        f"obj={obj:.0f} time={elapsed:.3f}s horizon={horizon} "
        f"empty={sum(empty_counts.values())}",
        flush=True,
    )
    return SolveResult(assigned, True, WORKERS)


def apply_replan(
    result: SolveResult,
    replan_tiles: list[int],
    tile_queues: dict,
    tile_state: dict | None,
    horizon: int,
    chain_to_queue_items,
) -> int:
    if not result.complete:
        return 0
    for idx in replan_tiles:
        chain = result.assigned.get(idx, [])
        tile_queues[idx] = chain_to_queue_items(chain, horizon)
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
    return len(replan_tiles)
