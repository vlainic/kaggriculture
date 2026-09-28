"""TwoLand WSP cascade — milos-local, workers-scoped (NW + ACTIVE_NE)."""

from __future__ import annotations

from collections.abc import Callable

from milos.wsp import data as rollouts
from milos.wsp import mip
from milos.wsp.config import NUM_DAYS
from milos.replan_lock import empty_locked as _empty_locked
from milos.wsp.farmer import _load_prestart_raw
from milos.wsp.types import SolveResult
from milos.zoning import HAND_WORKERS, NET_TILE_OPS, NUM_TILES, WORKERS, WORKER_TILES


def _locked_conservative_handoff(
    opening: list[int],
    locked: dict,
    horizon: int,
    worker: str,
    *,
    charge_hire_daily: bool,
) -> list[int]:
    from milos.zoning import HAND_DAILY_COST

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
    workers: tuple[str, ...],
) -> bool:
    if horizon != NUM_DAYS:
        return False
    scope = sorted(
        idx for w in workers for idx in WORKER_TILES.get(w, ())
    )
    if sorted(empty_tiles) != scope:
        return False
    for worker in workers:
        if empty_counts.get(worker, 0) != len(WORKER_TILES[worker]):
            return False
    return True


def solve(
    chains: list,
    *,
    horizon: int,
    empty_tiles: list[int],
    empty_counts: dict[str, int] | None = None,
    locked_by_worker: dict[str, dict] | None = None,
    starting_money: int,
    max_time: float = 20.0,
    track_shed: bool = True,
    w_open0: int = 0,
    f_open0: int = 0,
    min_balance: int = 0,
    price_of: Callable[..., int] | None = None,
    charge_hire_daily: bool = True,
    workers: tuple[str, ...] | None = None,
    **kwargs,
) -> SolveResult:
    del chains, kwargs
    worker_list = workers if workers is not None else WORKERS
    counts = empty_counts or {w: 0 for w in worker_list}
    if _is_prestart_solve(horizon, empty_tiles, counts, worker_list):
        assigned, complete, solved_workers = _load_prestart_raw()
        print(
            f"[milos/wsp] twoland prestart tiles={len(assigned)} "
            f"complete={complete} workers={solved_workers}",
            flush=True,
        )
        return SolveResult(assigned, complete, solved_workers)

    if price_of is None:
        base = rollouts.i0_base_prices()
        price_of = lambda product, rel_day=0, _base=base: _base[product]

    empty_set = set(empty_tiles)
    per_zone_time = max_time / max(1, len(worker_list))
    opening = [starting_money] * horizon
    assigned: dict[int, list] = {}
    solved_workers: list[str] = []
    locked_harvest: dict[str, int] = {}
    patterns = mip.build_patterns(horizon, price_of)
    locks = locked_by_worker or {}

    for worker in worker_list:
        n_empty = counts.get(worker, 0)
        locked = locks.get(worker) or _empty_locked(horizon)
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

        zone_empty = [idx for idx in WORKER_TILES[worker] if idx in empty_set]
        if worker == worker_list[0] and track_shed:
            w_open = w_open0
            f_open = f_open0
        else:
            w_open = 0
            f_open = 0

        res = mip.solve_zone(
            patterns,
            horizon=horizon,
            empty_tiles=zone_empty,
            locked=locked,
            locked_counts=locked_harvest,
            opening_balances=opening,
            w_open=w_open,
            f_open=f_open,
            max_time=per_zone_time,
            track_shed=track_shed and worker == worker_list[0],
            min_balance=min_balance,
            price_of=price_of,
            worker=worker,
            net_tile_ops=NET_TILE_OPS.get(worker, 18),
            charge_hire_daily=charge_hire_daily,
        )
        if res is None:
            print(
                f"[milos/wsp] twoland skip zone={worker} INFEASIBLE keep cascade",
                flush=True,
            )
            opening = _locked_conservative_handoff(
                opening,
                locked,
                horizon,
                worker,
                charge_hire_daily=charge_hire_daily,
            )
            continue

        picked = res["picked"]
        assigned.update(
            mip.decode_wsp_assignment(
                empty_set,
                picked,
                tile_order=tuple(WORKER_TILES[worker]),
            )
        )
        for pick in picked:
            for prod, units in pick["pattern"]["harvest_units"].items():
                locked_harvest[prod] = locked_harvest.get(prod, 0) + units
        opening = res["conservative"]
        solved_workers.append(worker)

    return SolveResult(
        assigned,
        len(solved_workers) == len(worker_list),
        tuple(solved_workers),
    )
