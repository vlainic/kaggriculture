"""Sequential per-zone CP-SAT with conservative cash handoff."""

from __future__ import annotations

import time
from collections.abc import Callable

from ortools.sat.python import cp_model

from agent.solvers.common import decode_zone_assignment
from agent.solvers.types import SolveResult
from agent.zoning import (
    HAND_DAILY_COST,
    HAND_WORKERS,
    NET_TILE_OPS,
    NUM_TILES,
    WORKERS,
    WORKER_TILES,
)

WHEAT_PRICE = 25
FERT_PRICE = 100
MAX_BUY = NUM_TILES * 30
ZONE_PLACEMENT_BUFFER = 150


def _downstream_cash_reserve(
    remaining_workers: tuple[str, ...],
    horizon: int,
    *,
    charge_hire_daily: bool,
) -> int:
    reserve = 0
    hire_days = min(horizon, 7)
    for w in remaining_workers:
        if charge_hire_daily and w in HAND_WORKERS:
            reserve += HAND_DAILY_COST.get(w, 0) * hire_days
        reserve += ZONE_PLACEMENT_BUFFER
    return reserve


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


def _solve_zone(
    worker: str,
    chains: list,
    *,
    horizon: int,
    n_empty: int,
    locked: dict,
    opening_balances: list[int],
    w_open: int,
    f_open: int,
    max_time: float,
    charge_hire_daily: bool,
    track_shed: bool,
    force_all_idle: bool = False,
    min_close0: int = 0,
    min_balance: int = 0,
):
    model = cp_model.CpModel()
    count = [
        model.NewIntVar(0, n_empty, f"n_{worker}_{c['id']}") for c in chains
    ]
    model.Add(sum(count) == n_empty)
    if force_all_idle:
        idle_ci = next(
            i
            for i, c in enumerate(chains)
            if c.get("id") == "IDLE" or not c.get("raw_chain")
        )
        for ci, var in enumerate(count):
            model.Add(var == (n_empty if ci == idle_ci else 0))

    cap = NET_TILE_OPS[worker]
    for day in range(horizon):
        terms = []
        for ci, chain in enumerate(chains):
            n = chain["daily_tile_ops"][day]
            if n:
                terms.append(count[ci] * n)
        locked_ops = locked["daily_tile_ops"][day]
        if worker in HAND_WORKERS:
            animal_terms = [
                count[ci]
                for ci, chain in enumerate(chains)
                if chain["daily_animal_active"][day]
            ]
            if animal_terms:
                preamble = model.NewBoolVar(f"preamble_{worker}_{day}")
                animal_count = sum(animal_terms)
                model.Add(preamble <= animal_count)
                model.Add(animal_count <= preamble * max(1, n_empty))
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
        W = [model.NewIntVar(0, MAX_BUY, f"W_{worker}_{d}") for d in range(horizon + 1)]
        F = [model.NewIntVar(0, MAX_BUY, f"F_{worker}_{d}") for d in range(horizon + 1)]
        model.Add(W[0] == w_open)
        model.Add(F[0] == f_open)

        for d in range(horizon):
            feed_d = locked["daily_feed"][d] + sum(
                count[ci] * chains[ci]["daily_feed"][d] for ci in range(len(chains))
            )
            fert_d = locked["daily_fert"][d] + sum(
                count[ci] * chains[ci]["daily_fert"][d] for ci in range(len(chains))
            )
            collect_d = locked["daily_collect"][d] + sum(
                count[ci] * chains[ci]["daily_collect"][d] for ci in range(len(chains))
            )
            wheat_d = locked["daily_wheat"][d] + sum(
                count[ci] * chains[ci]["daily_wheat"][d] for ci in range(len(chains))
            )
            bw = model.NewIntVar(0, MAX_BUY, f"buy_w_{worker}_{d}")
            bf = model.NewIntVar(0, MAX_BUY, f"buy_f_{worker}_{d}")
            buy_w.append(bw)
            buy_f.append(bf)
            buy_w_cost.append(WHEAT_PRICE * bw)
            buy_f_cost.append(FERT_PRICE * bf)
            model.Add(W[d] >= feed_d)
            model.Add(F[d] >= fert_d)
            model.Add(W[d + 1] == W[d] - feed_d + wheat_d + bw)
            model.Add(F[d + 1] == F[d] - fert_d + collect_d + bf)

    balance_vars: list = []
    conservative_vars: list = []
    hire = HAND_DAILY_COST.get(worker, 0) if charge_hire_daily else 0

    for d in range(horizon):
        day_terms = [locked["cash_by_day"][d]]
        spend_terms = [locked["spend_by_day"][d]]
        for ci, chain in enumerate(chains):
            cash = chain["cash_by_day"][d]
            if cash:
                day_terms.append(count[ci] * cash)
            spend = chain["spend_by_day"][d]
            if spend:
                spend_terms.append(count[ci] * spend)
        if track_shed:
            day_terms.append(-WHEAT_PRICE * buy_w[d])
            day_terms.append(-FERT_PRICE * buy_f[d])
        if charge_hire_daily and worker in HAND_WORKERS:
            day_terms.append(-hire)
            spend_terms.append(-hire)

        if worker in HAND_WORKERS:
            prev = opening_balances[d] if d < len(opening_balances) else opening_balances[-1]
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

    if min_close0 > 0:
        model.Add(balance_vars[0] >= min_close0)

    obj_terms = [chains[ci]["weight"] * count[ci] for ci in range(len(chains))]
    if track_shed:
        obj_terms.extend(-c for c in buy_w_cost)
        obj_terms.extend(-c for c in buy_f_cost)
    model.Maximize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 8
    solver.parameters.max_time_in_seconds = max_time
    t0 = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - t0

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(
            f"[planner] zone={worker} status={solver.StatusName(status)} "
            f"time={elapsed:.3f}s empty={n_empty} "
            f"open0={opening_balances[0] if opening_balances else 'N/A'}",
            flush=True,
        )
        return None

    w_levels = (
        [int(solver.Value(W[d])) for d in range(horizon + 1)] if track_shed else []
    )
    f_levels = (
        [int(solver.Value(F[d])) for d in range(horizon + 1)] if track_shed else []
    )
    print(
        f"[planner] zone={worker} {solver.StatusName(status)} "
        f"obj={solver.ObjectiveValue():.0f} time={elapsed:.3f}s "
        f"close0={int(solver.Value(balance_vars[0]))} "
        f"cons0={int(solver.Value(conservative_vars[0]))} "
        f"open0={opening_balances[0] if opening_balances else 'N/A'} "
        f"empty={n_empty}",
        flush=True,
    )
    return {
        "balance": [int(solver.Value(b)) for b in balance_vars],
        "conservative": [int(solver.Value(c)) for c in conservative_vars],
        "w_levels": w_levels,
        "f_levels": f_levels,
        "solver": solver,
        "count": count,
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
) -> SolveResult:
    del price_of  # chains already stamped by planner
    empty_set = set(empty_tiles)
    per_zone_time = max_time / max(1, len(WORKERS))
    opening = [starting_money] * horizon
    w_levels = [0] * (horizon + 1)
    f_levels = [0] * (horizon + 1)
    assigned: dict[int, list] = {}
    solved_workers: list[str] = []

    for worker in WORKERS:
        n_empty = empty_counts[worker]
        locked = locked_by_worker[worker]
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

        if worker == WORKERS[0] and track_shed:
            w_open = w_open0
            f_open = f_open0
        elif worker != WORKERS[0] and track_shed:
            w_open = w_levels[1]
            f_open = f_levels[1]
        else:
            w_open = 0
            f_open = 0
        wi = WORKERS.index(worker)
        remaining = WORKERS[wi + 1 :]
        min_close0 = (
            _downstream_cash_reserve(
                remaining, horizon, charge_hire_daily=charge_hire_daily
            )
            if cascade_reserve and remaining
            else 0
        )
        res = _solve_zone(
            worker,
            chains,
            horizon=horizon,
            n_empty=n_empty,
            locked=locked,
            opening_balances=opening,
            w_open=w_open,
            f_open=f_open,
            max_time=per_zone_time,
            charge_hire_daily=charge_hire_daily,
            track_shed=track_shed,
            min_close0=min_close0,
            min_balance=min_balance,
        )
        if res is None:
            break

        zone_empty = {idx for idx in WORKER_TILES[worker] if idx in empty_set}
        assigned.update(
            decode_zone_assignment(
                worker, chains, res["solver"], res["count"], zone_empty
            )
        )
        opening = res["balance"]
        if opening[0] < 0:
            print(
                f"[planner] zone={worker} handoff open0={opening[0]} < 0, stop cascade",
                flush=True,
            )
            solved_workers.append(worker)
            break
        if track_shed:
            w_levels = res["w_levels"]
            f_levels = res["f_levels"]
        solved_workers.append(worker)

    return SolveResult(
        assigned,
        len(solved_workers) == len(WORKERS),
        tuple(solved_workers),
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
                print(
                    f"[planner] zone={worker} apply_replan t{idx + 1}: "
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
